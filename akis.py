"""Olay izleyici: olaylar.jsonl'deki koşu bitişlerine tepki verir (Telegram'dan bağımsız).

- Ajan sorusu → önemliyse doğrudan kullanıcıya; değilse CEO triyajı (kendim → ajan devam eder, karar kaydedilir).
- Hata → kullanıcıya bildirim. Telegram'dan başlatılan işin sonucu → kullanıcıya bildirim.
- Meşgul ajana giden cevap kuyruğa girer; ajanın koşusu bitince başlar.
Model çağrısı yalnız triyajda olur; izlemenin kendisi 0 token.
"""
import json
import os
import sys
import threading
import time

import ortak
import sorular

OTOMATIK_SINIR = 3
TELEGRAM_KAYNAKLARI = ("telegram", "telegram-ceo")
ARALIK_SN = 1.0


class Izleyici:
    def __init__(self, gorev_baslat, triyaj, bildir=None, mesgul_mu=ortak.ajan_mesgul):
        self.gorev_baslat = gorev_baslat
        self.mesgul_mu = mesgul_mu
        self.triyaj = triyaj
        self.bildir = bildir or (lambda metin, hedef: None)  # Telegram bağlanınca atanır

    # ---------- çekirdek ----------

    def olay_isle(self, olay):
        tur = olay.get("tur")
        if tur == "ceo_bitti" and olay.get("durum") == "hata":
            self.bildir(f"⚠ CEO plan çıkaramadı: {olay.get('hata')}", None)
            return
        if tur != "kosu_bitti":
            return
        ajan = olay.get("ajan")
        bekleyen = sorular.devam_al(ajan)
        if bekleyen:
            self._baslat(ajan, bekleyen)
        hedef = {"tip": "kosu", "ajan": ajan, "session_id": olay.get("session_id"), "kosu_id": olay.get("kosu_id")}
        if olay.get("durum") == "hata":
            self.bildir(f"⚠ {ajan} hata: {olay.get('hata')}", hedef)
        elif olay.get("soru") is not None:
            self._soru_isle(olay)
        elif olay.get("kaynak") in TELEGRAM_KAYNAKLARI:
            self.bildir(f"✓ {ajan} bitti: {olay.get('ozet') or ''}\n\n{olay.get('cikti') or ''}".strip(), hedef)

    def kuyruk_isle(self):
        """Meşgul olduğu için bekletilen cevapları, ajan boşalınca başlatır (koşu kosu_bitti yazmadan
        kapanmış olsa ya da 409 ile kuyruğa giriş arasında bitmiş olsa da cevap kaybolmaz)."""
        for ajan in sorular.devam_kuyrugu():
            if not self.mesgul_mu(ajan):
                istek = sorular.devam_al(ajan)
                if istek:
                    self._baslat(ajan, istek)

    def _soru_isle(self, olay):
        ajan, session_id = olay["ajan"], olay.get("session_id")
        soru, tur = olay.get("soru") or "", olay.get("soru_tur") or "eksik"
        soru_id = sorular.soru_ekle(ajan, olay.get("kosu_id"), session_id, soru, tur)
        # Önemli tür, bozuk etiket, sürdürülemeyen oturum ya da döngü sınırı: CEO'ya hiç sorulmaz.
        if tur != "diger" or not session_id or sorular.otomatik_sayi(session_id) >= OTOMATIK_SINIR:
            return self._kullaniciya(soru_id, olay, "")
        t = self.triyaj(ajan, soru, olay.get("ozet") or "")
        if t.get("karar") != "kendim":
            return self._kullaniciya(soru_id, olay, t.get("kullaniciya_not") or "")
        sorular.karar_ekle({"ajan": ajan, "soru": soru, "cevap": t["cevap"], "gerekce": t.get("gerekce"),
                            "kosu_id": olay.get("kosu_id"), "session_id": session_id})
        sorular.otomatik_artir(session_id)
        sorular.soru_guncelle(soru_id, durum="ceo", cevap=t["cevap"])
        self._baslat(ajan, {"kaynak": olay.get("kaynak"),
                            "devam": {"session_id": session_id, "cevap": t["cevap"], "cevap_kaynak": "ceo"}})

    def _kullaniciya(self, soru_id, olay, ceo_notu):
        metin = f"❓ {olay['ajan']} soruyor: {olay.get('soru') or '(soru metni boş)'}"
        if ceo_notu:
            metin += f"\n\nCEO notu: {ceo_notu}"
        if olay.get("ozet"):
            metin += f"\n\n{olay['ozet']}"
        metin += "\n\nCevap için bu mesajı Yanıtla."
        sorular.soru_guncelle(soru_id, durum="kullanicida", bildirim=metin)
        self.bildir(metin, {"tip": "soru", "soru_id": soru_id, "ajan": olay["ajan"],
                            "session_id": olay.get("session_id")})

    def _baslat(self, ajan, istek):
        try:
            self.gorev_baslat(ajan, **istek)
        except Exception as e:  # noqa: BLE001
            if getattr(e, "kod", None) == 409:
                sorular.devam_birak(ajan, istek)  # ajan meşgul: koşusu bitince başlar
            else:
                self.bildir(f"⚠ {ajan} devam ettirilemedi: {e}", None)

    # ---------- iş parçacığı ----------

    def _ofset_yolu(self):
        return os.path.join(ortak.DURUM_DIZINI, "izleyici-ofset.json")

    def _ofset_oku(self):
        try:
            with open(self._ofset_yolu(), encoding="utf-8") as f:
                return int(json.load(f)["ofset"])
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
            # İlk açılış: geçmiş olaylara tepki verilmez, dosyanın sonundan başlanır.
            return os.path.getsize(ortak.OLAYLAR) if os.path.exists(ortak.OLAYLAR) else 0

    def _ofset_yaz(self, ofset):
        gecici = self._ofset_yolu() + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({"ofset": ofset}, f)
        os.replace(gecici, self._ofset_yolu())

    def tur(self, ofset):
        """Yeni tam satırları işler, yeni ofseti döndürür."""
        boyut = os.path.getsize(ortak.OLAYLAR) if os.path.exists(ortak.OLAYLAR) else 0
        if boyut < ofset:
            ofset = 0  # dosya silinip yeniden oluşmuş
        if boyut == ofset:
            return ofset
        with open(ortak.OLAYLAR, "rb") as f:
            f.seek(ofset)
            parca = f.read(boyut - ofset)
        son = parca.rfind(b"\n")
        if son < 0:
            return ofset
        for satir in parca[:son].splitlines():
            try:
                olay = json.loads(satir.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            try:
                self.olay_isle(olay)
            except Exception as e:  # noqa: BLE001 — tek olay izleyiciyi düşürmez
                sys.stderr.write(f"izleyici: olay işlenemedi ({type(e).__name__}: {e})\n")
        ofset += son + 1
        self._ofset_yaz(ofset)
        return ofset

    def dongu(self):
        ofset = self._ofset_oku()
        while True:
            try:
                ofset = self.tur(ofset)
                self.kuyruk_isle()
            except OSError as e:
                sys.stderr.write(f"izleyici: {type(e).__name__}: {e}\n")
                time.sleep(10)
            time.sleep(ARALIK_SN)

    def baslat(self):
        threading.Thread(target=self.dongu, name="olay-izleyici", daemon=True).start()
