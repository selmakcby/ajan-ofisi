"""Opencode bağlantısı: kurulu mu, hangi model varsayılan, kimlik doğrulanmış mı?

Opencode kimlik bilgilerini kendi deposunda tutar (~/.local/share/opencode/auth.json).
Sunucuda ajanlar "ajan" kullanıcısıyla ve HOME=/veri/ev-ajan ile çalışır; bu yüzden
durum/deneme çağrıları da aynı kullanıcıyla (sudo) yapılır. Anahtar/token okunmaz,
loga ya da tarayıcıya yazılmaz.
"""
import json
import os
import re
import shutil
import subprocess

import ortak

VARSAYILAN_TEST_MODEL = "opencode/deepseek-v4.1-flash-free"
AJAN_ORTAM = "HOME,OPENCODE_CONFIG,OPENCODE_DISABLE_AUTOUPDATE"


def exe():
    return shutil.which("opencode") or "opencode"


def ajan_home():
    """Sunucuda ajan süreçlerinin ev dizini (auth.json burada aranır)."""
    return os.path.join(ortak.VERI, "ev-ajan") if ortak.SUNUCU else os.path.expanduser("~")


def _komut(argv):
    """Sunucuda ajan kullanıcısı/ev diziniyle çalıştır (kimlik deposu tutarlı olsun)."""
    if not ortak.SUNUCU:
        return argv
    return ["sudo", "-n", "-u", "ajan", "--preserve-env=" + AJAN_ORTAM, "--", *argv]


def _ortam():
    o = {**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "1"}
    if ortak.SUNUCU:
        o["HOME"] = ajan_home()
    return o


def test_modeli(env_yolu=None):
    return (ortak.env_oku(env_yolu).get("OFIS_OPENCODE_MODEL") or VARSAYILAN_TEST_MODEL).strip()


def _auth_dosyalari():
    adaylar = []
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        adaylar.append(os.path.join(xdg, "opencode", "auth.json"))
    adaylar.append(os.path.join(ajan_home(), ".local", "share", "opencode", "auth.json"))
    adaylar.append(os.path.expanduser("~/.local/share/opencode/auth.json"))
    adaylar.append(os.path.expanduser("~/.config/opencode/auth.json"))
    return list(dict.fromkeys(adaylar))


def _auth_var():
    for p in _auth_dosyalari():
        try:
            if os.path.exists(p):
                return True
        except OSError:
            continue
    if ortak.SUNUCU:  # /veri/ev-ajan 0700: ofis okuyamaz, ajan olarak test et
        for p in _auth_dosyalari():
            try:
                r = subprocess.run(_komut(["test", "-f", p]), capture_output=True, timeout=15, env=_ortam())
                if r.returncode == 0:
                    return True
            except (OSError, subprocess.TimeoutExpired):
                break
    return False


def durum(env_yolu=None):
    yol = shutil.which("opencode")
    if not yol:
        return {"tur": "yok", "surum": None, "auth": False, "model": test_modeli(env_yolu)}
    try:
        r = subprocess.run(_komut([yol, "--version"]), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, env=_ortam())
        surum = (r.stdout or "").strip().splitlines()[0][:40] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        surum = None
    return {"tur": "kurulu", "surum": surum, "auth": _auth_var(), "model": test_modeli(env_yolu)}


def modeller():
    """`opencode models` çıktısındaki provider/model satırlarını döndürür (en fazla 200)."""
    try:
        r = subprocess.run(_komut([exe(), "models"]), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90, env=_ortam())
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("opencode komutu çalıştırılamadı.") from None
    if r.returncode != 0:
        raise ValueError("Model listesi alınamadı (opencode kurulumu/oturumu?).")
    desen = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9._:-]+$")
    liste = [s.strip() for s in (r.stdout or "").splitlines() if desen.match(s.strip())]
    return list(dict.fromkeys(liste))[:200]


def baglanti_dene(env_yolu=None):
    """Çok kısa bir opencode çağrısı: kurulum ve kimlik doğrulaması çalışıyor mu?"""
    model = test_modeli(env_yolu)
    if "/" not in model:
        raise ValueError("Deneme modeli 'saglayici/model' biçiminde olmalı (OFIS_OPENCODE_MODEL).")
    try:
        r = subprocess.run(_komut([exe(), "run", "--format", "json", "-m", model, "Yalnız OK yaz."]),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=150, cwd=ajan_home() if ortak.SUNUCU else ortak.VERI, env=_ortam())
    except subprocess.TimeoutExpired:
        raise ValueError("Opencode 150 saniyede cevap vermedi.") from None
    except OSError:
        raise ValueError("opencode çalıştırılamadı (kurulum/izin sorunu).") from None
    metin, hata = "", None
    for satir in (r.stdout or "").splitlines():
        try:
            olay = json.loads(satir)
        except json.JSONDecodeError:
            continue
        if olay.get("type") == "text":
            metin += (olay.get("part") or {}).get("text", "")
        if olay.get("type") == "error":
            hata = str((olay.get("part") or {}).get("error") or olay.get("error") or "")[:200]
    if hata:
        raise ValueError("Opencode bağlantısı çalışmadı: " + hata)
    if not metin.strip() and r.returncode != 0:
        raise ValueError("Opencode bağlantısı çalışmadı; `opencode auth login` ile giriş yap.")
    return {"tamam": True, "yanit": metin.strip()[:80], "model": model}


def islem(veri, env_yolu=None):
    i = veri.get("islem")
    if i == "dene":
        return {**durum(env_yolu), "deneme": baglanti_dene(env_yolu)}
    if i == "modeller":
        return {**durum(env_yolu), "modeller": modeller()}
    raise ValueError("bilinmeyen işlem")
