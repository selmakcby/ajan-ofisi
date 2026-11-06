"""Ofis sahibinin hesabı: şifre özeti, oturumlar, kaba kuvvet beklemesi. Yalnız stdlib.

- Şifre düz metin saklanmaz: hashlib.scrypt (n=2^14, r=8, p=1, 32 bayt, 16 bayt tuz); karşılaştırma sabit zamanlı.
- Oturum token'ı yalnız tarayıcının HttpOnly çerezinde durur; sunucu yalnız sha256 özetini saklar.
- Dosyalar durum/ altında (gitignore), izin 0600. Yollar her çağrıda ortak.DURUM_DIZINI'nden kurulur.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time

import ortak

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}
OTURUM_SN = 30 * 86400
KULLANICI_DESENI = re.compile(r"^[\w.-]{3,40}$")
MIN_SIFRE = 8
SERBEST_HATA = 5
MAKS_BEKLEME = 300

KILIT = threading.Lock()
_hata = {"sayi": 0, "son": 0.0}  # ponytail: bellek içi; sunucu yeniden başlarsa sıfırlanır


def _yol(ad):
    return os.path.join(ortak.DURUM_DIZINI, ad)


def _oku(ad, varsayilan):
    try:
        with open(_yol(ad), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return varsayilan


def _yaz(ad, veri):
    os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
    gecici = _yol(ad) + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f)
    os.chmod(gecici, ortak.ENV_IZIN)
    os.replace(gecici, _yol(ad))


def _ozet(sifre, tuz):
    return hashlib.scrypt(sifre.encode("utf-8"), salt=tuz, **SCRYPT).hex()


def _sifre_kontrol(sifre):
    if not isinstance(sifre, str) or len(sifre) < MIN_SIFRE:
        raise ValueError(f"Şifre en az {MIN_SIFRE} karakter olmalı.")


# ---------- hesap ----------

def hesap_var():
    return bool(_oku("hesap.json", {}).get("kullanici_adi"))


def kullanici_adi():
    return _oku("hesap.json", {}).get("kullanici_adi")


def hesap_olustur(kullanici_adi, sifre):
    if not isinstance(kullanici_adi, str) or not KULLANICI_DESENI.match(kullanici_adi):
        raise ValueError("Kullanıcı adı 3-40 karakter olmalı; harf, rakam, nokta, _ ve - kullanılabilir.")
    _sifre_kontrol(sifre)
    with KILIT:
        if hesap_var():
            raise ValueError("Hesap zaten var.")
        tuz = secrets.token_bytes(16)
        _yaz("hesap.json", {"kullanici_adi": kullanici_adi, "tuz": tuz.hex(), "sifre_ozeti": _ozet(sifre, tuz),
                            "parametreler": SCRYPT, "olusturma": ortak.simdi_iso()})


def dogrula(ad, sifre):
    h = _oku("hesap.json", {})
    if not h.get("kullanici_adi") or not isinstance(sifre, str):
        return False
    ozet = _ozet(sifre, bytes.fromhex(h["tuz"]))  # ad yanlış olsa da hesapla: zamanlama ad sızdırmasın
    return hmac.compare_digest(ozet, h["sifre_ozeti"]) and hmac.compare_digest(str(ad), h["kullanici_adi"])


def sifre_sifirla(yeni):
    _sifre_kontrol(yeni)
    with KILIT:
        h = _oku("hesap.json", {})
        if not h.get("kullanici_adi"):
            raise ValueError("Henüz hesap yok; önce arayüzden kurulum yap.")
        tuz = secrets.token_bytes(16)
        h.update(tuz=tuz.hex(), sifre_ozeti=_ozet(yeni, tuz), parametreler=SCRYPT)
        _yaz("hesap.json", h)
        _yaz("oturumlar.json", {})  # tüm oturumlar düşer


# ---------- oturumlar ----------

def _token_ozeti(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def oturum_ac():
    token = secrets.token_urlsafe(32)
    with KILIT:
        simdi = time.time()
        v = {k: t for k, t in _oku("oturumlar.json", {}).items() if t > simdi}  # süresi dolanlar temizlenir
        v[_token_ozeti(token)] = simdi + OTURUM_SN
        _yaz("oturumlar.json", v)
    return token


def oturum_gecerli(token):
    if not isinstance(token, str) or not token:
        return False
    bitis = _oku("oturumlar.json", {}).get(_token_ozeti(token))
    return isinstance(bitis, (int, float)) and bitis > time.time()


def oturum_kapat(token):
    if not isinstance(token, str) or not token:
        return
    with KILIT:
        v = _oku("oturumlar.json", {})
        if v.pop(_token_ozeti(token), None) is not None:
            _yaz("oturumlar.json", v)


# ---------- kaba kuvvet ----------

def giris_bekleme():
    """Kalan bekleme (sn). İlk SERBEST_HATA hata beklemesiz; sonra 2, 4, 8 … en çok MAKS_BEKLEME."""
    fazla = _hata["sayi"] - SERBEST_HATA
    if fazla <= 0:
        return 0
    sure = min(2 ** fazla, MAKS_BEKLEME)
    return max(0, int(_hata["son"] + sure - time.time() + 0.999))


def giris_hatasi():
    _hata["sayi"] += 1
    _hata["son"] = time.time()


def giris_basarili():
    _hata["sayi"], _hata["son"] = 0, 0.0
