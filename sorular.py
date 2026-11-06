"""Telegram köprüsünün kalıcı durumu: sorular, CEO kararları, Telegram mesaj eşlemesi, devam kuyruğu, rapor.

Hepsi durum/ altında (gitignore). Yollar her çağrıda ortak.DURUM_DIZINI'nden kurulur (testler bunu değiştirir).
Yalnız sunucu süreci yazar (HTTP + izleyici + bot iş parçacıkları); süreç içi tek kilit yeter.
"""
import json
import os
import threading

import ortak

KILIT = threading.RLock()
MAKS_MESAJ = 500
MADDE_MAKS = 300
_derlenen_satir = None  # rapor_derle'nin gördüğü karar sayısı; rapor_isaretle bunu işaretler


def _yol(ad):
    return os.path.join(ortak.DURUM_DIZINI, ad)


def _oku(ad, varsayilan):
    # Kilit altında: Windows'ta başka iş parçacığı dosyayı açıkken os.replace PermissionError verir.
    with KILIT:
        try:
            with open(_yol(ad), encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return varsayilan


def _yaz(ad, veri):
    os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
    gecici = _yol(ad) + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, _yol(ad))


# ---------- sorular + otomatik cevap sayacı ----------

def _sorular():
    v = _oku("sorular.json", {})
    return {"sorular": v.get("sorular") or {}, "otomatik": v.get("otomatik") or {}}


def soru_ekle(ajan, kosu_id, session_id, soru, tur):
    with KILIT:
        v = _sorular()
        v["sorular"][kosu_id] = {"ajan": ajan, "kosu_id": kosu_id, "session_id": session_id, "soru": soru,
                                 "tur": tur, "durum": "yeni", "zaman": ortak.simdi_iso()}
        _yaz("sorular.json", v)
    return kosu_id


def soru_al(soru_id):
    s = _sorular()["sorular"].get(soru_id)
    return {**s, "soru_id": soru_id} if s else None


def soru_guncelle(soru_id, **alanlar):
    with KILIT:
        v = _sorular()
        if soru_id in v["sorular"]:
            v["sorular"][soru_id].update(alanlar)
            _yaz("sorular.json", v)


def bekleyen_sorular():
    return [{**s, "soru_id": i} for i, s in _sorular()["sorular"].items() if s.get("durum") == "kullanicida"]


def otomatik_sayi(session_id):
    return int(_sorular()["otomatik"].get(session_id or "", 0))


def otomatik_artir(session_id):
    with KILIT:
        v = _sorular()
        n = int(v["otomatik"].get(session_id, 0)) + 1
        v["otomatik"][session_id] = n
        _yaz("sorular.json", v)
    return n


def otomatik_sifirla(session_id):
    with KILIT:
        v = _sorular()
        if v["otomatik"].pop(session_id, None) is not None:
            _yaz("sorular.json", v)


# ---------- CEO kararları ve gün sonu raporu ----------

def karar_ekle(kayit):
    with KILIT:
        os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
        with open(_yol("kararlar.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"zaman": ortak.simdi_iso(), **kayit}, ensure_ascii=False) + "\n")


def _kararlar():
    try:
        with open(_yol("kararlar.jsonl"), encoding="utf-8") as f:
            satirlar = f.read().splitlines()
    except FileNotFoundError:
        return []
    sonuc = []
    for s in satirlar:
        try:
            sonuc.append(json.loads(s))
        except json.JSONDecodeError:
            sonuc.append(None)  # bozuk satır sayımı kaydırmasın
    return sonuc


def son_kararlar():
    """Son rapordan bu yana verilen kararlar (en eskisi önce)."""
    kararlar = _kararlar()
    return [k for k in kararlar[int(_oku("rapor-son.json", {}).get("satir") or 0):] if k]


def rapor_derle():
    """(metin|None, maddeler): son rapordan beri CEO kararları; karar yoksa (None, [])."""
    global _derlenen_satir
    with KILIT:
        _derlenen_satir = len(_kararlar())
        kararlar = son_kararlar()
    if not kararlar:
        return None, []
    satirlar = []
    for i, k in enumerate(kararlar, 1):
        madde = f"{i}. {k.get('ajan')}: {k.get('soru')} → {k.get('cevap')} ({k.get('gerekce')})"
        satirlar.append(madde if len(madde) <= MADDE_MAKS else madde[:MADDE_MAKS - 1] + "…")
    maddeler = [{"ajan": k.get("ajan"), "session_id": k.get("session_id"), "kosu_id": k.get("kosu_id")}
                for k in kararlar]
    return "\n".join(satirlar), maddeler


def rapor_isaretle(zaman_iso):
    """Raporu gönderildi say: rapor_derle'nin gördüğü kararlar bir daha rapora girmez."""
    global _derlenen_satir
    with KILIT:
        satir = _derlenen_satir if _derlenen_satir is not None else len(_kararlar())
        _yaz("rapor-son.json", {"zaman": zaman_iso, "satir": satir})
        _derlenen_satir = None


def son_rapor_zamani():
    return _oku("rapor-son.json", {}).get("zaman")


# ---------- Telegram mesajı → hedef eşlemesi ----------

def mesaj_esle(mesaj_id, hedef):
    with KILIT:
        v = _oku("telegram-mesajlar.json", {})
        v[str(mesaj_id)] = hedef
        if len(v) > MAKS_MESAJ:
            v = dict(list(v.items())[-MAKS_MESAJ:])  # ekleme sırası korunur; en eskiler düşer
        _yaz("telegram-mesajlar.json", v)


def mesaj_hedefi(mesaj_id):
    return _oku("telegram-mesajlar.json", {}).get(str(mesaj_id))


# ---------- meşgul ajan için devam kuyruğu ----------

def devam_birak(ajan, istek):
    """Ajan başına tek bekleyen devam; yenisi eskisini ezer."""
    with KILIT:
        v = _oku("devam-kuyrugu.json", {})
        v[ajan] = istek
        _yaz("devam-kuyrugu.json", v)


def devam_kuyrugu():
    """Bekleyen devamı olan ajanlar."""
    return list(_oku("devam-kuyrugu.json", {}))


def devam_al(ajan):
    with KILIT:
        v = _oku("devam-kuyrugu.json", {})
        istek = v.pop(ajan, None)
        if istek is not None:
            _yaz("devam-kuyrugu.json", v)
    return istek
