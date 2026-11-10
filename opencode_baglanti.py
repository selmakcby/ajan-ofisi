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
import time

import ortak

VARSAYILAN_TEST_MODEL = "opencode/deepseek-v4.1-flash-free"
AJAN_ORTAM = "HOME,OPENCODE_CONFIG,OPENCODE_DISABLE_AUTOUPDATE"


def model_cache_yolu():
    return os.path.join(ortak.DURUM_DIZINI, "opencode-modeller.json")


ADAY_YOLLAR = ("/usr/local/bin/opencode", "/usr/bin/opencode", "/opt/opencode/bin/opencode")


def exe():
    """opencode ikilisini bul: PATH, sonra bilinen kurulum yerleri."""
    yol = shutil.which("opencode")
    if yol:
        return yol
    for p in ADAY_YOLLAR:
        try:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        except OSError:
            continue
    return "opencode"


def ajan_home():
    """Sunucuda ajan süreçlerinin ev dizini (auth.json burada aranır)."""
    return os.path.join(ortak.VERI, "ev-ajan") if ortak.SUNUCU else os.path.expanduser("~")


def calisma_dizini():
    """opencode sürecinin başlatılacağı dizin: ofis kullanıcısının erişebildiği bir yer olmalı.
    (/veri/ev-ajan 0700'dir; ofis oraya giremez — Home ayarı sudo ile verilir, cwd ile değil.)"""
    if not ortak.SUNUCU:
        return ortak.VERI
    return ortak.VERI if os.access(ortak.VERI, os.X_OK) else "/tmp"


def _kisa_hata(r):
    """Komutun gerçek hatasını kısa ve anahtarsız biçimde çıkarır."""
    for akis in (r.stderr, r.stdout):
        metin = (akis or "").strip()
        if metin:
            satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
            return " | ".join(satirlar[-3:])[:300]
    return f"çıkış kodu {r.returncode}" if r.returncode else ""


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


_AUTH_CACHE = {"t": 0.0, "v": None}


def _auth_var():
    # 60 sn önbellek: her panel açılışında sudo/python süreci başlatmayalım
    simdi = time.time()
    if _AUTH_CACHE["v"] is not None and simdi - _AUTH_CACHE["t"] < 60:
        return _AUTH_CACHE["v"]
    sonuc = _auth_var_hesapla()
    _AUTH_CACHE["v"], _AUTH_CACHE["t"] = sonuc, simdi
    return sonuc


def _auth_var_hesapla():
    for p in _auth_dosyalari():
        try:
            if os.path.exists(p):
                return True
        except OSError:
            continue
    if ortak.SUNUCU:  # /veri/ev-ajan 0700: ofis okuyamaz; izinli yardımcıyla (sudo) sor
        try:
            sonuc = auth_islem({"islem": "liste"})
            return bool(sonuc.get("saglayicilar"))
        except ValueError:
            return False
    return False


def durum(env_yolu=None):
    yol = shutil.which("opencode") or (exe() if exe() != "opencode" else None)
    if not yol:
        return {"tur": "yok", "surum": None, "auth": False, "model": test_modeli(env_yolu)}
    try:
        r = subprocess.run(_komut([yol, "--version"]), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, env=_ortam())
        surum = (r.stdout or "").strip().splitlines()[0][:40] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        surum = None
    return {"tur": "kurulu", "surum": surum, "auth": _auth_var(), "model": test_modeli(env_yolu)}


MODEL_DESENI = re.compile(r"^[a-z0-9][a-z0-9_-]*/[A-Za-z0-9._:-]+$")
_YAP_CACHE = {"t": 0.0, "v": None}


def yapilandirma(tazele=False):
    """opencode.json'daki tanımlı sağlayıcı/modeller (anahtarlar dönmez). 60 sn önbellekli."""
    simdi = time.time()
    if not tazele and _YAP_CACHE["v"] is not None and simdi - _YAP_CACHE["t"] < 60:
        return _YAP_CACHE["v"]
    try:
        sonuc = auth_islem({"islem": "yapilandirma"})
    except ValueError:
        sonuc = {"saglayicilar": [], "modeller": []}
    _YAP_CACHE["v"], _YAP_CACHE["t"] = sonuc, simdi
    return sonuc


def _modeller_getir():
    """`opencode models` + opencode.json tanımlı modelleri birleştirir."""
    listeler, hatalar = [], []
    try:
        r = subprocess.run(_komut([exe(), "models"]), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90, env=_ortam())
        if r.returncode == 0:
            listeler.append([s.strip() for s in (r.stdout or "").splitlines() if MODEL_DESENI.match(s.strip())])
        else:
            hatalar.append(_kisa_hata(r) or f"çıkış kodu {r.returncode}")
    except (OSError, subprocess.TimeoutExpired) as e:
        hatalar.append(f"{type(e).__name__}")
    cfg = yapilandirma(tazele=True)
    listeler.append([m for m in (cfg.get("modeller") or []) if MODEL_DESENI.match(m)])
    liste = list(dict.fromkeys([m for l in listeler for m in l]))
    if not liste:
        raise ValueError("Hiç model bulunamadı. opencode.json'da tanımlı sağlayıcı/model yok"
                         + (f" ve `opencode models` başarısız: {hatalar[0]}" if hatalar else "") + ".")
    return liste[:500]


def saglayici_listesi():
    """Kimlik doğrulaması yapılmış ya da yapılandırmada tanımlı sağlayıcılar: [{id, ad}]."""
    adlar = {x.get("id"): x.get("ad") for x in (yapilandirma().get("saglayicilar") or []) if x.get("id")}
    provs = {m.split("/", 1)[0] for m in (model_ozeti().get("modeller") or []) if "/" in m}
    provs |= set(adlar)
    try:
        provs |= {x.get("id") for x in (auth_islem({"islem": "liste"}).get("saglayicilar") or []) if x.get("id")}
    except ValueError:
        pass
    return [{"id": p, "ad": adlar.get(p)} for p in sorted(x for x in provs if x)]


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
                           timeout=150, cwd=calisma_dizini(), env=_ortam())
    except subprocess.TimeoutExpired:
        raise ValueError("Opencode 150 saniyede cevap vermedi.") from None
    except OSError as e:
        raise ValueError(f"opencode başlatılamadı: {type(e).__name__}: {e}") from None
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
        detay = _kisa_hata(r)
        raise ValueError("Opencode bağlantısı çalışmadı" + (f": {detay}" if detay else "; `opencode auth login` ile giriş yap."))
    return {"tamam": True, "yanit": metin.strip()[:80], "model": model}


def teshis():
    """Sunucuda opencode kurulumu/izinleri için ayrıntılı tanılama (sır içermez)."""
    yol = shutil.which("opencode")
    bilgi = {"sunucu": ortak.SUNUCU, "yol": yol, "mevcut": bool(yol),
             "surum": None, "calistirma": None, "cwd": calisma_dizini(),
             "auth": None}
    if yol:
        try:
            bilgi["mevcut"] = os.path.isfile(yol)
            bilgi["calistirilabilir"] = os.access(yol, os.X_OK)
        except OSError:
            pass
        try:
            r = subprocess.run(_komut([yol, "--version"]), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30, env=_ortam())
            bilgi["surum"] = (r.stdout or "").strip().splitlines()[0][:40] if r.returncode == 0 else None
            bilgi["calistirma"] = {"kod": r.returncode, "hata": _kisa_hata(r) if r.returncode else ""}
        except subprocess.TimeoutExpired:
            bilgi["calistirma"] = {"kod": None, "hata": "zaman aşımı"}
        except OSError as e:
            bilgi["calistirma"] = {"kod": None, "hata": f"{type(e).__name__}: {e}"}
    try:
        l = auth_islem({"islem": "liste"})
        bilgi["auth"] = [x.get("id") for x in (l.get("saglayicilar") or [])]
    except ValueError as e:
        bilgi["auth"] = f"okunamadı: {e}"
    try:
        cfg = auth_islem({"islem": "yapilandirma"})
        bilgi["yapilandirma"] = cfg
    except ValueError as e:
        bilgi["yapilandirma"] = {"hata": str(e)}
    return bilgi


def _auth_helper_komut():
    """Kimlik deposunu yöneten yardımcı betiği çalıştıracak komut (sunucuda sudo ile ajan)."""
    if ortak.SUNUCU:
        # HOME korunur: auth.json ve opencode.json ajanın ev dizininde olsun.
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


def eksik_anahtarlar(liste):
    """Model listesinde geçen ama ne auth.json'da ne config'de anahtarı olan sağlayıcılar."""
    provs = {str(m).split("/", 1)[0] for m in (liste or []) if "/" in str(m)} - {"opencode"}
    if not provs:
        return []
    cfg = yapilandirma()
    cfg_anahtar = {x.get("id") for x in (cfg.get("saglayicilar") or []) if x.get("anahtar")}
    try:
        auth_ids = {x.get("id") for x in (auth_islem({"islem": "liste"}).get("saglayicilar") or [])}
    except ValueError:
        auth_ids = set()
    return sorted(p for p in provs if p not in cfg_anahtar and p not in auth_ids)


def islem(veri, env_yolu=None):
    i = veri.get("islem")
    if i == "dene":
        return {**durum(env_yolu), "deneme": baglanti_dene(env_yolu)}
    if i == "modeller":
        m = modeller(tazele=bool(veri.get("tazele")))
        return {**durum(env_yolu), **m, "saglayici_listesi": saglayici_listesi(),
                "eksik_anahtar": eksik_anahtarlar(m.get("modeller"))}
    if i == "auth-liste":
        return auth_islem({"islem": "liste"})
    if i == "auth-ekle":
        auth_islem({"islem": "ekle", "saglayici": veri.get("saglayici"), "anahtar": veri.get("anahtar")})
        return {"tamam": True, **auth_islem({"islem": "liste"})}
    if i == "auth-sil":
        auth_islem({"islem": "sil", "saglayici": veri.get("saglayici")})
        return {"tamam": True, **auth_islem({"islem": "liste"})}
    if i == "teshis":
        return teshis()
    if i == "config-yaz":
        metin = veri.get("metin")
        if not isinstance(metin, str):
            raise ValueError("Yapılandırma metni gerekli.")
        sonuc = auth_islem({"islem": "config-yaz", "metin": metin})
        _YAP_CACHE["v"] = None  # önbelleği geçersiz kıl
        return {**sonuc, **yapilandirma(tazele=True)}
    raise ValueError("bilinmeyen işlem")
