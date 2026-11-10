#!/usr/bin/env python3
"""Opencode kimlik deposunu yönetir (yalnız bu iş için, sudo ile 'ajan' kullanıcısı olarak çalışır).

stdin'den tek satır JSON alır:
  {"islem":"liste"}                          → {"saglayicilar":[{"id":"..","tur":"api"}]}
  {"islem":"ekle","saglayici":"..","anahtar":".."} → {"tamam":true}
  {"islem":"sil","saglayici":".."}           → {"tamam":true}
Anahtar hiçbir zaman stdout'a yazılmaz. auth.json 0600 olarak atomik yazılır.
"""
import json
import os
import re
import sys
import tempfile

SAGLAYICI_DESENI = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
MAKS_ANAHTAR = 4096


def auth_yolu():
    return os.path.join(os.path.expanduser("~"), ".local", "share", "opencode", "auth.json")


def _oku():
    try:
        with open(auth_yolu(), encoding="utf-8") as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _yaz(veri):
    yol = auth_yolu()
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol), prefix=".auth-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=1)
        os.chmod(gecici, 0o600)
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            try:
                os.remove(gecici)
            except OSError:
                pass


def _saglayici(veri):
    s = veri.get("saglayici")
    if not isinstance(s, str) or not SAGLAYICI_DESENI.match(s.strip()):
        raise ValueError("Geçersiz sağlayıcı kimliği.")
    return s.strip()


def _config_yollari():
    home = os.path.expanduser("~")
    return [os.path.join(home, ".config", "opencode", "opencode.json"),
            os.path.join(home, ".config", "opencode", "opencode.jsonc")]


def _yapilandirma():
    """opencode.json'daki tanımlı sağlayıcı ve modelleri okur (anahtar/baseURL döndürülmez)."""
    yollar = _config_yollari()
    for yol in yollar:
        try:
            with open(yol, encoding="utf-8") as f:
                metin = f.read()
        except (FileNotFoundError, OSError):
            continue
        metin = __import__("re").sub(r"^\s*//.*$", "", metin, flags=__import__("re").M)  # jsonc yorumları
        try:
            veri = json.loads(metin)
        except json.JSONDecodeError:
            return {"saglayicilar": [], "modeller": [], "yol": yol, "var": True,
                    "hata": "JSON çözümlenemedi"}
        saglayicilar, modeller = [], []
        for sid, s in ((veri or {}).get("provider") or {}).items():
            if not isinstance(sid, str) or not SAGLAYICI_DESENI.match(sid):
                continue
            ad = s.get("name") if isinstance(s, dict) else None
            saglayicilar.append({"id": sid, "ad": ad if isinstance(ad, str) else None})
            for mid in ((s or {}).get("models") or {}):
                if isinstance(mid, str) and mid:
                    modeller.append(f"{sid}/{mid}")
        return {"saglayicilar": saglayicilar, "modeller": modeller, "yol": yol, "var": True}
    return {"saglayicilar": [], "modeller": [], "yol": yollar[0], "var": False}


MAKS_CONFIG = 200_000


def _config_yaz(metin):
    """Yönetici tarafından verilen opencode.json içeriğini ajanın ev dizinine atomik yazar."""
    if not isinstance(metin, str) or not metin.strip():
        raise ValueError("Yapılandırma boş.")
    if len(metin) > MAKS_CONFIG:
        raise ValueError("Yapılandırma çok büyük.")
    try:
        veri = json.loads(metin)
    except json.JSONDecodeError as e:
        raise ValueError(f"Geçersiz JSON: satır {e.lineno}, sütun {e.colno}")
    if not isinstance(veri, dict):
        raise ValueError("Yapılandırma bir JSON nesnesi olmalı.")
    if "provider" in veri and not isinstance(veri["provider"], dict):
        raise ValueError("'provider' bir nesne olmalı.")
    yol = _config_yollari()[0]
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    if os.path.exists(yol):
        try:
            with open(yol, "rb") as f:
                eski = f.read()
            with open(yol + ".bak", "wb") as f:
                f.write(eski)
        except OSError:
            pass
    fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol), prefix=".cfg-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        os.chmod(gecici, 0o644)
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            try:
                os.remove(gecici)
            except OSError:
                pass
    return {"tamam": True, "yol": yol}


def main():
    try:
        veri = json.loads(sys.stdin.read() or "{}")
        islem = veri.get("islem")
        if islem == "liste":
            sonuc = {"saglayicilar": [{"id": k, "tur": (v or {}).get("type") if isinstance(v, dict) else None}
                                      for k, v in _oku().items()]}
        elif islem == "yapilandirma":
            sonuc = _yapilandirma()
        elif islem == "config-yaz":
            sonuc = _config_yaz(veri.get("metin") if isinstance(veri.get("metin"), str) else veri.get("json"))
        elif islem == "ekle":
            s = _saglayici(veri)
            anahtar = veri.get("anahtar")
            if not isinstance(anahtar, str) or not anahtar.strip() or len(anahtar) > MAKS_ANAHTAR:
                raise ValueError("API anahtarı boş ya da çok uzun.")
            kayit = _oku()
            kayit[s] = {"type": "api", "key": anahtar.strip()}
            _yaz(kayit)
            sonuc = {"tamam": True, "saglayici": s}
        elif islem == "sil":
            s = _saglayici(veri)
            kayit = _oku()
            kayit.pop(s, None)
            _yaz(kayit)
            sonuc = {"tamam": True, "saglayici": s}
        else:
            raise ValueError("bilinmeyen işlem")
        sys.stdout.write(json.dumps(sonuc, ensure_ascii=False))
    except ValueError as e:
        sys.stdout.write(json.dumps({"hata": str(e)}, ensure_ascii=False))
        return 1
    except Exception as e:  # sır sızdırmadan genel hata
        sys.stdout.write(json.dumps({"hata": type(e).__name__}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
