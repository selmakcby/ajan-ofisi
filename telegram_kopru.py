"""Telegram köprüsü: Bot API istemcisi, long polling, yönlendirme, eşleştirme ve gün sonu raporu.

Yalnız stdlib. Dışa doğru long polling (getUpdates, timeout=50): açık port, webhook yok; dinlemek 0 token.
Yalnız eşleşmiş hesabın mesajları işlenir; tek istisna geçerli "/baslat <kod>".
Token hiçbir log, olay ya da hata mesajına yazılmaz.
(Dosya adı "telegram.py" değil: kurulu python-telegram-bot paketiyle çakışmasın.)
"""
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

import ortak
import sorular

TELEGRAM_SINIR = 4000          # Telegram 4096 karakter (UTF-16) sayar; emoji payı bırakılır
POLL_SN = 50
KOD_SURE_SN = 600
MAKS_BEKLEME = 300
AJAN_DESENI = re.compile(r"^@([a-z0-9-]{1,40})\s+(.+)$", re.S)
RAPOR_MADDE = re.compile(r"^\s*(\d+)\s+(.+)$", re.S)
ESLESTIR = re.compile(r"^/baslat\s+(\d{6})$")
TOKEN_DESENI = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")
PANEL_SAAT = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class TelegramHatasi(Exception):
    def __init__(self, mesaj, kod=None):
        super().__init__(mesaj)
        self.kod = kod


def kisalt(metin, sinir=TELEGRAM_SINIR, ek=""):
    if len(metin) <= sinir:
        return metin
    kuyruk = "…\n" + ek if ek else "…"
    return metin[:sinir - len(kuyruk)] + kuyruk


def yonlendir(metin, yanit_hedefi, tablo):
    """Gelen metni nereye gideceğine çevirir (saf fonksiyon)."""
    metin = metin.strip()
    e = ESLESTIR.match(metin)
    if e:
        return {"tip": "eslestir", "kod": e.group(1)}
    h = yanit_hedefi or {}
    if h.get("tip") in ("soru", "kosu"):
        if not h.get("session_id"):  # sürdürülecek oturum yok: aynı ajana yeni görev
            return {"tip": "ajan", "ajan": h["ajan"], "prompt": metin}
        y = {"tip": "devam", "ajan": h["ajan"], "session_id": h["session_id"], "cevap": metin}
        return {**y, "soru_id": h["soru_id"]} if h.get("soru_id") else y
    if h.get("tip") == "rapor":
        e = RAPOR_MADDE.match(metin)
        if e:
            maddeler = h.get("maddeler") or []
            no = int(e.group(1))
            if not 1 <= no <= len(maddeler):
                return {"tip": "hata", "mesaj": f"raporda {no}. madde yok"}
            return yonlendir(e.group(2), {"tip": "kosu", **maddeler[no - 1]}, tablo)
    if h.get("tip") == "ceo":
        return {"tip": "ceo", "metin": metin, "onceki_cevap": h.get("cevap")}
    e = AJAN_DESENI.match(metin)
    if e:
        ajan, prompt = e.group(1), e.group(2).strip()
        if ajan == "ceo":
            return {"tip": "ceo", "metin": prompt, "onceki_cevap": None}
        if not (tablo.get(ajan) or {}).get("kurulu"):
            return {"tip": "hata", "mesaj": f"bilinmeyen ya da kurulmamış ajan: @{ajan}"}
        return {"tip": "ajan", "ajan": ajan, "prompt": prompt}
    return {"tip": "ceo", "metin": metin, "onceki_cevap": None}


def rapor_zamani_mi(simdi, rapor_saati, son_rapor_iso):
    """Bugünün rapor anı geçti ve o andan sonra rapor gönderilmedi mi?"""
    an = simdi.replace(hour=rapor_saati[0], minute=rapor_saati[1], second=0, microsecond=0)
    if simdi < an:
        return False
    if not son_rapor_iso:
        return True
    son = datetime.fromisoformat(son_rapor_iso)
    if son.tzinfo:
        son = son.astimezone().replace(tzinfo=None)
    return son < an


class Api:
    def __init__(self, token):
        self._url = f"https://api.telegram.org/bot{token}/"

    def cagir(self, metod, **param):
        istek = urllib.request.Request(self._url + metod, data=json.dumps(param).encode("utf-8"),
                                       headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(istek, timeout=param.get("timeout", 0) + 15) as r:
                veri = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                veri = json.loads(e.read())
            except (ValueError, OSError):
                raise TelegramHatasi(f"HTTP {e.code}", e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            # `from None`: zincirde token'lı URL taşıyan istisna kalmasın
            raise TelegramHatasi(f"bağlantı hatası ({type(e).__name__})") from None
        if not veri.get("ok"):
            raise TelegramHatasi(veri.get("description") or "bilinmeyen Telegram hatası", veri.get("error_code"))
        return veri.get("result")

    def guncellemeler(self, ofset):
        return self.cagir("getUpdates", offset=ofset, timeout=POLL_SN, allowed_updates=["message"]) or []

    def gonder(self, chat_id, metin, yanit_id=None):
        param = {"chat_id": chat_id, "text": kisalt(metin)}  # parse_mode yok: düz metin, özel karakter sorunu yok
        if yanit_id:
            param["reply_parameters"] = {"message_id": yanit_id, "allow_sending_without_reply": True}
        return self.cagir("sendMessage", **param)["message_id"]


class Bot:
    def __init__(self, ayar, api, gorev_baslat, ceo_calistir, env_yolu=None):
        self.ayar = dict(ayar)
        self.api = api
        self.gorev_baslat = gorev_baslat
        self.ceo_calistir = ceo_calistir
        self.env_yolu = env_yolu
        self.bot_id = str(ayar["token"]).split(":", 1)[0]
        self.kod = None
        self.kullanici_adi = None
        self.bekleme = 0
        self.son_hata = None
        self.son_hata_kod = None
        self._loglanan = None
        self.ofset = self._ofset_oku()

    # ---------- kalıcı ofset (bot başına; kapalıyken gelenler açılışta sırayla işlenir) ----------

    def _ofset_yolu(self):
        return os.path.join(ortak.DURUM_DIZINI, "telegram-ofset.json")

    def _ofset_oku(self):
        try:
            with open(self._ofset_yolu(), encoding="utf-8") as f:
                v = json.load(f)
            return int(v["ofset"]) if v.get("bot") == self.bot_id else 0
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
            return 0

    def _ofset_yaz(self):
        os.makedirs(ortak.DURUM_DIZINI, exist_ok=True)
        gecici = self._ofset_yolu() + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({"bot": self.bot_id, "ofset": self.ofset}, f)
        os.replace(gecici, self._ofset_yolu())

    # ---------- gönderme ----------

    def bildir(self, metin, hedef=None):
        """Eşleşmiş hesaba mesaj; hedef varsa Yanıtla eşlemesi kaydedilir. Telegram hatası çağıranı düşürmez."""
        if not self.ayar.get("kullanici"):
            return None
        try:
            mid = self.api.gonder(self.ayar["kullanici"], metin)
        except Exception as e:  # noqa: BLE001
            self._hata_kaydet(e)
            return None
        if hedef:
            sorular.mesaj_esle(mid, hedef)
            if hedef.get("tip") == "soru" and hedef.get("soru_id"):
                sorular.soru_guncelle(hedef["soru_id"], telegram_mesaj_id=mid)
        return mid

    def bekleyenleri_gonder(self):
        """Telegram kapalıyken kullanıcıya yükseltilmiş sorular (henüz gönderilmemiş olanlar)."""
        for s in sorular.bekleyen_sorular():
            if not s.get("telegram_mesaj_id") and s.get("bildirim"):
                self.bildir(s["bildirim"], {"tip": "soru", "soru_id": s["soru_id"], "ajan": s["ajan"],
                                            "session_id": s.get("session_id")})

    def _cevapla(self, mesaj, metin, hedef=None):
        mid = self.api.gonder(mesaj["chat"]["id"], metin, yanit_id=mesaj.get("message_id"))
        if hedef:
            sorular.mesaj_esle(mid, hedef)
        return mid

    # ---------- eşleştirme ----------

    def kod_uret(self):
        self.kod = {"kod": f"{secrets.randbelow(10 ** 6):06d}", "bitis_ts": time.time() + KOD_SURE_SN}
        return dict(self.kod)

    def _eslestir(self, kod, mesaj):
        k = self.kod
        if not k or time.time() > k["bitis_ts"] or not secrets.compare_digest(kod, k["kod"]):
            return  # yanlış/süresi geçmiş kod: sessizce yok sayılır
        self.kod = None
        kimlik = mesaj["from"]["id"]
        ortak.env_yaz({"OFIS_TELEGRAM_KULLANICI": str(kimlik)}, self.env_yolu)
        self.ayar["kullanici"] = kimlik
        self.kullanici_adi = mesaj["from"].get("first_name") or str(kimlik)
        self._cevapla(mesaj, "✓ Eşleşti. Bundan sonra ofise buradan yazabilirsin.\n"
                             "@ajan ile başlarsan doğrudan o ajana, yoksa CEO'ya gider. "
                             "Bir mesaja Yanıtla ile cevap verirsen o işe devam edilir.")
        self.bekleyenleri_gonder()

    # ---------- gelen mesaj ----------

    def isle(self, guncelleme):
        mesaj = guncelleme.get("message") or {}
        metin = (mesaj.get("text") or "").strip()
        if not metin or not mesaj.get("from") or not mesaj.get("chat"):
            return
        yanit = mesaj.get("reply_to_message")
        hedef = sorular.mesaj_hedefi(yanit["message_id"]) if yanit else None
        _, tablo = ortak.ajanlari_yukle()
        y = yonlendir(metin, hedef, tablo)
        if y["tip"] == "eslestir":
            return self._eslestir(y["kod"], mesaj)
        if not self.ayar.get("kullanici") or mesaj["from"]["id"] != self.ayar["kullanici"]:
            return  # eşleşmemiş hesap: hiçbir şey yapılmaz, cevap da verilmez
        if len(metin) > ortak.MAKS_GIRDI:
            return self._cevapla(mesaj, f"Mesaj en fazla {ortak.MAKS_GIRDI} karakter olabilir.")
        try:
            if y["tip"] == "hata":
                self._cevapla(mesaj, "⚠ " + y["mesaj"])
            elif y["tip"] == "ajan":
                b = self.gorev_baslat(y["ajan"], prompt=y["prompt"], kaynak="telegram")
                self._cevapla(mesaj, f"▶ {y['ajan']} başladı. Bitince buraya yazacağım.",
                              {"tip": "kosu", "ajan": y["ajan"], "session_id": None, "kosu_id": b.get("kosu_id")})
            elif y["tip"] == "devam":
                self._devam(mesaj, y)
            else:
                self._ceo(mesaj, y)
        except Exception as e:  # noqa: BLE001 — IstekHatasi dahil: kullanıcıya kısa açıklama
            self._cevapla(mesaj, f"⚠ {e}")

    def _devam(self, mesaj, y):
        sorular.otomatik_sifirla(y["session_id"])  # kullanıcı cevap verdi: CEO döngü sayacı sıfırlanır
        if y.get("soru_id"):
            sorular.soru_guncelle(y["soru_id"], durum="cevaplandi", cevap=y["cevap"])
        istek = {"kaynak": "telegram",
                 "devam": {"session_id": y["session_id"], "cevap": y["cevap"], "cevap_kaynak": "kullanici"}}
        try:
            self.gorev_baslat(y["ajan"], **istek)
            self._cevapla(mesaj, f"▶ {y['ajan']} cevabınla devam ediyor.")
        except Exception as e:  # noqa: BLE001
            if getattr(e, "kod", None) != 409:
                raise
            sorular.devam_birak(y["ajan"], istek)
            self._cevapla(mesaj, f"⏳ {y['ajan']} şu an meşgul; elindeki iş bitince cevabınla devam edecek.")

    def _ceo(self, mesaj, y):
        try:
            self.api.cagir("sendChatAction", chat_id=mesaj["chat"]["id"], action="typing")
        except Exception:  # noqa: BLE001 — "yazıyor…" göstergesi olmasa da olur
            pass
        s = self.ceo_calistir(y["metin"], kaynak="telegram", onceki_cevap=y.get("onceki_cevap"))
        satirlar = [s.get("cevap") or ""]
        satirlar += [f"▶ {b['ajan']} başladı" for b in s.get("baslatilan") or []]
        satirlar += [f"✗ {r.get('ajan')}: {r.get('neden')}" for r in s.get("reddedilen") or []]
        self._cevapla(mesaj, "\n".join(x for x in satirlar if x), {"tip": "ceo", "cevap": s.get("cevap")})

    # ---------- döngü ----------

    def _hata_kaydet(self, e):
        self.son_hata = str(e)[:200]
        self.son_hata_kod = getattr(e, "kod", None)
        if type(e).__name__ + self.son_hata != self._loglanan:  # aynı hata logu boğmasın
            self._loglanan = type(e).__name__ + self.son_hata
            sys.stderr.write(f"telegram: {type(e).__name__}: {self.son_hata}\n")

    def tur(self):
        """Bir long polling turu + gün sonu raporu kontrolü. İstisna fırlatmaz."""
        try:
            for g in self.api.guncellemeler(self.ofset + 1 if self.ofset else 0):
                self.ofset = g["update_id"]
                self._ofset_yaz()  # önce ofset: çökse bile aynı mesaj iki kez koşu başlatmaz
                try:
                    self.isle(g)
                except Exception as e:  # noqa: BLE001
                    sys.stderr.write(f"telegram: mesaj işlenemedi ({type(e).__name__}: {e})\n")
            self.bekleme, self.son_hata, self.son_hata_kod, self._loglanan = 0, None, None, None
        except Exception as e:  # noqa: BLE001 — ağ yok, token geçersiz…: geri çekil
            self._hata_kaydet(e)
            self.bekleme = min(max(5, self.bekleme * 2), MAKS_BEKLEME)
        try:
            self._rapor()
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"telegram: rapor gönderilemedi ({type(e).__name__})\n")

    def _rapor(self):
        if not self.ayar.get("kullanici"):
            return
        if not rapor_zamani_mi(datetime.now(), self.ayar["rapor_saati"], sorular.son_rapor_zamani()):
            return
        metin, maddeler = sorular.rapor_derle()
        if metin:
            mid = self.bildir("📋 CEO'nun bugünkü kararları\n\n" + metin +
                              "\n\nBir maddeye dönmek için bu mesajı Yanıtla: '<no> mesajın'",
                              {"tip": "rapor", "maddeler": maddeler})
            if mid is None:
                return  # gönderilemedi: işaretleme, sonra yeniden denenir
        sorular.rapor_isaretle(ortak.simdi_iso())

    def dongu(self, dur):
        try:
            self.bekleyenleri_gonder()
        except Exception:  # noqa: BLE001
            pass
        while not dur.is_set():
            self.tur()
            if self.bekleme:
                dur.wait(self.bekleme)


class Yonetici:
    """Botun yaşam döngüsü: .env'den başlatır, panelden değişince yeniden başlatır."""

    def __init__(self, gorev_baslat, ceo_calistir, env_yolu=None, api_sinifi=Api):
        self.gorev_baslat = gorev_baslat
        self.ceo_calistir = ceo_calistir
        self.env_yolu = env_yolu
        self.api_sinifi = api_sinifi
        self.bot = None
        self._dur = None
        self.kilit = threading.RLock()

    def baslat(self):
        with self.kilit:
            ayar = ortak.telegram_ayari(self.env_yolu)
            if not ayar:
                sys.stderr.write("Telegram kapalı (token yok). Arayüzdeki Telegram panelinden bağlanabilirsin.\n")
                return
            self.bot = Bot(ayar, self.api_sinifi(ayar["token"]), self.gorev_baslat, self.ceo_calistir,
                           self.env_yolu)
            self._dur = threading.Event()
            threading.Thread(target=self.bot.dongu, args=(self._dur,), name="telegram", daemon=True).start()

    def durdur(self):
        with self.kilit:
            if self._dur:
                self._dur.set()  # eski iş parçacığı en geç long polling süresi sonunda çıkar
            self.bot, self._dur = None, None

    def yeniden_baslat(self):
        with self.kilit:
            self.durdur()
            self.baslat()

    def bildir(self, metin, hedef=None):
        bot = self.bot
        return bot.bildir(metin, hedef) if bot else None

    # ---------- web paneli ----------

    def _ortamdan(self):
        return bool(os.environ.get("OFIS_TELEGRAM_TOKEN"))

    def durum(self):
        """Panel için durum. Token ASLA dönmez (yalnız son 4 karakter)."""
        ayar = ortak.telegram_ayari(self.env_yolu)
        bot = self.bot
        d = {"durum": "kapali", "bot": None, "token_son4": None, "kullanici_adi": None,
             "rapor_saati": "%02d:%02d" % (ayar["rapor_saati"] if ayar else (18, 0)),
             "son_hata": None, "kod": None, "kod_kalan_sn": None, "ortamdan": self._ortamdan()}
        if not ayar:
            return d
        d["token_son4"] = ayar["token"][-4:]
        if not bot:
            return {**d, "durum": "gecersiz", "son_hata": "bot başlatılamadı"}
        if getattr(bot, "bot_adi", None) is None:
            try:
                bot.bot_adi = "@" + bot.api.cagir("getMe")["username"]
            except Exception as e:  # noqa: BLE001
                bot._hata_kaydet(e)
        if bot.ayar.get("kullanici") and not bot.kullanici_adi:
            try:
                bot.kullanici_adi = bot.api.cagir("getChat", chat_id=bot.ayar["kullanici"]).get("first_name")
            except Exception:  # noqa: BLE001
                bot.kullanici_adi = str(bot.ayar["kullanici"])
        kalan = int(bot.kod["bitis_ts"] - time.time()) if bot.kod else 0
        if bot.son_hata_kod in (401, 404):
            durum = "gecersiz"
        else:
            durum = "bagli" if bot.ayar.get("kullanici") else "eslesme_bekliyor"
        return {**d, "durum": durum, "bot": getattr(bot, "bot_adi", None), "kullanici_adi": bot.kullanici_adi,
                "son_hata": bot.son_hata, "kod": bot.kod["kod"] if kalan > 0 else None,
                "kod_kalan_sn": kalan if kalan > 0 else None}

    def islem(self, veri):
        """Panel işlemi; hata → ValueError (kullanıcıya gösterilecek Türkçe mesaj). Sonuç: durum()."""
        islem = veri.get("islem")
        with self.kilit:
            if islem == "token":
                if self._ortamdan():
                    raise ValueError("Token ortam değişkeninden geliyor, panelden değiştirilemez.")
                token = str(veri.get("token") or "").strip()
                if not TOKEN_DESENI.match(token):
                    raise ValueError("Bu bir bot token'ına benzemiyor. BotFather'ın verdiği "
                                     "'123456:ABC…' biçimindeki metni yapıştır.")
                try:
                    ben = self.api_sinifi(token).cagir("getMe")
                except Exception as e:  # noqa: BLE001
                    raise ValueError(f"Telegram bu token'ı kabul etmedi ({e}).") from None
                ortak.env_yaz({"OFIS_TELEGRAM_TOKEN": token, "OFIS_TELEGRAM_KULLANICI": None}, self.env_yolu)
                self.yeniden_baslat()
                if self.bot:
                    self.bot.bot_adi = "@" + (ben or {}).get("username", "")
                    self.bot.kod_uret()
            elif islem == "kod":
                if not self.bot:
                    raise ValueError("Önce bot token'ını gir.")
                self.bot.kod_uret()
            elif islem == "rapor_saati":
                saat = str(veri.get("rapor_saati") or "")
                e = PANEL_SAAT.match(saat)
                if not e:
                    raise ValueError("Saat SS:DD biçiminde olmalı (ör. 18:00).")
                ortak.env_yaz({"OFIS_TELEGRAM_RAPOR_SAATI": saat}, self.env_yolu)
                if self.bot:
                    self.bot.ayar["rapor_saati"] = (int(e.group(1)), int(e.group(2)))
            elif islem == "test":
                if not self.bot or not self.bot.ayar.get("kullanici"):
                    raise ValueError("Önce Telegram hesabını eşleştir.")
                if self.bot.bildir("Ajan Ofisi test mesajı ✓") is None:
                    raise ValueError(f"Mesaj gönderilemedi: {self.bot.son_hata}")
            elif islem == "kaldir":
                if self._ortamdan():
                    raise ValueError("Token ortam değişkeninden geliyor, panelden kaldırılamaz.")
                ortak.env_yaz({"OFIS_TELEGRAM_TOKEN": None, "OFIS_TELEGRAM_KULLANICI": None,
                               "OFIS_TELEGRAM_RAPOR_SAATI": None}, self.env_yolu)
                self.durdur()
            else:
                raise ValueError("bilinmeyen işlem")
        return self.durum()
