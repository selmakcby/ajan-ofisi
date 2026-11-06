#!/usr/bin/env python3
"""Ajan Ofisi self-check. Bağımlılık yok: python test_ofis.py → her test_* koşar, sonunda OK.

`tmp` parametresi alan teste yeni bir geçici klasör verilir; her testten önce ortak.DURUM_DIZINI
o klasörün altındaki durum/'a çevrilir (gerçek çalışma verisine dokunulmaz).
"""
import inspect
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak  # noqa: E402


# ---------- Task 1: .env ve Telegram ayarı ----------

def test_env_oku(tmp):
    yol = os.path.join(tmp, ".env")
    open(yol, "w", encoding="utf-8").write('# yorum\n\nA=1\nB="iki"\nC = üç \n')
    assert ortak.env_oku(yol) == {"A": "1", "B": "iki", "C": "üç"}
    assert ortak.env_oku(os.path.join(tmp, "yok")) == {}


def test_telegram_ayari(tmp):
    yol = os.path.join(tmp, ".env")
    open(yol, "w", encoding="utf-8").write("OFIS_TELEGRAM_TOKEN=\n")
    assert ortak.telegram_ayari(yol) is None
    open(yol, "w", encoding="utf-8").write(
        "OFIS_TELEGRAM_TOKEN=t\nOFIS_TELEGRAM_KULLANICI=42\nOFIS_TELEGRAM_RAPOR_SAATI=9:5x\n")
    assert ortak.telegram_ayari(yol) == {"token": "t", "kullanici": 42, "rapor_saati": (18, 0)}
    os.environ["OFIS_TELEGRAM_KULLANICI"] = "7"
    try:
        assert ortak.telegram_ayari(yol)["kullanici"] == 7
    finally:
        del os.environ["OFIS_TELEGRAM_KULLANICI"]


def test_env_yaz(tmp):
    yol = os.path.join(tmp, ".env")
    open(yol, "w", encoding="utf-8").write("# not\nBASKA=1\nOFIS_TELEGRAM_TOKEN=eski\n")
    ortak.env_yaz({"OFIS_TELEGRAM_TOKEN": "yeni", "OFIS_TELEGRAM_KULLANICI": "5"}, yol)
    assert ortak.env_oku(yol) == {"BASKA": "1", "OFIS_TELEGRAM_TOKEN": "yeni", "OFIS_TELEGRAM_KULLANICI": "5"}
    ortak.env_yaz({"OFIS_TELEGRAM_TOKEN": None}, yol)
    assert "OFIS_TELEGRAM_TOKEN" not in ortak.env_oku(yol)
    assert open(yol, encoding="utf-8").read().startswith("# not")
    ortak.env_yaz({"YENI": "x"}, os.path.join(tmp, "olmayan.env"))  # dosya yoksa oluşturur
    assert ortak.env_oku(os.path.join(tmp, "olmayan.env")) == {"YENI": "x"}


# ---------- Task 2: koşucu soru bloğu ve sürdürme ----------

def test_soru_ayikla():
    import kosucu
    assert kosucu.soru_ayikla("bitti") is None
    assert kosucu.soru_ayikla('x <soru tur="diger">Plan uygun mu?</soru>') == {"soru": "Plan uygun mu?", "tur": "diger"}
    assert kosucu.soru_ayikla('<soru tur="maliyet">SMS?</soru>')["tur"] == "maliyet"


def test_soru_ayikla_bozuk():
    import kosucu
    assert kosucu.soru_ayikla("<soru>tur yok</soru>")["tur"] == "eksik"
    assert kosucu.soru_ayikla('<soru tur="uydurma">a</soru>')["tur"] == "eksik"
    assert kosucu.soru_ayikla('<soru tur="diger">a</soru><soru tur="diger">b</soru>') == {"soru": "a\nb", "tur": "eksik"}
    assert kosucu.soru_ayikla('<soru tur="diger">  </soru>') == {"soru": "", "tur": "eksik"}


def test_komut_kur_devam():
    import kosucu
    ajan = {"model": "haiku", "cwd": ".", "izinli_araclar": []}
    k = kosucu.komut_kur(ajan, [], "cikti")
    assert "--no-session-persistence" not in k and "--resume" not in k
    k = kosucu.komut_kur(ajan, [], "cikti", devam_session="abc")
    assert k[k.index("--resume") + 1] == "abc"


def test_soru_temizle():
    import kosucu
    assert kosucu.soru_temizle('Plan hazır.\n<soru tur="diger">Uygun mu?</soru>') == "Plan hazır."


# ---------- Task 3: sorular.py kalıcı durum ----------

def test_soru_kaydi():
    import sorular
    sid = sorular.soru_ekle("yazar", "k1", "s1", "Uygun mu?", "diger")
    assert sid == "k1" and sorular.soru_al("k1")["durum"] == "yeni"
    sorular.soru_guncelle(sid, durum="kullanicida")
    assert [s["soru_id"] for s in sorular.bekleyen_sorular()] == ["k1"]
    assert sorular.otomatik_artir("s1") == 1 and sorular.otomatik_artir("s1") == 2
    sorular.otomatik_sifirla("s1")
    assert sorular.otomatik_sayi("s1") == 0


def test_mesaj_esleme_sinir():
    import sorular
    assert sorular.MAKS_MESAJ == 500
    eski, sorular.MAKS_MESAJ = sorular.MAKS_MESAJ, 5  # Windows'ta 500 dosya yazımı yavaş; davranış aynı
    try:
        for i in range(8):
            sorular.mesaj_esle(i, {"tip": "ceo", "cevap": str(i)})
    finally:
        sorular.MAKS_MESAJ = eski
    assert sorular.mesaj_hedefi(2) is None and sorular.mesaj_hedefi(3)["cevap"] == "3"
    assert sorular.mesaj_hedefi(7)["cevap"] == "7"


def test_devam_kuyrugu():
    import sorular
    sorular.devam_birak("yazar", {"a": 1})
    sorular.devam_birak("yazar", {"a": 2})
    assert sorular.devam_al("yazar") == {"a": 2} and sorular.devam_al("yazar") is None


def test_rapor_derle():
    import sorular
    assert sorular.rapor_derle() == (None, [])
    sorular.karar_ekle({"ajan": "yazar", "soru": "S", "cevap": "C", "gerekce": "G", "kosu_id": "k", "session_id": "s"})
    metin, maddeler = sorular.rapor_derle()
    assert metin.startswith("1. yazar: S → C") and maddeler == [{"ajan": "yazar", "session_id": "s", "kosu_id": "k"}]
    sorular.rapor_isaretle(ortak.simdi_iso())
    assert sorular.rapor_derle() == (None, [])


# ---------- Task 4: sunucu triyaj ve ofis durumu ----------

def test_triyaj_guvenli_taraf():
    import sunucu
    eski = sunucu.claude_json
    try:
        def bozuk(*a, **k):
            raise ValueError("bozuk")
        sunucu.claude_json = bozuk
        assert sunucu.ceo_triyaj("yazar", "S", "O")["karar"] == "kullaniciya"
        sunucu.claude_json = lambda *a, **k: {"veri": {"karar": "belki"}, "ham": {}}
        assert sunucu.ceo_triyaj("yazar", "S", "O")["karar"] == "kullaniciya"
        tamam = {"karar": "kendim", "cevap": "evet", "gerekce": "küçük", "kullaniciya_not": ""}
        sunucu.claude_json = lambda *a, **k: {"veri": tamam, "ham": {}}
        assert sunucu.ceo_triyaj("yazar", "S", "O") == tamam
    finally:
        sunucu.claude_json = eski


def test_ofis_durumu_sinir():
    import sunucu
    tablo = {f"a{i}": {"id": f"a{i}", "ad": "A", "oda": "genel", "kurulu": True} for i in range(200)}
    assert len(sunucu.ofis_durumu_metni(tablo)) <= 3000


def test_canli_durum_cevap_bekliyor():
    import sunucu
    ortak.durum_yaz("yazar", {"durum": "cevap_bekliyor", "bitis_ts": 0, "soru": "S"})
    assert sunucu.canli_durum("yazar")[0] == "cevap_bekliyor"


# ---------- Task 5: akis.py olay izleyici ----------

class MesgulHata(Exception):
    kod = 409


def _izleyici(triyaj_sonucu=None, mesgul=False):
    import akis
    cagrilar = []

    def gorev_baslat(ajan, **k):
        cagrilar.append(("gorev", ajan, k))
        if mesgul:
            raise MesgulHata("ajan zaten çalışıyor")

    def triyaj(ajan, soru, ozet):
        cagrilar.append(("triyaj", ajan, soru))
        return triyaj_sonucu

    def bildir(metin, hedef):
        cagrilar.append(("bildir", hedef and hedef.get("tip"), metin))

    return akis.Izleyici(gorev_baslat, triyaj, bildir), cagrilar


def _bitti(**k):
    return {"tur": "kosu_bitti", "ajan": "yazar", "kosu_id": "k1", "session_id": "s1", "durum": "basarili",
            "ozet": "Plan hazır.", "kaynak": "buton", "soru": None, "soru_tur": None, "hata": None, **k}


def test_onemli_soru_triyajsiz_kullaniciya():
    import sorular
    iz, c = _izleyici()
    iz.olay_isle(_bitti(soru="SMS entegrasyonu yapalım mı?", soru_tur="buyuk-degisiklik"))
    assert [x[:2] for x in c] == [("bildir", "soru")]
    assert "SMS entegrasyonu" in c[0][2] and sorular.soru_al("k1")["durum"] == "kullanicida"


def test_diger_soru_ceo_kendim():
    import sorular
    iz, c = _izleyici({"karar": "kendim", "cevap": "Evet, başla.", "gerekce": "küçük", "kullaniciya_not": ""})
    iz.olay_isle(_bitti(soru="Dosya adı uygun mu?", soru_tur="diger", kaynak="telegram"))
    assert c == [("triyaj", "yazar", "Dosya adı uygun mu?"),
                 ("gorev", "yazar", {"kaynak": "telegram", "devam": {"session_id": "s1", "cevap": "Evet, başla.",
                                                                     "cevap_kaynak": "ceo"}})]
    assert len(sorular.son_kararlar()) == 1 and sorular.otomatik_sayi("s1") == 1
    assert sorular.soru_al("k1")["durum"] == "ceo"


def test_diger_soru_ceo_kullaniciya_yukseltir():
    iz, c = _izleyici({"karar": "kullaniciya", "cevap": "", "gerekce": "", "kullaniciya_not": "Maliyetli olabilir."})
    iz.olay_isle(_bitti(soru="Yeni sunucu?", soru_tur="diger"))
    assert [x[:2] for x in c] == [("triyaj", "yazar"), ("bildir", "soru")] and "Maliyetli olabilir." in c[1][2]


def test_otomatik_sinir_3():
    import sorular
    for _ in range(3):
        sorular.otomatik_artir("s1")
    iz, c = _izleyici({"karar": "kendim", "cevap": "x", "gerekce": "", "kullaniciya_not": ""})
    iz.olay_isle(_bitti(soru="Yine uygun mu?", soru_tur="diger"))
    assert [x[:2] for x in c] == [("bildir", "soru")]


def test_mesgul_ajana_devam_kuyruga():
    import sorular
    iz, c = _izleyici({"karar": "kendim", "cevap": "Evet.", "gerekce": "", "kullaniciya_not": ""}, mesgul=True)
    iz.olay_isle(_bitti(soru="Uygun mu?", soru_tur="diger"))
    bekleyen = sorular.devam_al("yazar")
    assert bekleyen["devam"]["cevap"] == "Evet."
    sorular.devam_birak("yazar", bekleyen)
    iz2, c2 = _izleyici()
    iz2.olay_isle(_bitti(kosu_id="k2"))  # ajanın sonraki koşusu bitti → kuyruktaki devam başlar
    assert c2[0] == ("gorev", "yazar", {k: v for k, v in bekleyen.items() if k != "ajan_id"})
    assert sorular.devam_al("yazar") is None


def test_hata_bildirilir_arayuz_sonucu_bildirilmez():
    iz, c = _izleyici()
    iz.olay_isle(_bitti())
    assert c == []
    iz.olay_isle(_bitti(durum="hata", hata="claude çıkış kodu 1"))
    assert [x[:2] for x in c] == [("bildir", "kosu")] and "claude çıkış kodu 1" in c[0][2]
    iz.olay_isle(_bitti(kaynak="telegram-ceo"))
    assert [x[:2] for x in c][-1] == ("bildir", "kosu")
    iz.olay_isle({"tur": "ceo_bitti", "durum": "hata", "hata": "TimeoutExpired"})
    assert c[-1][1] is None and "TimeoutExpired" in c[-1][2]


def test_bitir_durum_olaydan_once(tmp):
    import kosucu
    gorulen = []
    eski = ortak.olay_yaz
    try:
        ortak.olay_yaz = lambda olay: gorulen.append(ortak.durum_oku("yazar")["durum"])
        os.makedirs(os.path.join(tmp, "cikti"))
        kosucu.bitir({"id": "yazar"}, {"kosu_id": "k", "ajan": "yazar", "oda": "genel"},
                     {"result": "tamam", "session_id": "s"}, None, 0, os.path.join(tmp, "x.log"),
                     os.path.join(tmp, "cikti"))
    finally:
        ortak.olay_yaz = eski
    assert gorulen == ["bitti"]  # izleyici kosu_bitti'yi gördüğünde ajan artık meşgul değil


# ---------- Task 6: telegram.py ----------

class SahteApi:
    def __init__(self, guncellemeler=None, hata=None):
        self.gonderilen, self.g, self.hata, self.sayac = [], list(guncellemeler or []), hata, 100

    def guncellemeler(self, ofset):
        if self.hata:
            raise self.hata
        g, self.g = self.g, []
        return g

    def gonder(self, chat_id, metin, yanit_id=None):
        self.sayac += 1
        self.gonderilen.append((chat_id, metin, yanit_id))
        return self.sayac

    def cagir(self, metod, **p):
        return {}


def _mesaj(metin, gonderen=42, yanit=None, uid=1):
    m = {"message_id": 500 + uid, "text": metin, "from": {"id": gonderen, "first_name": "Ramazan"},
         "chat": {"id": gonderen}}
    if yanit is not None:
        m["reply_to_message"] = {"message_id": yanit}
    return {"update_id": uid, "message": m}


def _bot(tmp, kullanici=42, mesgul=False, api=None):
    import json as _json
    import telegram_kopru as telegram
    yol = os.path.join(tmp, "ajanlar.json")
    os.makedirs(os.path.join(tmp, "yazar"), exist_ok=True)
    _json.dump({"ajanlar": [{"id": "yazar", "ad": "Yazar", "cwd": os.path.join(tmp, "yazar")},
                            {"id": "ceo", "ad": "CEO", "cwd": tmp}]}, open(yol, "w", encoding="utf-8"))
    ortak.AJANLAR_DOSYASI = yol
    cagrilar = []

    def gorev_baslat(ajan, **k):
        cagrilar.append(("gorev", ajan, k))
        if mesgul:
            raise MesgulHata("ajan zaten çalışıyor")
        return {"kosu_id": "k9", "ajan": ajan}

    def ceo_calistir(metin, **k):
        cagrilar.append(("ceo", metin, k))
        return {"cevap": "Herkes uyuyor.", "baslatilan": [], "reddedilen": []}

    api = api or SahteApi()
    bot = telegram.Bot({"token": "1:x", "kullanici": kullanici, "rapor_saati": (18, 0)}, api,
                       gorev_baslat, ceo_calistir, env_yolu=os.path.join(tmp, ".env"))
    return bot, api, cagrilar


def test_kisalt_4096():
    import telegram_kopru as telegram
    m = telegram.kisalt("*_[" * 3000, ek="cikti/x.md")
    assert len(m) <= 4096 and m.endswith("cikti/x.md")
    assert telegram.kisalt("kısa") == "kısa"


def test_yonlendir():
    import telegram_kopru as telegram
    t = {"yazar": {"id": "yazar", "kurulu": True}, "eski": {"id": "eski", "kurulu": False}}
    assert telegram.yonlendir("ne yapıyorsunuz?", None, t) == {"tip": "ceo", "metin": "ne yapıyorsunuz?", "onceki_cevap": None}
    assert telegram.yonlendir("@yazar taslak yaz", None, t) == {"tip": "ajan", "ajan": "yazar", "prompt": "taslak yaz"}
    assert telegram.yonlendir("@ceo durum?", None, t)["tip"] == "ceo"
    soru = {"tip": "soru", "soru_id": "k", "ajan": "yazar", "session_id": "s"}
    assert telegram.yonlendir("onaylıyorum", soru, t) == {"tip": "devam", "ajan": "yazar", "session_id": "s",
                                                          "cevap": "onaylıyorum", "soru_id": "k"}
    r = {"tip": "rapor", "maddeler": [{"ajan": "yazar", "session_id": "s", "kosu_id": "k"}]}
    assert telegram.yonlendir("1 geri al", r, t)["session_id"] == "s"
    assert telegram.yonlendir("1 geri al", r, t)["cevap"] == "geri al"
    assert telegram.yonlendir("5 geri al", r, t)["tip"] == "hata"
    assert telegram.yonlendir("genel yorum", r, t)["tip"] == "ceo"
    assert telegram.yonlendir("tamam", {"tip": "ceo", "cevap": "önceki"}, t)["onceki_cevap"] == "önceki"
    assert telegram.yonlendir("/baslat 482913", None, t) == {"tip": "eslestir", "kod": "482913"}


def test_yonlendir_bilinmeyen_ajan():
    import telegram_kopru as telegram
    t = {"eski": {"id": "eski", "kurulu": False}}
    assert telegram.yonlendir("@yok selam", None, t)["tip"] == "hata"
    assert telegram.yonlendir("@eski selam", None, t)["tip"] == "hata"


def test_rapor_zamani_mi():
    from datetime import datetime
    import telegram_kopru as telegram
    s = datetime(2026, 11, 6, 18, 1)
    assert telegram.rapor_zamani_mi(s, (18, 0), None)
    assert not telegram.rapor_zamani_mi(s, (18, 0), "2026-11-06T18:00:30+03:00")
    assert telegram.rapor_zamani_mi(s, (18, 0), "2026-11-05T18:00:30+03:00")
    assert not telegram.rapor_zamani_mi(datetime(2026, 11, 6, 17, 59), (18, 0), None)


def test_yetkisiz_kullanici(tmp):
    bot, api, c = _bot(tmp)
    bot.isle(_mesaj("@yazar sil her şeyi", gonderen=99))
    bot.isle(_mesaj("ne var ne yok", gonderen=99))
    assert c == [] and api.gonderilen == []


def test_bot_yonlendirme(tmp):
    bot, api, c = _bot(tmp)
    bot.isle(_mesaj("@yazar taslak yaz"))
    assert c == [("gorev", "yazar", {"prompt": "taslak yaz", "kaynak": "telegram"})]
    bot.isle(_mesaj("kim ne yapıyor?", uid=2))
    assert c[-1] == ("ceo", "kim ne yapıyor?", {"kaynak": "telegram", "onceki_cevap": None})
    assert "Herkes uyuyor." in api.gonderilen[-1][1]


def test_bot_soruya_cevap(tmp):
    import sorular
    bot, api, c = _bot(tmp, mesgul=True)
    sorular.soru_ekle("yazar", "k1", "s1", "Uygun mu?", "diger")
    sorular.otomatik_artir("s1")
    sorular.mesaj_esle(777, {"tip": "soru", "soru_id": "k1", "ajan": "yazar", "session_id": "s1"})
    bot.isle(_mesaj("onaylıyorum", yanit=777))
    assert c[0][2]["devam"] == {"session_id": "s1", "cevap": "onaylıyorum", "cevap_kaynak": "kullanici"}
    assert sorular.otomatik_sayi("s1") == 0 and sorular.soru_al("k1")["durum"] == "cevaplandi"
    assert sorular.devam_al("yazar")["devam"]["cevap"] == "onaylıyorum"  # meşgul → kuyruk
    assert "meşgul" in api.gonderilen[-1][1]


def test_eslestirme(tmp):
    import time as _time
    bot, api, c = _bot(tmp, kullanici=None)
    kod = bot.kod_uret()["kod"]
    assert len(kod) == 6 and kod.isdigit()
    yanlis = "000000" if kod != "000000" else "111111"
    bot.isle(_mesaj(f"/baslat {yanlis}", gonderen=77))
    assert bot.ayar["kullanici"] is None and api.gonderilen == []
    bot.isle(_mesaj(f"/baslat {kod}", gonderen=77, uid=2))
    assert bot.ayar["kullanici"] == 77 and ortak.env_oku(os.path.join(tmp, ".env"))["OFIS_TELEGRAM_KULLANICI"] == "77"
    assert len(api.gonderilen) == 1
    bot.isle(_mesaj(f"/baslat {kod}", gonderen=88, uid=3))  # tek kullanımlık
    assert bot.ayar["kullanici"] == 77
    yeni = bot.kod_uret()
    bot.kod["bitis_ts"] = _time.time() - 1  # süresi dolmuş
    bot.isle(_mesaj(f"/baslat {yeni['kod']}", gonderen=88, uid=4))
    assert bot.ayar["kullanici"] == 77


def test_api_hatasi_dongu_dusurmez(tmp):
    bot, api, c = _bot(tmp, api=SahteApi(hata=OSError("ağ yok")))
    bot.tur()
    assert bot.bekleme > 0 and bot.son_hata
    bot.api.hata = None
    bot.tur()
    assert bot.bekleme == 0 and bot.son_hata is None


def test_bot_ofset_ve_kapaliyken_gelenler(tmp):
    api = SahteApi([_mesaj("@yazar bir", uid=10), _mesaj("@yazar iki", uid=11)])
    bot, api, c = _bot(tmp, api=api)
    bot.tur()
    assert [x[2]["prompt"] for x in c] == ["bir", "iki"]  # geliş sırasıyla, sorulmadan
    bot2, _, _ = _bot(tmp)
    assert bot2.ofset == 11


def test_bildir_soru_mesaj_eslemesi(tmp):
    import sorular
    bot, api, c = _bot(tmp)
    sorular.soru_ekle("yazar", "k1", "s1", "Uygun mu?", "maliyet")
    mid = bot.bildir("❓ yazar soruyor", {"tip": "soru", "soru_id": "k1", "ajan": "yazar", "session_id": "s1"})
    assert sorular.mesaj_hedefi(mid)["soru_id"] == "k1" and sorular.soru_al("k1")["telegram_mesaj_id"] == mid


# ---------- koşucu ----------

def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows'ta yönlendirilmiş çıktı cp1254 olabilir
    sys.stderr.reconfigure(encoding="utf-8")
    testler = [(ad, f) for ad, f in globals().items() if ad.startswith("test_") and callable(f)]
    if len(sys.argv) > 1:
        testler = [(ad, f) for ad, f in testler if any(s in ad for s in sys.argv[1:])]
    asil_durum = ortak.DURUM_DIZINI
    hatali = 0
    for ad, f in testler:
        tmp = tempfile.mkdtemp(prefix="ofis-test-")
        ortak.DURUM_DIZINI = os.path.join(tmp, "durum")
        os.makedirs(ortak.DURUM_DIZINI)
        try:
            f(tmp) if inspect.signature(f).parameters else f()
            print(f"  ✓ {ad}")
        except Exception:
            hatali += 1
            print(f"  ✗ {ad}")
            traceback.print_exc()
        finally:
            ortak.DURUM_DIZINI = asil_durum
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"{len(testler) - hatali}/{len(testler)}")
    if hatali:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
