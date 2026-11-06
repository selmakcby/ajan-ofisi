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
