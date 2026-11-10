"""Tarayıcıdan ajan ve oda yönetimi: ajanlar.json üzerinde doğrulanmış ekle / güncelle / sil, şablonlar.

Her değişiklik: oku → değiştir → doğrula → yedek (ajanlar.json.bak) → .tmp + os.replace. Hata → ValueError(Türkçe).
Sunucu dosyayı her istekte okuduğu için değişiklik yeniden başlatmadan geçerli olur.
"""
import json
import os
import re
import shutil
import threading

import ortak

YETKILER = {"okuma": ["Read", "Glob", "Grep"], "yazma": ["Write", "Edit"], "komut": ["Bash"],
            "web": ["WebSearch", "WebFetch"]}
MODELLER = ("sonnet", "haiku", "opus")
SAGLAYICILAR = ("claude", "opencode")
# Opencode model varyantı (sağlayıcıya özgü düşünme gücü); boş = varsayılan
VARIANTLAR = ("", "minimal", "low", "medium", "high", "max")
OPENCODE_MODEL_DESENI = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9._:-]+$")
TEMALAR = ("ceo", "yazi", "kod", "tasarim", "sosyal", "arastirma", "gun-sonu", "atolye", "bakim", "posta", "veri")
MAKS_AJAN = 60
MAKS_AD = 60
MAKS_ACIKLAMA = 500
MAKS_GOREV = 10
CALISMA = "calisma"
TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosucgiosuaiu")
KILIT = threading.RLock()


def id_turet(ad, mevcut):
    sade = re.sub(r"['’`]", "", str(ad).translate(TR).lower())  # "Şeyma'nın" → "seymanin"
    taban = re.sub(r"[^a-z0-9]+", "-", sade).strip("-")[:40].strip("-") or "ajan"
    aday, n = taban, 2
    while aday in mevcut:
        ek = f"-{n}"
        aday, n = taban[:40 - len(ek)] + ek, n + 1
    return aday


def oku():
    return ortak.ajanlari_yukle()[0]


# ---------- doğrulama ve yazma ----------

def _metin(deger, ad, maks, bos_olabilir=True):
    if not isinstance(deger, str) or len(deger) > maks or (not bos_olabilir and not deger.strip()):
        raise ValueError(f"{ad} {'boş olamaz ve ' if not bos_olabilir else ''}en fazla {maks} karakter olmalı.")
    return deger.strip()


def dogrula(veri):
    """Yalnız yükleyicinin (ortak.ajanlari_yukle) ve ön yüzün çalışması için gerekenler. Eski dosyalardaki
    tuhaflıklar (aynı id'li iki oda, uzun görev etiketi, tam model adı, cwd'siz ajan) reddedilmez; uzunluk ve
    seçenek sınırları yalnız formdan gelen alanlarda (_alanlari_uygula) uygulanır."""
    if not isinstance(veri, dict) or not isinstance(veri.get("ajanlar"), list):
        raise ValueError("Yapılandırmada 'ajanlar' listesi yok.")
    idler = set()
    for a in veri["ajanlar"]:
        if not isinstance(a, dict) or not isinstance(a.get("id"), str) or not ortak.AJAN_ID_DESENI.match(a["id"]):
            raise ValueError(f"Geçersiz ajan kimliği: {a.get('id') if isinstance(a, dict) else a!r}")
        if a["id"] in idler:
            raise ValueError(f"Aynı kimlikte iki ajan var: {a['id']}")
        idler.add(a["id"])
        if "ad" in a and (not isinstance(a["ad"], str) or not a["ad"].strip()):
            raise ValueError(f"Ajan adı boş olamaz: {a['id']}")
        oda = a.get("oda") or "genel"
        if not isinstance(oda, str) or not ortak.ODA_ID_DESENI.fullmatch(oda):
            raise ValueError(f"Geçersiz oda: {oda!r}")
        for g in a.get("hazir_gorevler") or []:
            if not isinstance(g, dict) or not isinstance(g.get("etiket"), str) or not isinstance(g.get("prompt"), str):
                raise ValueError("Hazır görev biçimi bozuk.")
        if not all(isinstance(x, str) for x in a.get("izinli_araclar") or []):
            raise ValueError("Araç listesi bozuk.")
        if a.get("saglayici") not in (None, *SAGLAYICILAR):
            raise ValueError(f"Geçersiz sağlayıcı: {a.get('saglayici')!r}")
        if a.get("saglayici") == "opencode" and isinstance(a.get("model"), str) \
                and not OPENCODE_MODEL_DESENI.match(a["model"]):
            raise ValueError(f"Opencode modeli 'saglayici/model' biçiminde olmalı: {a.get('model')!r}")
        if a.get("variant") not in (None, *[v for v in VARIANTLAR if v]):
            raise ValueError(f"Geçersiz düşünme gücü: {a.get('variant')!r}")
        yedek = a.get("yedek_saglayici")
        if yedek not in (None, "", "opencode"):
            raise ValueError(f"Yedek sağlayıcı yalnız opencode olabilir: {yedek!r}")
        if isinstance(a.get("yedek_model"), str) and a["yedek_model"] \
                and not OPENCODE_MODEL_DESENI.match(a["yedek_model"]):
            raise ValueError(f"Yedek model 'saglayici/model' biçiminde olmalı: {a['yedek_model']!r}")
        if a.get("yedek_variant") not in (None, *[v for v in VARIANTLAR if v]):
            raise ValueError(f"Geçersiz yedek düşünme gücü: {a.get('yedek_variant')!r}")
    if "ceo" not in idler:
        raise ValueError("CEO silinemez.")
    for o in veri.get("odalar") or []:  # aynı id'li oda eski dosyalarda olabilir: ilki geçerli, reddedilmez
        if not isinstance(o, dict) or not isinstance(o.get("id"), str) or not ortak.ODA_ID_DESENI.fullmatch(o["id"]):
            raise ValueError("Geçersiz oda kaydı.")
        if o.get("tema") is not None and o["tema"] not in TEMALAR:
            raise ValueError(f"Bilinmeyen oda görünümü: {o['tema']}")


def kaydet(veri):
    with KILIT:
        dogrula(veri)
        yol = ortak.AJANLAR_DOSYASI
        if os.path.exists(yol):
            shutil.copyfile(yol, yol + ".bak")  # elle düzeltmek gerekirse bir önceki hâl
        ortak.atomik_yaz(yol, json.dumps(veri, ensure_ascii=False, indent=2))


# ---------- odalar ----------

def _oda_idleri(veri):
    return ({o.get("id") for o in veri.get("odalar") or []} | {a.get("oda") or "genel" for a in veri["ajanlar"]}
            | {"ceo", "genel"})


def _oda_olustur(veri, ad, tema=None, aciklama=""):
    ad = _metin(ad, "Oda adı", MAKS_AD, bos_olabilir=False)
    if tema is not None and tema not in TEMALAR:
        raise ValueError(f"Bilinmeyen oda görünümü: {tema}")
    oda = {"id": id_turet(ad, _oda_idleri(veri)), "ad": ad,
           **({"tema": tema} if tema else {}), "aciklama": _metin(aciklama or "", "Oda açıklaması", MAKS_ACIKLAMA)}
    veri.setdefault("odalar", []).append(oda)
    return oda


def oda_ekle(ad, tema=None, aciklama=""):
    with KILIT:
        veri = oku()
        oda = _oda_olustur(veri, ad, tema, aciklama)
        kaydet(veri)
        return oda


def oda_guncelle(oda_id, alanlar):
    with KILIT:
        veri = oku()
        if oda_id not in _oda_idleri(veri):
            raise ValueError("Böyle bir oda yok.")
        oda = next((o for o in veri.setdefault("odalar", []) if o.get("id") == oda_id), None)
        if oda is None:  # yalnız ajanlarda geçen oda: listeye eklenir
            oda = {"id": oda_id, "ad": oda_id}
            veri["odalar"].append(oda)
        if "ad" in alanlar:
            oda["ad"] = _metin(alanlar["ad"], "Oda adı", MAKS_AD, bos_olabilir=False)
        if "aciklama" in alanlar:
            oda["aciklama"] = _metin(alanlar["aciklama"] or "", "Oda açıklaması", MAKS_ACIKLAMA)
        if "tema" in alanlar:
            if alanlar["tema"] and alanlar["tema"] not in TEMALAR:
                raise ValueError(f"Bilinmeyen oda görünümü: {alanlar['tema']}")
            oda.pop("tema", None)
            if alanlar["tema"]:
                oda["tema"] = alanlar["tema"]
        kaydet(veri)
        return oda


# ---------- ajanlar ----------

def _bul(veri, ajan_id):
    a = next((a for a in veri["ajanlar"] if a.get("id") == ajan_id), None)
    if a is None:
        raise ValueError("Böyle bir ajan yok.")
    return a


def _yetkiler(araclar):
    return [k for k, liste in YETKILER.items() if set(liste) <= set(araclar or [])]


def _alanlari_uygula(veri, ajan, alanlar):
    """Formdan gelen alanları ajana uygular; formda olmayan alanlara dokunmaz. Oluşturulacak klasörü döndürür."""
    if "ad" in alanlar:
        ajan["ad"] = _metin(alanlar["ad"], "Ajan adı", MAKS_AD, bos_olabilir=False)
    if alanlar.get("yeni_oda"):
        y = alanlar["yeni_oda"]
        if not isinstance(y, dict):
            raise ValueError("Yeni oda bilgisi bozuk.")
        ajan["oda"] = _oda_olustur(veri, y.get("ad"), y.get("tema") or None, y.get("aciklama") or "")["id"]
    elif "oda" in alanlar:
        oda = alanlar["oda"]
        if not isinstance(oda, str) or oda not in _oda_idleri(veri) or (oda == "ceo" and ajan.get("oda") != "ceo"):
            raise ValueError("Böyle bir oda yok.")  # CEO odasına yeni ajan konmaz; zaten oradaysa kalabilir
        ajan["oda"] = oda
    if ajan.get("id") == "ceo" and ajan.get("oda", "ceo") != "ceo":
        raise ValueError("CEO kendi odasında kalır.")
    if "aciklama" in alanlar:
        ajan["aciklama"] = _metin(alanlar["aciklama"] or "", "Açıklama", MAKS_ACIKLAMA)
    if "saglayici" in alanlar:
        sag = alanlar["saglayici"]
        if sag not in SAGLAYICILAR:
            raise ValueError("Sağlayıcı Claude ya da Opencode olmalı.")
        ajan["saglayici"] = sag
    if "variant" in alanlar:
        v = alanlar["variant"] or ""
        if v not in VARIANTLAR:
            raise ValueError("Düşünme gücü minimal, low, medium, high ya da max olmalı.")
        if v:
            ajan["variant"] = v
        else:
            ajan.pop("variant", None)
    if "yedek_saglayici" in alanlar:
        ys = alanlar["yedek_saglayici"] or ""
        if ys not in ("", "opencode"):
            raise ValueError("Yedek sağlayıcı yalnız opencode olabilir.")
        if ys:
            ajan["yedek_saglayici"] = ys
        else:  # yedek kapatıldı: ilgili alanları temizle
            for k in ("yedek_saglayici", "yedek_model", "yedek_variant"):
                ajan.pop(k, None)
    if "yedek_model" in alanlar:
        ym = (alanlar["yedek_model"] or "").strip()
        if ym and (not OPENCODE_MODEL_DESENI.match(ym) or len(ym) > 120):
            raise ValueError("Yedek model 'saglayici/model' biçiminde olmalı.")
        if ym:
            ajan["yedek_model"] = ym
        else:
            ajan.pop("yedek_model", None)
    if "yedek_variant" in alanlar:
        yv = alanlar["yedek_variant"] or ""
        if yv not in VARIANTLAR:
            raise ValueError("Yedek düşünme gücü geçersiz.")
        if yv:
            ajan["yedek_variant"] = yv
        else:
            ajan.pop("yedek_variant", None)
    if "model" in alanlar:
        model = alanlar["model"]
        sag = ajan.get("saglayici") or "claude"
        if sag == "opencode":
            if not isinstance(model, str) or not OPENCODE_MODEL_DESENI.match(model) or len(model) > 120:
                raise ValueError("Opencode modeli 'saglayici/model' biçiminde olmalı (ör. myprovider/deepseek-v4.1-flash).")
        elif model not in MODELLER:
            raise ValueError("Model Sonnet, Haiku ya da Opus olmalı.")
        ajan["model"] = model
    if "izinli_araclar" in alanlar:
        araclar = alanlar["izinli_araclar"]
        if not isinstance(araclar, list) or not all(isinstance(x, str) and 0 < len(x) <= 100 for x in araclar):
            raise ValueError("Araç listesi bozuk.")
        ajan["izinli_araclar"] = list(dict.fromkeys(araclar))
    elif "yetkiler" in alanlar:
        y = alanlar["yetkiler"]
        if not isinstance(y, list) or not all(isinstance(k, str) for k in y) or not set(y) <= set(YETKILER):
            raise ValueError("Bilinmeyen yetki.")
        ajan["izinli_araclar"] = [a for k in YETKILER if k in y or k == "okuma" for a in YETKILER[k]]
    if "hazir_gorevler" in alanlar:
        g = alanlar["hazir_gorevler"]
        if not isinstance(g, list) or len(g) > MAKS_GOREV:
            raise ValueError(f"En fazla {MAKS_GOREV} hazır görev olabilir.")
        ajan["hazir_gorevler"] = [{"etiket": _metin(x.get("etiket"), "Görev adı", MAKS_AD, bos_olabilir=False),
                                   "prompt": _metin(x.get("prompt"), "Görev metni", ortak.MAKS_GIRDI, bos_olabilir=False)}
                                  for x in g if isinstance(x, dict)]
    if "yalin" in alanlar:
        ajan["yalin"] = bool(alanlar["yalin"])
    if "tetik_kelime" in alanlar:
        t = _metin(alanlar["tetik_kelime"] or "", "Tetik kelime", 40)
        ajan.pop("tetik_kelime", None)
        if t:
            ajan["tetik_kelime"] = t
    if "cwd" in alanlar:
        cwd = _metin(alanlar["cwd"] or "", "Çalışma klasörü", 500)
        if cwd and ortak.SUNUCU and not ortak.calisma_icinde(ortak.cwd_coz(cwd)):
            raise ValueError("Sunucuda çalışma klasörü yalnız calisma/ altında olabilir; boş bırakırsan otomatik açılır.")
        ajan["cwd"] = cwd or f"{CALISMA}/{ajan['id']}"
    return ortak.cwd_coz(ajan["cwd"]) if ajan.get("cwd") == f"{CALISMA}/{ajan['id']}" else None


def ajan_ekle(alanlar):
    with KILIT:
        veri = oku()
        ad = _metin(alanlar.get("ad"), "Ajan adı", MAKS_AD, bos_olabilir=False)
        ajan = {"id": id_turet(ad, {a.get("id") for a in veri["ajanlar"]}), "ad": ad, "oda": "genel",
                "cwd": "", "saglayici": "claude", "model": "sonnet", "ne_zaman": "istek", "ne_zaman_metin": "İstek gelince",
                "aciklama": "", "izinli_araclar": list(YETKILER["okuma"]), "hazir_gorevler": []}
        if len(veri["ajanlar"]) >= MAKS_AJAN:
            raise ValueError(f"En fazla {MAKS_AJAN} ajan olabilir.")
        klasor = _alanlari_uygula(veri, ajan, {"cwd": "", **alanlar})
        veri["ajanlar"].append(ajan)
        kaydet(veri)
        if klasor:
            ortak.ajan_klasoru_ac(klasor)
        return ajan


def ajan_guncelle(ajan_id, alanlar):
    with KILIT:
        veri = oku()
        ajan = _bul(veri, ajan_id)
        klasor = _alanlari_uygula(veri, ajan, {k: v for k, v in alanlar.items() if k != "id"})
        kaydet(veri)
        if klasor:
            ortak.ajan_klasoru_ac(klasor)
        return ajan


def ajan_sil(ajan_id):
    if ajan_id == "ceo":
        raise ValueError("CEO silinemez.")
    with KILIT:
        veri = oku()
        _bul(veri, ajan_id)
        veri["ajanlar"] = [a for a in veri["ajanlar"] if a.get("id") != ajan_id]
        kaydet(veri)  # hafiza/<id>.md ve cikti/<id>/ diskte kalır


def ajan_ayrinti(ajan_id):
    a = dict(_bul(oku(), ajan_id))
    a["yetkiler"] = _yetkiler(a.get("izinli_araclar"))
    return a


# ---------- sektör şablonları ----------
SABLON_DIZINI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sablonlar")


def _sablonlar():
    sonuc = {}
    for ad in sorted(os.listdir(SABLON_DIZINI)):
        if ad.endswith(".json"):
            with open(os.path.join(SABLON_DIZINI, ad), encoding="utf-8") as f:
                sonuc[ad[:-5]] = json.load(f)
    return sonuc


def sablon_listesi():
    liste = [{"id": i, "ad": s["ad"], "aciklama": s["aciklama"], "odalar": s["odalar"],
              "ajanlar": [{k: a[k] for k in ("id", "ad", "oda", "aciklama")} for a in s["ajanlar"]]}
             for i, s in _sablonlar().items()]
    return sorted(liste, key=lambda s: s["ad"])


def sablondan_ekle(sablon_id, ajan_idleri=None):
    """Şablonun (seçili) ajanlarını ve yalnız onların odalarını ekler; var olan ajan id'si atlanır."""
    sablon = _sablonlar().get(sablon_id)  # yalnız listedeki adlar: yol enjeksiyonu yok
    if not sablon:
        raise ValueError("Böyle bir şablon yok.")
    secili = [a for a in sablon["ajanlar"] if ajan_idleri is None or a["id"] in ajan_idleri]
    with KILIT:
        veri = oku()
        var_olan = {a.get("id") for a in veri["ajanlar"]}
        eklenen, atlanan, klasorler = [], [], []
        for s in secili:
            if s["id"] in var_olan:
                atlanan.append(s["id"])
                continue
            if s["oda"] not in _oda_idleri(veri):  # var olan oda id'si yeniden kullanılır
                oda = next(o for o in sablon["odalar"] if o["id"] == s["oda"])
                veri.setdefault("odalar", []).append({k: oda[k] for k in ("id", "ad", "tema", "aciklama") if k in oda})
            cwd = f"{CALISMA}/{s['id']}"
            veri["ajanlar"].append({
                "id": s["id"], "ad": s["ad"], "oda": s["oda"], "cwd": cwd, "model": s["model"],
                "ne_zaman": "istek", "ne_zaman_metin": "İstek gelince", "aciklama": s["aciklama"],
                "izinli_araclar": [a for k in YETKILER if k in s["yetkiler"] for a in YETKILER[k]],
                "hazir_gorevler": [dict(g) for g in s["hazir_gorevler"]],
            })
            eklenen.append(s["id"])
            klasorler.append(ortak.cwd_coz(cwd))
        if len(veri["ajanlar"]) > MAKS_AJAN:
            raise ValueError(f"En fazla {MAKS_AJAN} ajan olabilir.")
        if eklenen:
            kaydet(veri)
        for k in klasorler:
            ortak.ajan_klasoru_ac(k)
    return {"eklenen": eklenen, "atlanan": atlanan}
