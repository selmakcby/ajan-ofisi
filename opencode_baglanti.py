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
import sys

import ortak

VARSAYILAN_TEST_MODEL = "opencode/deepseek-v4.1-flash-free"
AJAN_ORTAM = "HOME,OPENCODE_CONFIG,OPENCODE_DISABLE_AUTOUPDATE"


def model_cache_yolu():
    return os.path.join(ortak.DURUM_DIZINI, "opencode-modeller.json")


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


def _modeller_getir():
    """`opencode models` çalıştırıp provider/model satırlarını döndürür (yavaş olabilir)."""
    try:
        r = subprocess.run(_komut([exe(), "models"]), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90, env=_ortam())
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("opencode komutu çalıştırılamadı.") from None
    if r.returncode != 0:
        raise ValueError("Model listesi alınamadı (opencode kurulumu/oturumu?).")
    desen = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9._:-]+$")
    liste = [s.strip() for s in (r.stdout or "").splitlines() if desen.match(s.strip())]
    return list(dict.fromkeys(liste))[:300]


def _cache_oku():
    try:
        with open(model_cache_yolu(), encoding="utf-8") as f:
            veri = json.load(f)
        if isinstance(veri, dict) and isinstance(veri.get("modeller"), list):
            return veri
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def model_ozeti():
    """Önbellekteki model listesi (komut çalıştırmadan, hızlı). Yoksa boş."""
    c = _cache_oku()
    return c or {"modeller": [], "zaman": None}


def _cache_yaz(liste):
    try:
        os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
        gecici = model_cache_yolu() + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({"modeller": liste, "zaman": ortak.simdi_iso()}, f, ensure_ascii=False, indent=1)
        os.replace(gecici, model_cache_yolu())
    except OSError:
        pass


def modeller(tazele=False):
    """Model listesi: JSON önbellekten (hızlı); tazele=True ya da önbellek yoksa `opencode models` çalışır."""
    if not tazele:
        c = _cache_oku()
        if c:
            return c
    liste = _modeller_getir()
    _cache_yaz(liste)
    return {"modeller": liste, "zaman": ortak.simdi_iso()}


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


def _auth_helper_komut():
    """Kimlik deposunu yöneten yardımcı betiği çalıştıracak komut (sunucuda sudo ile ajan)."""
    if ortak.SUNUCU:
        # HOME korunur: auth.json ajanın ev dizininde (/veri/ev-ajan) olsun.
        return ["sudo", "-n", "-u", "ajan", "--preserve-env=HOME", "--", "python3",
                "/uygulama/docker/opencode_auth.py"]
    return [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "docker", "opencode_auth.py")]


def auth_islem(veri):
    """auth.json yönetimi: liste / ekle / sil. Anahtar hiçbir zaman geri döndürülmez."""
    try:
        r = subprocess.run(_auth_helper_komut(), input=json.dumps(veri), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=45, env=_ortam())
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("Opencode kimlik deposuna ulaşılamadı.") from None
    try:
        sonuc = json.loads((r.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        raise ValueError("Kimlik deposu yanıtı okunamadı.") from None
    if isinstance(sonuc, dict) and sonuc.get("hata"):
        raise ValueError(sonuc["hata"])
    if r.returncode != 0:
        raise ValueError("Kimlik deposu işlemi başarısız.")
    return sonuc


def islem(veri, env_yolu=None):
    i = veri.get("islem")
    if i == "dene":
        return {**durum(env_yolu), "deneme": baglanti_dene(env_yolu)}
    if i == "modeller":
        return {**durum(env_yolu), **modeller(tazele=bool(veri.get("tazele")))}
    if i == "auth-liste":
        return auth_islem({"islem": "liste"})
    if i == "auth-ekle":
        auth_islem({"islem": "ekle", "saglayici": veri.get("saglayici"), "anahtar": veri.get("anahtar")})
        return {"tamam": True, **auth_islem({"islem": "liste"})}
    if i == "auth-sil":
        auth_islem({"islem": "sil", "saglayici": veri.get("saglayici")})
        return {"tamam": True, **auth_islem({"islem": "liste"})}
    raise ValueError("bilinmeyen işlem")
