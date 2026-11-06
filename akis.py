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
from datetime import datetime

import ortak
import projeler
import sorular
import toplanti

OTOMATIK_SINIR = 3
CEVAPLAYAN = {"ceo-zaman-asimi": "CEO, 1 saat dolunca", "kullanici-web": "web", "kullanici-telegram": "Telegram"}
TELEGRAM_KAYNAKLARI = ("telegram", "telegram-ceo")
ARALIK_SN = 1.0
PERIYOT_SN = 30  # 1 saat kuralı ve toplantı zamanlayıcısı bu aralıkla bakılır
ZAMAN_ASIMI_SN = 3600
BAYAT_SN = 24 * 3600  # bundan eski sorular (ör. sürüm yükseltmeden kalma) otomatik cevaplanmaz, kullanıcıyı bekler
GUVENLI_CEVAP = ("Kullanıcı 1 saat içinde cevap vermedi. Güvenli taraf: para harcatan, ücretli servis ekleyen, "
                 "büyük değişiklik ya da yeni entegrasyon gerektiren, yayın/mail/ödeme yapan yolu SEÇME. Bu kısmı "
                 "yapmadan, ücretsiz ve geri alınabilir yolla işin geri kalanına devam et; atladığın kısmı çıktında "
                 "açıkça yaz.")
TOPLANTI_ZAMAN_ASIMI_NOTU = "Kullanıcı 1 saat içinde cevap vermedi; bu konuda güvenli/varsayılan yolla devam edilecek."


class Izleyici:
    def __init__(self, gorev_baslat, triyaj, bildir=None, mesgul_mu=ortak.ajan_mesgul, ceo_calistir=None,
                 zaman_asimi_cevabi=None, zamanlayici=None):
        self.gorev_baslat = gorev_baslat
        self.mesgul_mu = mesgul_mu
        self.triyaj = triyaj
        self.bildir = bildir or (lambda metin, hedef: None)  # Telegram bağlanınca atanır
        self.ceo_calistir = ceo_calistir
        self.zaman_asimi_cevabi = zaman_asimi_cevabi or (lambda ajan, soru, baglam: None)
        self.zamanlayici = zamanlayici

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
        """→ "basladi" | "kuyruk" | "hata"."""
        try:
            self.gorev_baslat(ajan, **istek)
            return "basladi"
        except Exception as e:  # noqa: BLE001
            if getattr(e, "kod", None) == 409:
                sorular.devam_birak(ajan, istek)  # ajan meşgul: koşusu bitince başlar
                return "kuyruk"
            self.bildir(f"⚠ {ajan} devam ettirilemedi: {e}", None)
            return "hata"

    # ---------- soruların tek cevap yolu (Telegram, web, 1 saat kuralı) ----------

    def soru_cevapla(self, soru_id, cevap, kaynak):
        """kaynak: kullanici-telegram | kullanici-web | ceo-zaman-asimi. Kullanıcıya gösterilecek kısa metin döner."""
        s = sorular.soru_al(soru_id)
        if not s:
            return "Böyle bir soru yok."
        if not sorular.cevap_kilitle(soru_id, cevap, kaynak):
            s = sorular.soru_al(soru_id)
            kim = "CEO" if s.get("durum") == "ceo" else CEVAPLAYAN.get(s.get("cevaplayan"), "Telegram")
            hedef = "ajana" if s.get("ajan") == "ceo" else s.get("ajan")
            return (f"Bu soru zaten cevaplandı ({kim}): {s.get('cevap') or ''}. "
                    f"Fikrin değiştiyse @{hedef} ile yeni iş ver.")
        telegram = kaynak == "kullanici-telegram"
        tur = s.get("kaynak")
        if tur == "bitti_mi":
            return self._bitti_mi_cevabi(s, cevap)
        if tur == "toplanti":
            return self._toplanti_cevabi(s, cevap, kaynak, telegram)
        ajan, session_id = s["ajan"], s.get("session_id")
        kullanici = kaynak.startswith("kullanici")
        if session_id:
            (sorular.otomatik_sifirla if kullanici else sorular.otomatik_artir)(session_id)
        run_kaynak = "telegram" if telegram else "arayuz"
        if not session_id and not kullanici:
            return "Sürdürülecek oturum yok; ajan başlatılmadı."  # bağlamsız yeni koşu tokensız iş değildir
        if not session_id:  # sürdürülecek oturum yok: aynı ajana yeni görev
            sonuc = self._baslat(ajan, {"prompt": cevap, "kaynak": run_kaynak})
        else:
            sonuc = self._baslat(ajan, {"kaynak": run_kaynak, "devam": {
                "session_id": session_id, "cevap": cevap, "cevap_kaynak": "kullanici" if kullanici else "ceo"}})
        if sonuc == "kuyruk":
            return f"⏳ {ajan} şu an meşgul; elindeki iş bitince cevabınla devam edecek."
        if sonuc == "hata":
            return f"⚠ {ajan} devam ettirilemedi."
        return f"▶ {ajan} cevabınla devam ediyor."

    def _bitti_mi_cevabi(self, s, cevap):
        p = projeler.al(s.get("proje_id")) or {}
        baslik = p.get("baslik") or "proje"
        try:
            if projeler.evet_mi(cevap):
                projeler.onayla(s.get("proje_id"))
                return f"✅ '{baslik}' kapandı."
            projeler.reddet(s.get("proje_id"), cevap)
            return f"↩ '{baslik}' açık kaldı; notun CEO'ya iletildi."
        except ValueError as e:
            return f"⚠ {e}"

    def _toplanti_cevabi(self, s, cevap, kaynak, telegram):
        proje_id = s.get("proje_id")
        try:
            projeler.not_ekle(proje_id, cevap, "kullanici" if kaynak.startswith("kullanici") else "ceo")
        except ValueError:
            pass  # proje kapanmış/silinmiş: cevap yine CEO'ya gider
        if not self.ceo_calistir:
            return "Cevabın projeye not olarak eklendi."
        try:
            r = self.ceo_calistir(cevap, kaynak="telegram" if telegram else "arayuz", onceki_cevap=s.get("soru"))
        except Exception as e:  # noqa: BLE001 — IstekHatasi dahil
            return f"Cevabın projeye not olarak eklendi; CEO şu an çalışamadı: {e}"
        for b in r.get("baslatilan") or []:
            if b.get("kosu_id"):  # akşam toplantısı bu koşuyu projeye bağlar
                toplanti.eslesme_ekle(b["kosu_id"], proje_id, None)
        satirlar = [r.get("cevap") or ""]
        satirlar += [f"▶ {b['ajan']} başladı" for b in r.get("baslatilan") or []]
        satirlar += [f"✗ {x.get('ajan')}: {x.get('neden')}" for x in r.get("reddedilen") or []]
        return "\n".join(x for x in satirlar if x)

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
        son_periyot = 0.0
        while True:
            try:
                ofset = self.tur(ofset)
                self.kuyruk_isle()
            except OSError as e:
                sys.stderr.write(f"izleyici: {type(e).__name__}: {e}\n")
                time.sleep(10)
            if time.time() - son_periyot >= PERIYOT_SN:
                son_periyot = time.time()
                for islev in (self.zaman_asimi_isle, self.zamanlayici):
                    try:
                        if islev:
                            islev()
                    except Exception as e:  # noqa: BLE001 — izleyici düşmez
                        sys.stderr.write(f"izleyici: periyodik iş ({type(e).__name__}: {e})\n")
            time.sleep(ARALIK_SN)

    # ---------- 1 saat kuralı ----------

    def zaman_asimi_isle(self, simdi_ts=None):
        """Kullanıcıya gidip 1 saat cevapsız kalan soruları CEO cevaplar (önemli türlerde sabit güvenli cevap)."""
        simdi = time.time() if simdi_ts is None else simdi_ts
        for s in sorular.bekleyen_sorular():
            try:
                yas = simdi - datetime.fromisoformat(s.get("zaman") or "").timestamp()
            except (TypeError, ValueError):
                continue
            if yas < ZAMAN_ASIMI_SN or yas > BAYAT_SN or s.get("kaynak") == "bitti_mi":
                continue  # "bitti mi?" yalnız kullanıcının kararı
            sid, ajan, session_id = s["soru_id"], s.get("ajan"), s.get("session_id")
            if s.get("kaynak") == "toplanti":
                if not sorular.cevap_kilitle(sid, TOPLANTI_ZAMAN_ASIMI_NOTU, "ceo-zaman-asimi"):
                    continue
                try:
                    projeler.not_ekle(s.get("proje_id"), TOPLANTI_ZAMAN_ASIMI_NOTU, "ceo")
                except ValueError:
                    pass
                cevap = TOPLANTI_ZAMAN_ASIMI_NOTU
                kim = f"CEO'nun sorusu ({(projeler.al(s.get('proje_id')) or {}).get('baslik', 'proje')})"
            else:
                if session_id and sorular.otomatik_sayi(session_id) >= OTOMATIK_SINIR:
                    if not s.get("sinir_bildirildi"):
                        sorular.soru_guncelle(sid, sinir_bildirildi=True)
                        self.bildir(f"⏸ {ajan} {OTOMATIK_SINIR} kez otomatik cevap aldı; devam için senin "
                                    "cevabın gerekiyor", {"tip": "soru", "soru_id": sid, "ajan": ajan,
                                                         "session_id": session_id})
                    continue
                cevap = None
                if s.get("tur") == "diger":
                    try:
                        cevap = self.zaman_asimi_cevabi(ajan, s.get("soru") or "", s.get("bildirim") or "")
                    except Exception:  # noqa: BLE001
                        cevap = None
                cevap = cevap or GUVENLI_CEVAP
                self.soru_cevapla(sid, cevap, "ceo-zaman-asimi")
                if (sorular.soru_al(sid) or {}).get("cevaplayan") != "ceo-zaman-asimi":
                    continue  # bu arada kullanıcı cevapladı
                kim = f"{ajan} sorusuna"
            sorular.karar_ekle({"ajan": ajan, "soru": s.get("soru"), "cevap": cevap, "gerekce": "1 saat cevap yok",
                                "kosu_id": s.get("kosu_id"), "session_id": session_id})
            self.bildir(f"⏱ {kim} 1 saat içinde cevap gelmedi, CEO cevapladı: {cevap}", None)

    def baslat(self):
        threading.Thread(target=self.dongu, name="olay-izleyici", daemon=True).start()
