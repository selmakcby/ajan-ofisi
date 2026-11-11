"""Ajan başına günlük token sayacı. Yalnız gerçek usage alanları; maliyet hesabı yok.

Kalıcı dosya: durum/token-<YYYY-MM-DD>.json
  {"<ajan>": {"ofis": {4 alan}, "terminal": {4 alan}},          ← toplam görünüm (türetilir)
   "_kosular": {"<kosu_id>": {"ajan": .., "usage": {4 alan}}},   ← ofis koşusu başına (değiştirilerek yazılır)
   "_oturumlar": {"<session_id>": {"ajan": .., "usage": {..}}}}   ← terminal oturumu başına (değiştirilerek yazılır)
Kayıtlar "ekle" değil "yerine koy" ile yazılır: aynı koşu/oturum yeniden sayılırsa çift sayılmaz.
Süreçler arası (sunucu + kosucu) dosya kilidiyle korunur (ortak.dosya_kilidi).
"""
import json
import os
from contextlib import contextmanager
from datetime import datetime

import ortak

ALANLAR = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
KILIT = os.path.join(ortak.DURUM_DIZINI, "token.lock")


def bos():
    return {k: 0 for k in ALANLAR}


def usage_al(u):
    """Ham usage sözlüğünden yalnız 4 sayısal alan."""
    u = u if isinstance(u, dict) else {}
    return {k: int(u.get(k) or 0) if isinstance(u.get(k), (int, float)) else 0 for k in ALANLAR}


def topla(*usagelar):
    t = bos()
    for u in usagelar:
        for k in ALANLAR:
            t[k] += int((u or {}).get(k) or 0)
    return t


class MesajTekil:
    """message.id ile tekilleştirir. Aynı id'li satırlar tekrar ederse yalnız artan fark sayılır."""

    def __init__(self):
        self.gorulen = {}
        self.toplam = bos()

    def isle(self, mesaj_id, usage):
        u = usage_al(usage)
        onceki = self.gorulen.get(mesaj_id, bos()) if mesaj_id else bos()
        yeni = {k: max(u[k], onceki[k]) for k in ALANLAR}
        fark = {k: yeni[k] - onceki[k] for k in ALANLAR}
        if mesaj_id:
            self.gorulen[mesaj_id] = yeni
        if not any(fark.values()):
            return False
        self.toplam = topla(self.toplam, fark)
        return True


def yol(tarih):
    return os.path.join(ortak.DURUM_DIZINI, f"token-{tarih}.json")


def _oku(tarih):
    try:
        with open(yol(tarih), encoding="utf-8") as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


@contextmanager
def _kilitli():
    os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
    with open(KILIT, "a") as k:
        with ortak.dosya_kilidi(k):  # Windows: msvcrt, Linux/macOS: fcntl
            yield


def _ozet_kur(veri):
    """_kosular + _oturumlar → {ajan: {ofis, terminal}} görünümü."""
    ajanlar = {}
    for kaynak, anahtar in (("ofis", "_kosular"), ("terminal", "_oturumlar")):
        for kayit in (veri.get(anahtar) or {}).values():
            ajan = kayit.get("ajan")
            if not ajan:
                continue
            a = ajanlar.setdefault(ajan, {"ofis": bos(), "terminal": bos()})
            a[kaynak] = topla(a[kaynak], kayit.get("usage"))
    return ajanlar


def _yaz(tarih, veri):
    temiz = {"_kosular": veri.get("_kosular") or {}, "_oturumlar": veri.get("_oturumlar") or {}}
    tam = {**_ozet_kur(temiz), **temiz}
    gecici = yol(tarih) + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(tam, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol(tarih))
    return tam


def kayit_koy(tarih, tur, anahtar, ajan, usage):
    """tur: '_kosular' | '_oturumlar'. Kaydı yerine koyar; ajanın o günkü {ofis, terminal} değerini döndürür."""
    with _kilitli():
        veri = _oku(tarih)
        bolum = dict(veri.get(tur) or {})
        bolum[anahtar] = {"ajan": ajan, "usage": usage_al(usage)}
        tam = _yaz(tarih, {**veri, tur: bolum})
    return tam.get(ajan, {"ofis": bos(), "terminal": bos()})


def kosu_eksikse_koy(tarih, kosu_id, ajan, usage):
    """Geçmiş koşuyu (olaylar.jsonl'den) yalnız dosyada yoksa ekler."""
    with _kilitli():
        veri = _oku(tarih)
        if kosu_id in (veri.get("_kosular") or {}):
            return False
        bolum = {**(veri.get("_kosular") or {}), kosu_id: {"ajan": ajan, "usage": usage_al(usage)}}
        _yaz(tarih, {**veri, "_kosular": bolum})
    return True


def gun_ozeti(tarih):
    veri = _oku(tarih)
    return _ozet_kur(veri)


def ajan_gun(tarih, ajan):
    return gun_ozeti(tarih).get(ajan, {"ofis": bos(), "terminal": bos()})


def disari(ajan_kaydi):
    """{ofis, terminal} → API biçimi."""
    o, t = ajan_kaydi.get("ofis") or bos(), ajan_kaydi.get("terminal") or bos()
    h = topla(o, t)
    return {"toplam": sum(h.values()), "girdi": h["input_tokens"], "cikti": h["output_tokens"],
            "onbellek_yazma": h["cache_creation_input_tokens"], "onbellek_okuma": h["cache_read_input_tokens"],
            "ofis_toplam": sum(o.values()), "terminal_toplam": sum(t.values())}


def api_yaniti():
    tarih = ortak.bugun()
    ajanlar = {a: disari(k) for a, k in gun_ozeti(tarih).items()}
    return {"tarih": tarih, "ajanlar": ajanlar, "genel_toplam": sum(a["toplam"] for a in ajanlar.values())}


def yerel_tarih(iso_zaman):
    """Transkript timestamp'i (UTC, 'Z') → yerel YYYY-MM-DD; çözülemezse None."""
    try:
        return datetime.fromisoformat(str(iso_zaman).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def olaylardan_geri_kur(olaylar):
    """Bugünkü kosu_bitti/ceo_bitti olaylarının usage'ını dosyada eksikse ekler (özellik öncesi koşular)."""
    tarih = ortak.bugun()
    for o in olaylar:
        if o.get("tur") not in ("kosu_bitti", "ceo_bitti") or not str(o.get("zaman", "")).startswith(tarih):
            continue
        if o.get("kosu_id") and o.get("ajan") and o.get("kullanim"):
            kosu_eksikse_koy(tarih, o["kosu_id"], o["ajan"], o["kullanim"])
