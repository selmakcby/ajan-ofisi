"""Proje takip verisi: kullanıcı ekler, CEO görevlere böler ve ilerletir, kullanıcı kapatır.

Dosya gizli dizinde (sunucuda ajan kullanıcısı okuyamaz; yerelde izin kuralıyla yasak). Yalnız sunucu süreci yazar.
Hatalar kullanıcıya gösterilecek Türkçe ValueError'dır.
"""
import json
import os
import re
import secrets
import threading
from datetime import date

import ortak

KILIT = threading.RLock()
ONCELIKLER = ("dusuk", "orta", "yuksek")
GOREV_DURUMLARI = ("bekliyor", "yapiliyor", "bitti", "iptal")
MAKS_ACIK, MAKS_GOREV, MAKS_NOT, MAKS_KAPALI = 20, 30, 50, 100
BASLIK, ACIKLAMA, GOREV_BASLIK, NOT_MAKS = 120, 4000, 200, 1000
EVET = {"evet", "tamam", "onaylıyorum", "onayliyorum", "bitti"}


def _yol():
    return os.path.join(ortak.gizli_dizin(), "projeler.json")


def _oku():
    with KILIT:
        try:
            with open(_yol(), encoding="utf-8") as f:
                return json.load(f).get("projeler") or []
        except (FileNotFoundError, json.JSONDecodeError, AttributeError):
            return []


def _yaz(liste):
    os.makedirs(ortak.gizli_dizin(), exist_ok=True)
    ortak.atomik_yaz(_yol(), json.dumps({"projeler": liste}, ensure_ascii=False, indent=1))


def liste():
    return _oku()


def al(proje_id):
    return next((p for p in _oku() if p.get("id") == proje_id), None)


def acik_projeler():
    return [p for p in _oku() if p.get("durum") == "acik"]


def onay_bekleyenler():
    return [p for p in _oku() if p.get("durum") == "onay_bekliyor"]


def _metin(deger, ad, sinir, zorunlu=False):
    if deger is None:
        deger = ""
    if not isinstance(deger, str):
        raise ValueError(f"{ad} metin olmalı.")
    deger = deger.strip()
    if zorunlu and not deger:
        raise ValueError(f"{ad} boş olamaz.")
    if len(deger) > sinir:
        raise ValueError(f"{ad} en fazla {sinir} karakter olabilir.")
    return deger


def _alanlar(baslik=None, aciklama=None, oncelik=None, hedef_tarih=None, kismi=False):
    a = {}
    if not kismi or baslik is not None:
        a["baslik"] = _metin(baslik, "Başlık", BASLIK, zorunlu=True)
    if not kismi or aciklama is not None:
        a["aciklama"] = _metin(aciklama, "Açıklama", ACIKLAMA)
    if not kismi or oncelik is not None:
        if (oncelik or "orta") not in ONCELIKLER:
            raise ValueError("Öncelik düşük, orta ya da yüksek olmalı.")
        a["oncelik"] = oncelik or "orta"
    if not kismi or hedef_tarih is not None:
        if hedef_tarih:
            try:
                date.fromisoformat(str(hedef_tarih))
            except ValueError:
                raise ValueError("Hedef tarih YYYY-AA-GG biçiminde geçerli bir tarih olmalı.") from None
        a["hedef_tarih"] = hedef_tarih or None
    return a


def _degistir(proje_id, islev):
    """Projeyi kilit altında bulur, islev(p) ile değiştirir, kaydeder; p'yi döndürür."""
    with KILIT:
        lst = _oku()
        p = next((x for x in lst if x.get("id") == proje_id), None)
        if not p:
            raise ValueError("Böyle bir proje yok.")
        sonuc = islev(p)
        _yaz(lst)
        return p if sonuc is None else sonuc


def ekle(baslik, aciklama="", oncelik="orta", hedef_tarih=None):
    a = _alanlar(baslik, aciklama, oncelik, hedef_tarih)
    with KILIT:
        lst = _oku()
        if sum(p.get("durum") != "kapali" for p in lst) >= MAKS_ACIK:
            raise ValueError(f"En fazla {MAKS_ACIK} açık proje olabilir; önce birini kapat.")
        p = {"id": f"p-{secrets.token_hex(3)}", **a, "durum": "acik", "ilerleme": 0, "gorevler": [], "notlar": [],
             "olusturma": ortak.simdi_iso(), "kapanis": None}
        lst.append(p)
        _yaz(lst)
        return p


def guncelle(proje_id, baslik=None, aciklama=None, oncelik=None, hedef_tarih=None):
    a = _alanlar(baslik, aciklama, oncelik, hedef_tarih, kismi=True)
    return _degistir(proje_id, lambda p: p.update(a))


def _not(p, metin, kaynak):
    if kaynak not in ("kullanici", "ceo"):
        raise ValueError("geçersiz not kaynağı")
    p["notlar"] = (p.get("notlar") or []) + [{"zaman": ortak.simdi_iso(), "kaynak": kaynak,
                                              "metin": _metin(metin, "Not", NOT_MAKS, zorunlu=True)}]
    p["notlar"] = p["notlar"][-MAKS_NOT:]


def not_ekle(proje_id, metin, kaynak):
    _degistir(proje_id, lambda p: _not(p, metin, kaynak))


def _kapali_budanir(lst):
    kapali = [p for p in lst if p.get("durum") == "kapali"]
    for p in kapali[:max(0, len(kapali) - MAKS_KAPALI)]:
        lst.remove(p)


def _gecis(proje_id, onceki, sonraki, ek=None):
    with KILIT:
        lst = _oku()
        p = next((x for x in lst if x.get("id") == proje_id), None)
        if not p:
            raise ValueError("Böyle bir proje yok.")
        if p.get("durum") not in onceki:
            raise ValueError("Proje bu durumda değil.")
        p["durum"] = sonraki
        if ek:
            ek(p)
        if sonraki == "kapali":
            p["kapanis"] = ortak.simdi_iso()
            _kapali_budanir(lst)
        _yaz(lst)
        return p


def kapat(proje_id):
    return _gecis(proje_id, ("acik", "onay_bekliyor"), "kapali")


def onay_iste(proje_id, neden):
    return _gecis(proje_id, ("acik",), "onay_bekliyor",
                  lambda p: _not(p, "Bitti mi? " + (str(neden or "")[:300] or "CEO bittiğini düşünüyor."), "ceo"))


def onayla(proje_id):
    return _gecis(proje_id, ("onay_bekliyor",), "kapali")


def reddet(proje_id, metin):
    return _gecis(proje_id, ("onay_bekliyor",), "acik", lambda p: _not(p, metin or "Henüz bitmedi.", "kullanici"))


def gorev_yaz(proje_id, gorev_id, baslik, ajan, durum):
    """Görev ekler (gorev_id None) ya da günceller. Sınır doluysa ya da görev yoksa None."""
    if durum not in GOREV_DURUMLARI:
        raise ValueError("geçersiz görev durumu")
    baslik = _metin(baslik, "Görev başlığı", 10 ** 6, zorunlu=True)[:GOREV_BASLIK]

    def yaz(p):
        gorevler = p.setdefault("gorevler", [])
        if gorev_id is None:
            if len(gorevler) >= MAKS_GOREV:
                return False
            g = {"id": f"g-{secrets.token_hex(2)}", "baslik": baslik, "ajan": ajan, "durum": durum}
            gorevler.append(g)
            return g["id"]
        g = next((x for x in gorevler if x.get("id") == gorev_id), None)
        if not g:
            return False
        g.update(baslik=baslik, ajan=ajan, durum=durum)
        return g["id"]

    sonuc = _degistir(proje_id, yaz)
    return sonuc or None


def ilerleme_yaz(proje_id, yuzde):
    _degistir(proje_id, lambda p: p.update(ilerleme=max(0, min(100, int(yuzde)))))


def kullanici_metni(proje):
    """Kullanıcının bu projede yazdığı metin (tetik kelimesi yalnız buna karşı aranır)."""
    notlar = [n.get("metin", "") for n in proje.get("notlar") or [] if n.get("kaynak") == "kullanici"]
    return "\n".join([proje.get("baslik", ""), proje.get("aciklama", ""), *notlar])


def evet_mi(metin):
    kelimeler = re.sub(r"[^\w]+", " ", str(metin or "").lower()).split()
    return bool(kelimeler) and all(k in EVET for k in kelimeler)
