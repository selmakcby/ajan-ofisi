"""Ajan Ofisi ortak yardımcıları: yollar, ajan tablosu, olay günlüğü, durum dosyaları."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import sys
import time

if sys.platform == "win32":
    import ctypes
    import msvcrt
else:
    import fcntl

KOK = os.path.dirname(os.path.abspath(__file__))
# Yapılandırma: ajanlar.example.json'ı ajanlar.json olarak kopyala (ajanlar.json .gitignore'da).
AJANLAR_DOSYASI = os.environ.get("OFIS_AJANLAR", os.path.join(KOK, "ajanlar.json"))
OLAYLAR = os.path.join(KOK, "olaylar.jsonl")
DURUM_DIZINI = os.path.join(KOK, "durum")
KOSU_DIZINI = os.path.join(KOK, "kosular")
CIKTI_DIZINI = os.path.join(KOK, "cikti")
HAFIZA_DIZINI = os.path.join(KOK, "hafiza")

MAKS_GIRDI = 4000
MAKS_HAFIZA_EKI = 1200
AJAN_ID_DESENI = re.compile(r"^[a-z0-9-]{1,40}$")
# Oda id'si serbest (sahnede yoksa otomatik açılır) ama prompt'a ve olaylara girdiği için harf/rakam/_/- ve en çok 40 karakter.
ODA_ID_DESENI = re.compile(r"[\w-]{1,40}")


def simdi_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def bugun():
    return datetime.now().strftime("%Y-%m-%d")


class YapilandirmaHatasi(Exception):
    pass


VARSAYILAN_YASAK = ["Read(**/.env)", "Read(**/.env.*)", "Read(~/.env)", "Bash(rm:*)", "Bash(git push:*)",
                    "Bash(curl:*)", "Bash(open:*)"]


def en_kucuk_yapilandirma():
    """İlk açılışta (ajanlar.json yokken) yazılan yapılandırma: yalnız CEO. Gerisi kurulum sihirbazından gelir."""
    return {
        "surum": 2,
        "ayarlar": {"kullanici": "", "marka": "Ajan Ofisi"},
        "odalar": [],
        "varsayilan_yasak_araclar": list(VARSAYILAN_YASAK),
        "ajanlar": [{
            "id": "ceo", "ad": "CEO", "oda": "ceo", "cwd": ".", "model": "sonnet", "ne_zaman": "istek",
            "ne_zaman_metin": "Sen konuşunca",
            "aciklama": "Yalnız onunla konuşursun; işi ajanlara dağıtır. Araçsız, yalnız plan çıkarır.",
            "izinli_araclar": [], "hazir_gorevler": [],
        }],
    }


def yasakli_araclar(veri):
    """Varsayılan yasaklar her zaman; dosyadakiler onlara eklenir (sıra korunur, tekrar yok)."""
    return list(dict.fromkeys([*VARSAYILAN_YASAK, *(veri.get("varsayilan_yasak_araclar") or [])]))


def cwd_coz(cwd):
    """Göreli çalışma klasörü ofis klasörüne (KOK) göre çözülür; boş kalır (kurulmamış)."""
    if not cwd:
        return ""
    yol = os.path.expanduser(cwd)
    return os.path.normpath(yol if os.path.isabs(yol) else os.path.join(KOK, yol))


def ajanlari_yukle():
    try:
        with open(AJANLAR_DOSYASI, encoding="utf-8") as f:
            veri = json.load(f)
    except FileNotFoundError:
        veri = en_kucuk_yapilandirma()
        gecici = AJANLAR_DOSYASI + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        os.replace(gecici, AJANLAR_DOSYASI)
    if not isinstance(veri, dict) or not isinstance(veri.get("ajanlar"), list):
        raise YapilandirmaHatasi("ajanlar.json içinde 'ajanlar' listesi olmalı")
    tablo = {}
    for ajan in veri["ajanlar"]:
        if not AJAN_ID_DESENI.match(ajan["id"]):
            raise ValueError(f"geçersiz ajan id: {ajan['id']!r}")
        oda = ajan.get("oda") or "genel"
        if not isinstance(oda, str) or not ODA_ID_DESENI.fullmatch(oda):
            raise ValueError(f"geçersiz oda id: {oda!r} (ajan {ajan['id']})")
        cwd = cwd_coz(ajan.get("cwd"))
        tablo[ajan["id"]] = {
            **ajan,
            "oda": oda,
            "cwd": cwd,
            "kurulu": bool(cwd) and os.path.isdir(cwd),
        }
    return veri, tablo


def ayarlar(veri):
    """Arayüz ayarları: kullanıcı adı (selamlama) ve marka. İkisi de isteğe bağlı."""
    a = veri.get("ayarlar") if isinstance(veri.get("ayarlar"), dict) else {}
    return {
        "kullanici": str(a.get("kullanici") or "")[:40],
        "marka": str(a.get("marka") or "Ajan Ofisi")[:40],
    }


@contextmanager
def dosya_kilidi(f):
    """Platform bağımsız dosya kilitleme bağlam yöneticisi."""
    fd = f.fileno()
    if sys.platform == "win32":
        # Windows: Dosyanın başından 1 baytlık alanı kilitler
        f.seek(0)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        f.seek(0, os.SEEK_END)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            f.seek(0, os.SEEK_END)
    else:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def olay_yaz(olay):
    """olaylar.jsonl'e tek satır ekler (süreçler arası kilitli)."""
    satir = json.dumps({"zaman": simdi_iso(), **olay}, ensure_ascii=False)
    with open(OLAYLAR, "a", encoding="utf-8") as f:
        with dosya_kilidi(f):
            f.write(satir + "\n")
            f.flush()


def durum_yolu(ajan_id):
    return os.path.join(DURUM_DIZINI, f"{ajan_id}.json")


def durum_oku(ajan_id):
    try:
        with open(durum_yolu(ajan_id), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def durum_yaz(ajan_id, durum):
    gecici = durum_yolu(ajan_id) + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False, indent=1)
    os.replace(gecici, durum_yolu(ajan_id))


def surec_yasiyor(pid):
    """Verilen PID'ye sahip sürecin çalışıp çalışmadığını platforma uygun kontrol eder."""
    if not pid:
        return False
    try:
        pid = int(pid)
    except ValueError:
        return False

    if sys.platform == "win32":
        # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        STILL_ACTIVE = 259

        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
        )
        if not handle:
            return False

        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True


def ajan_mesgul(ajan_id):
    """Ajan şu an koşuyor mu? Ölü süreçten kalan 'calisiyor' kaydını meşgul saymaz."""
    d = durum_oku(ajan_id)
    if not d or d.get("durum") not in ("basliyor", "calisiyor"):
        return False
    if surec_yasiyor(d.get("pid")):
        return True
    return d.get("durum") == "basliyor" and time.time() - d.get("baslangic_ts", 0) < 30


# ---------- .env ve Telegram ayarı ----------
# .env repoya girmez (.gitignore) ve ajanların okuması varsayilan_yasak_araclar ile yasaktır.
ENV_DOSYASI = os.path.join(KOK, ".env")
ENV_SATIRI = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
SAAT_DESENI = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
ENV_IZIN = 0o600  # .env yalnız sahibi okuyabilsin (paylaşılan Linux/macOS makineleri)


def alt_surec_ortami():
    """Ajan/claude süreçlerine verilecek ortam: Telegram ayarları (token) çıkarılır."""
    return {k: v for k, v in os.environ.items() if not k.startswith("OFIS_TELEGRAM_")}


def env_oku(yol=None):
    """ANAHTAR=deger satırlarını okur; # ve boş satırlar atlanır, tırnaklar soyulur. Dosya yoksa {}."""
    try:
        with open(yol or ENV_DOSYASI, encoding="utf-8") as f:
            satirlar = f.read().splitlines()
    except FileNotFoundError:
        return {}
    sonuc = {}
    for satir in satirlar:
        e = ENV_SATIRI.match(satir)
        if not e or satir.lstrip().startswith("#"):
            continue
        deger = e.group(2).strip()
        if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in "\"'":
            deger = deger[1:-1]
        sonuc[e.group(1)] = deger
    return sonuc


def env_yaz(guncel, yol=None):
    """Verilen anahtarları günceller (yoksa sona ekler), None olanları siler; diğer satırlar aynen kalır."""
    yol = yol or ENV_DOSYASI
    try:
        with open(yol, encoding="utf-8") as f:
            satirlar = f.read().splitlines()
    except FileNotFoundError:
        satirlar = []
    kalan = dict(guncel)
    yeni = []
    for satir in satirlar:
        e = ENV_SATIRI.match(satir)
        if e and not satir.lstrip().startswith("#") and e.group(1) in guncel:
            deger = kalan.pop(e.group(1), None)
            if deger is not None:
                yeni.append(f"{e.group(1)}={deger}")
            continue  # silinen ya da aynı anahtarın tekrarı
        yeni.append(satir)
    yeni += [f"{k}={v}" for k, v in kalan.items() if v is not None]
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write("\n".join(yeni) + "\n")
    os.chmod(gecici, ENV_IZIN)
    os.replace(gecici, yol)


def telegram_ayari(yol=None):
    """{"token", "kullanici": int|None, "rapor_saati": (saat, dakika)}; token yoksa None. Ortam değişkeni .env'i ezer."""
    env = env_oku(yol)
    al = lambda k: (os.environ.get(k) or env.get(k) or "").strip()  # noqa: E731
    token = al("OFIS_TELEGRAM_TOKEN")
    if not token:
        return None
    kullanici = al("OFIS_TELEGRAM_KULLANICI")
    saat = SAAT_DESENI.match(al("OFIS_TELEGRAM_RAPOR_SAATI"))
    return {
        "token": token,
        "kullanici": int(kullanici) if kullanici.isdigit() else None,
        "rapor_saati": (int(saat.group(1)), int(saat.group(2))) if saat else (18, 0),
    }