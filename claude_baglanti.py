"""Claude bağlantısı: API anahtarı ya da abonelik token'ı (claude setup-token). Yalnız stdlib.

Ayar .env'de (sunucuda gizli dizinde): OFIS_CLAUDE_API_KEY ya da OFIS_CLAUDE_TOKEN — biri yazılınca diğeri silinir.
claude süreçlerine ortak.alt_surec_ortami() ile ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN olarak verilir.
Anahtar tarayıcıya, loga ya da hata mesajına yazılmaz; panel yalnız son 4 karakteri görür.
"""
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request

import ortak

API_DESENI = re.compile(r"^sk-ant-(?!oat)[A-Za-z0-9_-]{20,}$")
TOKEN_DESENI = re.compile(r"^sk-ant-oat[A-Za-z0-9_-]{20,}$")
ANAHTARLAR = ("OFIS_CLAUDE_API_KEY", "OFIS_CLAUDE_TOKEN")


def durum(env_yolu=None):
    env = ortak.env_oku(env_yolu)
    api, token = env.get("OFIS_CLAUDE_API_KEY", ""), env.get("OFIS_CLAUDE_TOKEN", "")
    tur = "api" if api else "abonelik" if token else ("yok" if ortak.SUNUCU else "yerel")
    return {"tur": tur, "son4": (api or token)[-4:] or None, "sunucu":ortak.SUNUCU}


def api_dogrula(anahtar, ac=urllib.request.urlopen):
    """Ücretsiz doğrulama: model listesi. Geçersiz/ulaşılamaz → ValueError (mesajda anahtar yok)."""
    istek = urllib.request.Request("https://api.anthropic.com/v1/models?limit=1",
                                   headers={"x-api-key": anahtar, "anthropic-version": "2023-06-01"})
    try:
        with ac(istek, timeout=15) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise ValueError("Anahtar geçersiz ya da yetkisiz." if e.code in (401, 403)
                         else f"Anthropic doğrulaması başarısız (HTTP {e.code}).") from None
    except (urllib.error.URLError, OSError):
        raise ValueError("Anthropic'e ulaşılamadı; sunucunun internet bağlantısını kontrol et.") from None


def baglanti_dene(env_yolu=None):
    """Çok kısa bir claude çağrısı (birkaç token): abonelik token'ı ancak böyle denenebilir."""
    claude = shutil.which("claude")
    if not claude:
        raise ValueError("claude komutu bulunamadı.")
    komut = [claude, "-p", "--model", "haiku", "--no-session-persistence", "--tools", "", "--output-format", "json"]
    try:
        r = subprocess.run(komut, input="Yalnız OK yaz.", capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60, cwd=ortak.VERI, env=ortak.alt_surec_ortami(env_yolu))
        sonuc = json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        raise ValueError("Claude 60 saniyede cevap vermedi.") from None
    except OSError:
        raise ValueError("claude çalıştırılamadı (kurulum/izin sorunu).") from None
    except ValueError:
        raise ValueError("Claude bağlantısı çalışmadı; anahtarı/token'ı kontrol et.") from None
    if sonuc.get("is_error"):
        raise ValueError("Claude bağlantısı çalışmadı: " + str(sonuc.get("result") or "")[:160])
    return {"tamam": True, "yanit": str(sonuc.get("result") or "")[:80], "maliyet_usd": sonuc.get("total_cost_usd")}


def islem(veri, env_yolu=None, dogrulayici=api_dogrula, deneyici=baglanti_dene):
    i = veri.get("islem")
    if i == "anahtar":
        anahtar = str(veri.get("anahtar") or "").strip()
        if not API_DESENI.match(anahtar):
            raise ValueError("Bu bir Claude API anahtarına benzemiyor (sk-ant-… ile başlar).")
        dogrulayici(anahtar)
        ortak.env_yaz({"OFIS_CLAUDE_API_KEY": anahtar, "OFIS_CLAUDE_TOKEN": None}, env_yolu)
    elif i == "token":
        token = str(veri.get("token") or "").strip()
        if not TOKEN_DESENI.match(token):
            raise ValueError("Bu bir abonelik token'ına benzemiyor. Kendi bilgisayarında `claude setup-token` çalıştır; "
                             "verdiği sk-ant-oat… metnini yapıştır.")
        ortak.env_yaz({"OFIS_CLAUDE_TOKEN": token, "OFIS_CLAUDE_API_KEY": None}, env_yolu)
    elif i == "dene":
        return {**durum(env_yolu), "deneme": deneyici(env_yolu)}
    elif i == "kaldir":
        ortak.env_yaz(dict.fromkeys(ANAHTARLAR), env_yolu)
    else:
        raise ValueError("bilinmeyen işlem")
    return durum(env_yolu)
