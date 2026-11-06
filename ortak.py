"""Ajan Ofisi ortak yardımcıları: yollar, ajan tablosu, olay günlüğü, durum dosyaları."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import shutil
import sys
import threading
import time

if sys.platform == "win32":
    import ctypes
    import msvcrt
else:
    import fcntl

KOK = os.path.dirname(os.path.abspath(__file__))
# Yapılandırma: ajanlar.example.json'ı ajanlar.json olarak kopyala (ajanlar.json .gitignore'da).
# Veri kökü: sunucuda (Docker) tek volume (OFIS_VERI=/veri); yerelde kod klasörü (bugünkü davranış).
VERI = os.environ.get("OFIS_VERI") or KOK
SUNUCU = os.environ.get("OFIS_SUNUCU") == "1"  # sunucu modu: gizli dizin, ajan kısıtları (bkz. sunucu_araclari)
AJANLAR_DOSYASI = os.environ.get("OFIS_AJANLAR", os.path.join(VERI, "ajanlar.json"))
OLAYLAR = os.path.join(VERI, "olaylar.jsonl")
DURUM_DIZINI = os.path.join(VERI, "durum")
KOSU_DIZINI = os.path.join(VERI, "kosular")
CIKTI_DIZINI = os.path.join(VERI, "cikti")
HAFIZA_DIZINI = os.path.join(VERI, "hafiza")


def gizli_dizin():
    """Hesap, oturumlar ve .env: sunucuda ajanların okuyamadığı VERI/gizli (0700); yerelde durum/ (bugünkü)."""
    return os.path.join(VERI, "gizli") if SUNUCU else DURUM_DIZINI


def env_dosyasi():
    return os.path.join(gizli_dizin(), ".env") if SUNUCU else os.path.join(VERI, ".env")


def claude_md_tohumla():
    """Veri kökü kod klasöründen ayrıysa CEO anayasasını oraya bir kez kopyalar (sunucuda düzenlenebilsin)."""
    hedef = os.path.join(VERI, "CLAUDE.md")
    if os.path.normpath(VERI) != os.path.normpath(KOK) and not os.path.exists(hedef):
        os.makedirs(VERI, exist_ok=True)
        with open(os.path.join(KOK, "CLAUDE.md"), encoding="utf-8") as f:
            atomik_yaz(hedef, f.read())

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
    """Varsayılan yasaklar her zaman; dosyadakiler onlara eklenir (sıra korunur, tekrar yok). Sunucuda ek yasaklar."""
    return list(dict.fromkeys([*VARSAYILAN_YASAK, *(veri.get("varsayilan_yasak_araclar") or []),
                               *(SUNUCU_YASAK if SUNUCU else [])]))


# ---------- sunucu modu: kısıtlı ajanlar ----------
# Serbest Bash yok: kandırılmış bir ajan anahtarı/dosyaları okuyup dışarı sızdıramasın. Yalnız güvenli kalıplar.
SUNUCU_BASH = ["Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git add:*)", "Bash(git commit:*)",
               "Bash(ls:*)", "Bash(npm test:*)", "Bash(pytest:*)", "Bash(python -m pytest:*)"]
SUNUCU_YASAK = ["Bash(env:*)", "Bash(printenv:*)", "Read(/proc/**)"]  # süreç ortamından anahtar okunmasın


def sunucu_araclari(izinli):
    """Serbest "Bash" → güvenli kalıplar; listede olmayan Bash(...) kalıpları düşer; diğer araçlar aynen kalır."""
    sonuc = []
    for a in izinli or []:
        if a == "Bash":
            sonuc += SUNUCU_BASH
        elif not a.startswith("Bash(") or a in SUNUCU_BASH:
            sonuc.append(a)
    return list(dict.fromkeys(sonuc))


def calisma_icinde(cwd):
    kok = os.path.normcase(os.path.normpath(os.path.join(VERI, "calisma")))
    return os.path.normcase(os.path.normpath(cwd)).startswith(kok + os.sep)


def ajan_klasoru_ac(yol):
    """Ajanın yazacağı klasör: sunucuda ayrı 'ajan' kullanıcısı da yazabilsin (grup ekip, setgid)."""
    os.makedirs(yol, exist_ok=True)
    if SUNUCU:
        os.chmod(yol, 0o2770)


BAGLANTI_HATASI = "Claude bağlantısı kurulmadı ya da geçersiz: üstteki Claude panelinden bağla."
_BAGLANTI_IZI = re.compile(r"not logged in|/login|invalid api key|api key|oauth token|authentication", re.I)


def baglanti_hatasi_mi(metin):
    """claude'un "giriş yok / anahtar geçersiz" cevabı mı? (kullanıcıya anlaşılır mesaj gösterilir)"""
    return bool(_BAGLANTI_IZI.search(metin or ""))


_ARA = object()


def kosu_modu(platform=None, tmux_yolu=_ARA):
    """Ajan koşusu nasıl açılır: Windows → konsol penceresi, tmux varsa → tmux, yoksa (Docker) → arka plan."""
    if (platform or sys.platform) == "win32":
        return "konsol"
    tmux = shutil.which("tmux") if tmux_yolu is _ARA else tmux_yolu
    return "tmux" if tmux else "arka"


def cwd_coz(cwd):
    """Göreli çalışma klasörü ofis klasörüne (KOK) göre çözülür; boş kalır (kurulmamış)."""
    if not cwd:
        return ""
    yol = os.path.expanduser(cwd)
    return os.path.normpath(yol if os.path.isabs(yol) else os.path.join(VERI, yol))


def ajanlari_yukle():
    try:
        with open(AJANLAR_DOSYASI, encoding="utf-8") as f:
            veri = json.load(f)
    except FileNotFoundError:
        veri = en_kucuk_yapilandirma()
        atomik_yaz(AJANLAR_DOSYASI, json.dumps(veri, ensure_ascii=False, indent=2))
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
            # sunucuda ajan yalnız VERI/calisma altında çalışır (CEO araçsız, hariç)
            "kurulu": bool(cwd) and os.path.isdir(cwd) and (not SUNUCU or ajan["id"] == "ceo" or calisma_icinde(cwd)),
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


def atomik_yaz(yol, metin, izin=None):
    """Geçici dosyaya yazıp yerine koyar. Windows'ta hedef başka bir iş parçacığı/süreçte açıkken os.replace
    PermissionError verir: kısa aralıklarla yeniden denenir. Geçici ad süreç/iş parçacığına özgüdür."""
    gecici = f"{yol}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(metin)
    if izin is not None:
        os.chmod(gecici, izin)
    for deneme in range(20):
        try:
            os.replace(gecici, yol)
            return
        except PermissionError:
            if deneme == 19:
                try:
                    os.remove(gecici)
                finally:
                    raise
            time.sleep(0.05)


def durum_yaz(ajan_id, durum):
    atomik_yaz(durum_yolu(ajan_id), json.dumps(durum, ensure_ascii=False, indent=1))


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
ENV_SATIRI = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
SAAT_DESENI = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
ENV_IZIN = 0o600  # .env yalnız sahibi okuyabilsin (paylaşılan Linux/macOS makineleri)


SIR_ONEKLERI = ("OFIS_TELEGRAM_", "OFIS_CLAUDE_")


def kosucu_ortami():
    """kosucu.py süreci: veri kökü gibi ayarlar kalır, sırlar (Telegram, Claude) çıkar."""
    return {k: v for k, v in os.environ.items() if not k.startswith(SIR_ONEKLERI)}


def alt_surec_ortami(env_yolu=None):
    """claude süreçleri: ofis ayarları çıkar; Claude bağlantısı (.env) varsa ilgili değişkenle verilir."""
    o = {k: v for k, v in os.environ.items() if not k.startswith("OFIS_")}
    env = env_oku(env_yolu)
    if env.get("OFIS_CLAUDE_API_KEY"):
        o["ANTHROPIC_API_KEY"] = env["OFIS_CLAUDE_API_KEY"]; o.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    elif env.get("OFIS_CLAUDE_TOKEN"):
        o["CLAUDE_CODE_OAUTH_TOKEN"] = env["OFIS_CLAUDE_TOKEN"]; o.pop("ANTHROPIC_API_KEY", None)
    return o


def env_oku(yol=None):
    """ANAHTAR=deger satırlarını okur; # ve boş satırlar atlanır, tırnaklar soyulur. Dosya yoksa {}."""
    try:
        with open(yol or env_dosyasi(), encoding="utf-8") as f:
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
    yol = yol or env_dosyasi()
    os.makedirs(os.path.dirname(yol), exist_ok=True)
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
    atomik_yaz(yol, "\n".join(yeni) + "\n", ENV_IZIN)


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