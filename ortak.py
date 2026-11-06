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


def ajanlari_yukle():
    try:
        with open(AJANLAR_DOSYASI, encoding="utf-8") as f:
            veri = json.load(f)
    except FileNotFoundError as e:
        raise YapilandirmaHatasi(
            f"{os.path.basename(AJANLAR_DOSYASI)} yok. Önce: cp ajanlar.example.json ajanlar.json"
        ) from e
    if not isinstance(veri, dict) or not isinstance(veri.get("ajanlar"), list):
        raise YapilandirmaHatasi("ajanlar.json içinde 'ajanlar' listesi olmalı")
    tablo = {}
    for ajan in veri["ajanlar"]:
        if not AJAN_ID_DESENI.match(ajan["id"]):
            raise ValueError(f"geçersiz ajan id: {ajan['id']!r}")
        oda = ajan.get("oda") or "genel"
        if not isinstance(oda, str) or not ODA_ID_DESENI.fullmatch(oda):
            raise ValueError(f"geçersiz oda id: {oda!r} (ajan {ajan['id']})")
        kurulu = os.path.isdir(os.path.expanduser(ajan.get("cwd") or ""))
        tablo[ajan["id"]] = {
            **ajan,
            "oda": oda,
            "cwd": os.path.expanduser(ajan.get("cwd") or ""),
            "kurulu": kurulu,
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