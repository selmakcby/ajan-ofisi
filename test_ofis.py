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
    for i in range(510):
        sorular.mesaj_esle(i, {"tip": "ceo", "cevap": str(i)})
    assert sorular.mesaj_hedefi(5) is None and sorular.mesaj_hedefi(509)["cevap"] == "509"


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
