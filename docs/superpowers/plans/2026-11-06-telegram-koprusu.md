# Telegram Köprüsü Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcı Telegram'dan CEO'ya / `@ajan`'a yazar; ajan soruları önce CEO triyajından geçer, önemliyse
Telegram'a gelir; cevapla ajan aynı Claude Code oturumunu sürdürür; aksilikler anında, CEO kararları gün sonunda
Telegram'a gider.

**Architecture:** `kosucu.py` `<soru>` bloğunu ve `session_id`'yi olaya yazar. `sorular.py` tüm kalıcı durumu
(sorular, kararlar, mesaj eşlemesi, devam kuyruğu, rapor) tutar. `akis.py` `olaylar.jsonl`'i izleyip triyaj ve
bildirimleri yapar (Telegram'dan bağımsız). `telegram.py` Bot API istemcisi, long polling, yönlendirme, gün sonu
raporu ve web paneli yöneticisidir (`Yonetici`). `sunucu.py` bunları başlatır ve CEO/triyaj çağrılarını sağlar.

**Tech Stack:** Python 3.10+ yalnız stdlib (`urllib.request`, `json`, `threading`, `re`), Claude Code CLI
(`claude -p`, `--resume`, `--json-schema`), Telegram Bot API (`getUpdates`, `sendMessage`).

**Spec:** `docs/superpowers/specs/2026-11-06-telegram-koprusu-design.md`

## Global Constraints

- Yalnız Python standart kütüphanesi; yeni bağımlılık yok. pytest yok: testler `test_ofis.py` içinde düz `assert`
  fonksiyonları, `python test_ofis.py` hepsini koşar ve `OK` basar.
- Windows ve Linux/macOS'ta çalışır. Mevcut dosyaların satır sonu (CRLF) korunur.
- Sunucu yalnız `127.0.0.1`; Telegram'a yalnız dışa long polling (`getUpdates`, `timeout=50`), webhook yok.
- Boşta 0 token: long polling ve rapor model çağırmaz.
- Girdi en fazla `ortak.MAKS_GIRDI` (4000) karakter; Telegram mesajı en fazla 4096 karakter, `parse_mode`
  kullanılmaz (düz metin).
- Bot token'ı hiçbir log, olay ya da çıktıya yazılmaz (hata mesajlarında URL basılmaz).
- Prompt shell'e string olarak birleşmez; `claude`'a stdin'den, `encoding="utf-8"` ile gider.
- Yalnız eşleşmiş `OFIS_TELEGRAM_KULLANICI` kimliğinden gelen mesajlar işlenir; tek istisna geçerli
  `/baslat <kod>` (6 hane, tek kullanımlık, 10 dakika, yalnız bellekte).
- Telegram web panelinden yönetilir; panel `.env`'deki yalnız `OFIS_TELEGRAM_*` satırlarını yazar. Token
  tarayıcıya geri gönderilmez (yalnız son 4 karakter). Değişiklik sunucu yeniden başlamadan uygulanır.
- Uygulama GitHub'da herkese açık dağıtılır: tüm kullanıcı metinleri Türkçe, kurulum `.env` düzenlemeden
  panelden yapılabilir.
- CEO aynı `session_id` için en fazla 3 otomatik cevap verir; 4. soru kullanıcıya gider.
- `<soru>` etiketinde `tur` `diger` değilse ya da eksik/bozuksa soru CEO'ya sorulmadan kullanıcıya gider.

## Review Focus

1. **Ajan meşgulken cevap** (kullanıcı ya da CEO cevabı geldiğinde ajan başka koşuda) → cevap kaybolmamalı,
   `devam_birak` ile kuyruğa girip koşu bitince başlamalı. Test: Task 5 `test_mesgul_ajana_devam_kuyruga`.
2. **Ağ yok / token yanlış (401)** → bot iş parçacığı sunucuyu düşürmemeli, logu boğmamalı (geri çekilme),
   ağ gelince devam etmeli. Test: Task 6 `test_api_hatasi_dongu_dusurmez`.
3. **Uzun ya da özel karakterli çıktı** (>4096, `*_[`) → Telegram 400 vermemeli; kısaltılır, sona çıktı yolu
   eklenir. Test: Task 6 `test_kisalt_4096`.
4. **Bilinmeyen ya da kurulmamış `@ajan`** → CEO'ya düşmemeli; kullanıcıya hata cevabı. Test: Task 6
   `test_yonlendir_bilinmeyen_ajan`.
5. **Bozuk `<soru>`** (tur yok, iki blok, boş) → güvenli taraf: kullanıcıya. Test: Task 2
   `test_soru_ayikla_bozuk`.

---

### Task 1: `.env` okuma ve Telegram ayarı

`.env.example` ve `.gitignore` istisnası zaten oluşturuldu (bu plandan önce); bu task yalnız okumayı ekler.

**Files:**
- Modify: `ortak.py` (sona ekle)
- Create: `test_ofis.py`

**Interfaces:**
- Produces: `ortak.env_oku(yol: str | None = None) -> dict[str, str]` (varsayılan `os.path.join(KOK, ".env")`;
  dosya yoksa `{}`; `#` ve boş satırlar atlanır; değerin etrafındaki tek/çift tırnak soyulur).
- Produces: `ortak.env_yaz(guncel: dict[str, str | None], yol: str | None = None) -> None` — verilen
  anahtarların satırlarını günceller (yoksa sona ekler), değeri `None` olanları siler; diğer satırlar ve
  yorumlar aynen kalır; `.tmp` + `os.replace` ile yazar.
- Produces: `ortak.telegram_ayari(yol: str | None = None) -> dict | None` →
  `{"token": str, "kullanici": int | None, "rapor_saati": (saat: int, dakika: int)}`; ortam değişkeni `.env`'i
  ezer; token boşsa `None`; `kullanici` boş/sayı değilse `None`; rapor saati bozuk/boşsa `(18, 0)`.

- [ ] **Step 1: Write the failing tests** (`test_ofis.py`, sonunda `if __name__ == "__main__":` tüm `test_*`
  fonksiyonlarını sırayla çağırıp `OK` basar)

```python
def test_env_oku(tmp):
    yol = os.path.join(tmp, ".env")
    open(yol, "w", encoding="utf-8").write('# yorum\n\nA=1\nB="iki"\nC = üç \n')
    assert ortak.env_oku(yol) == {"A": "1", "B": "iki", "C": "üç"}
    assert ortak.env_oku(os.path.join(tmp, "yok")) == {}

def test_telegram_ayari(tmp):
    yol = os.path.join(tmp, ".env")
    open(yol, "w", encoding="utf-8").write("OFIS_TELEGRAM_TOKEN=\n")
    assert ortak.telegram_ayari(yol) is None
    open(yol, "w", encoding="utf-8").write("OFIS_TELEGRAM_TOKEN=t\nOFIS_TELEGRAM_KULLANICI=42\nOFIS_TELEGRAM_RAPOR_SAATI=9:5x\n")
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
```

  Test koşucusu her teste `tempfile.mkdtemp()` ile yeni `tmp` verir ve `ortak.DURUM_DIZINI`'ni
  `os.path.join(tmp, "durum")` yapar (Task 3+ testleri buna dayanır).

- [ ] **Step 2: Run** `python test_ofis.py` → FAIL (`AttributeError: env_oku`)
- [ ] **Step 3: Implement** `env_oku`, `env_yaz` ve `telegram_ayari` in `ortak.py`
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`
- [ ] **Step 5: Commit** `git add ortak.py test_ofis.py .env.example .gitignore && git commit -m "feat: .env ve Telegram ayarı okuma"`

---

### Task 2: Koşucu — `<soru>`, `session_id`, sürdürme

**Files:**
- Modify: `kosucu.py` (`GOREV_SABLONU`, `komut_kur`, `kos`, `bitir`; yeni `soru_ayikla`, `DEVAM_SABLONU`)
- Modify: `test_ofis.py`

**Interfaces:**
- Produces: `kosucu.SORU_TURLERI = ("maliyet", "buyuk-degisiklik", "yayin-mail-para", "diger")`
- Produces: `kosucu.soru_ayikla(metin: str) -> dict | None` → `{"soru": str, "tur": str}`; blok yoksa `None`;
  `tur` geçerli değilse ya da eksikse `"eksik"`; birden çok blok varsa sorular `\n` ile birleşir ve
  `tur` `"eksik"` olur; boş blok `None` sayılmaz → `{"soru": "", "tur": "eksik"}`.
- Produces: `komut_kur(ajan, genel_yasak, cikti_dizini, devam_session: str | None = None) -> list[str]`:
  `--no-session-persistence` kaldırılır; `devam_session` varsa `["--resume", devam_session]` eklenir.
- Produces: argüman dosyasında isteğe bağlı `"devam": {"session_id": str, "cevap": str, "cevap_kaynak": "kullanici"|"ceo"}`.
  Varsa prompt `DEVAM_SABLONU`'dur (görev şablonu ve hafıza tekrar verilmez):

```
Kullanıcının/CEO'nun sorduğun soruya cevabı aşağıda. Bu cevaba göre işine kaldığın yerden devam et.
<cevap kaynak="{kaynak}">
{cevap}
</cevap>
Bitiriş kuralları aynı: kısa cevap, gerekirse yeni <soru> ya da <hafiza_ekle>.
```

- Produces: `kosu_bitti` olayına ek alanlar: `session_id` (result'taki `session_id`), `kaynak` (argümandan),
  `soru` (str | None), `soru_tur` (str | None). Çıktı dosyası ve `ozet` `<soru>` bloğundan temizlenir; soru
  metni çıktı dosyasının sonuna `\n\n**Soru:** …` olarak eklenir.
- Produces: soru varsa `durum/<ajan>.json` → `{"durum": "cevap_bekliyor", "soru": …, "soru_tur": …,
  "session_id": …, …bugünkü bitti alanları}`.
- `GOREV_SABLONU`'nun "Bitiriş" bölümüne eklenecek metin (aynen):

```
Kullanıcının kararı gereken bir noktaya geldiysen (onay, seçim, belirsizlik) işi orada bırak ve en sona
<soru tur="maliyet|buyuk-degisiklik|yayin-mail-para|diger">tek, açık soru</soru> yaz. tur: para/ücretli servis/
token artışı → maliyet; yeni entegrasyon, mimari ya da modül değişikliği → buyuk-degisiklik; yayın, mail, ödeme →
yayin-mail-para; diğerleri → diger. Soru yoksa bu bloğu yazma.
```

- [ ] **Step 1: Write the failing tests**

```python
def test_soru_ayikla():
    assert kosucu.soru_ayikla("bitti") is None
    assert kosucu.soru_ayikla('x <soru tur="diger">Plan uygun mu?</soru>') == {"soru": "Plan uygun mu?", "tur": "diger"}
    assert kosucu.soru_ayikla('<soru tur="maliyet">SMS?</soru>')["tur"] == "maliyet"

def test_soru_ayikla_bozuk():
    assert kosucu.soru_ayikla("<soru>tur yok</soru>")["tur"] == "eksik"
    assert kosucu.soru_ayikla('<soru tur="uydurma">a</soru>')["tur"] == "eksik"
    iki = kosucu.soru_ayikla('<soru tur="diger">a</soru><soru tur="diger">b</soru>')
    assert iki == {"soru": "a\nb", "tur": "eksik"}

def test_komut_kur_devam():
    ajan = {"model": "haiku", "cwd": ".", "izinli_araclar": []}
    k = kosucu.komut_kur(ajan, [], "cikti")
    assert "--no-session-persistence" not in k and "--resume" not in k
    k = kosucu.komut_kur(ajan, [], "cikti", devam_session="abc")
    assert k[k.index("--resume") + 1] == "abc"
```

- [ ] **Step 2: Run** `python test_ofis.py` → FAIL
- [ ] **Step 3: Implement** `soru_ayikla`, `komut_kur` değişikliği, `DEVAM_SABLONU`, şablon metni, `kos`/`bitir` alanları
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`
- [ ] **Step 5: Manual check** `sunucu.py`'yi açıp bir ajana `"Bir dosya adı öner ve uygun mu diye <soru tur=\"diger\"> ile sor."`
  görevi ver; `olaylar.jsonl`'deki `kosu_bitti` satırında `session_id` ve `soru` dolu, `durum/<ajan>.json`
  `cevap_bekliyor` olmalı.
- [ ] **Step 6: Commit** `git commit -am "feat: koşucu soru bloğu ve oturum sürdürme"`

---

### Task 3: `sorular.py` — kalıcı durum

**Files:**
- Create: `sorular.py`
- Modify: `test_ofis.py`

**Interfaces:** (her fonksiyon yolları çağrı anında `ortak.DURUM_DIZINI`'nden kurar; modül içi tek
`threading.Lock`; yazma `ortak.durum_yaz` gibi `.tmp` + `os.replace`)
- `soru_ekle(ajan: str, kosu_id: str, session_id: str, soru: str, tur: str) -> str` (soru_id = kosu_id);
  durum `"yeni"`.
- `soru_al(soru_id) -> dict | None`, `soru_guncelle(soru_id, **alanlar) -> None`
- `bekleyen_sorular() -> list[dict]` (durum `"kullanicida"` olanlar, her biri `soru_id` alanıyla)
- `otomatik_sayi(session_id) -> int`, `otomatik_artir(session_id) -> int`, `otomatik_sifirla(session_id) -> None`
  (`durum/sorular.json` → `{"sorular": {...}, "otomatik": {session_id: n}}`)
- `karar_ekle(kayit: dict) -> None` → `durum/kararlar.jsonl`'e `{"zaman": ortak.simdi_iso(), **kayit}`; kayıt
  alanları: `ajan, soru, cevap, gerekce, kosu_id, session_id`.
- `mesaj_esle(mesaj_id: int, hedef: dict) -> None`, `mesaj_hedefi(mesaj_id: int) -> dict | None`
  (`durum/telegram-mesajlar.json`, en son 500 kayıt tutulur). Hedef tipleri:
  `{"tip": "soru", "soru_id", "ajan", "session_id"}`, `{"tip": "kosu", "ajan", "session_id", "kosu_id"}`,
  `{"tip": "ceo", "cevap"}`, `{"tip": "rapor", "maddeler": [{"ajan", "session_id", "kosu_id"}]}`.
- `devam_birak(ajan: str, istek: dict) -> None`, `devam_al(ajan: str) -> dict | None` (alır ve siler; ajan başına
  tek kayıt, yenisi eskisini ezer) — `durum/devam-kuyrugu.json`. `istek` = `gorev_baslat` kwargs'ı.
- `rapor_derle() -> tuple[str | None, list[dict]]`: `durum/rapor-son.json`'daki `zaman`'dan sonraki kararlar;
  karar yoksa `(None, [])`; varsa numaralı düz metin (`1. <ajan>: <soru> → <cevap> (<gerekce>)`, her madde en
  fazla 300 karakter) ve madde hedefleri.
- `rapor_isaretle(zaman_iso: str) -> None`, `son_rapor_zamani() -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_soru_kaydi():
    sid = sorular.soru_ekle("yazar", "k1", "s1", "Uygun mu?", "diger")
    sorular.soru_guncelle(sid, durum="kullanicida")
    assert [s["soru_id"] for s in sorular.bekleyen_sorular()] == ["k1"]
    assert sorular.otomatik_artir("s1") == 1 and sorular.otomatik_artir("s1") == 2
    sorular.otomatik_sifirla("s1"); assert sorular.otomatik_sayi("s1") == 0

def test_mesaj_esleme_sinir():
    for i in range(510):
        sorular.mesaj_esle(i, {"tip": "ceo", "cevap": str(i)})
    assert sorular.mesaj_hedefi(5) is None and sorular.mesaj_hedefi(509)["cevap"] == "509"

def test_devam_kuyrugu():
    sorular.devam_birak("yazar", {"a": 1}); sorular.devam_birak("yazar", {"a": 2})
    assert sorular.devam_al("yazar") == {"a": 2} and sorular.devam_al("yazar") is None

def test_rapor_derle():
    assert sorular.rapor_derle() == (None, [])
    sorular.karar_ekle({"ajan": "yazar", "soru": "S", "cevap": "C", "gerekce": "G", "kosu_id": "k", "session_id": "s"})
    metin, maddeler = sorular.rapor_derle()
    assert metin.startswith("1. yazar: S → C") and maddeler == [{"ajan": "yazar", "session_id": "s", "kosu_id": "k"}]
    sorular.rapor_isaretle(ortak.simdi_iso())
    assert sorular.rapor_derle() == (None, [])
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** `sorular.py` · **Step 4: Run** → `OK`
- [ ] **Step 5: Commit** `git add sorular.py test_ofis.py && git commit -m "feat: soru/karar/mesaj kalıcı durumu"`

---

### Task 4: Sunucu — sürdürme, ofis durumu, CEO triyajı

**Files:**
- Modify: `sunucu.py`
- Modify: `test_ofis.py`

**Interfaces:**
- Consumes: Task 2 argüman `devam` alanı; Task 3 `bekleyen_sorular`, kararlar dosyası.
- Produces: `gorev_baslat(ajan_id, etiket=None, prompt=None, kaynak="buton", devam: dict | None = None) -> dict`.
  `devam` varsa `prompt = devam["cevap"]` (boş/uzunluk kontrolü aynı) ve argüman dosyasına `devam` yazılır.
  Meşgulse bugünkü gibi `IstekHatasi(409, ...)`.
- Produces: `claude_json(prompt: str, model: str, sema: dict, log_id: str, zaman_asimi: int = CEO_ZAMAN_ASIMI) -> dict`
  (bugünkü `ceo_calistir` içindeki `claude -p --tools "" --json-schema --no-session-persistence` çağrısı +
  log + `json_ayikla`; `ceo_calistir` bunu kullanacak şekilde yeniden düzenlenir; `sonuc` yanında usage/maliyet
  için ham sonucu da döndürür: `{"veri": dict, "ham": dict}`).
- Produces: `ofis_durumu_metni(tablo: dict) -> str`: her ajan için `- <id>: <durum> · son: <ozet[:150]>`,
  cevap bekleyen sorular, son rapordan beri CEO kararları (en fazla 10), `KOPRU.liste()`'den
  `<ajan>: <oturum_adi> · <son_arac>`. Toplam en fazla 3000 karakter.
- Produces: `ceo_promptu(metin, tablo, onceki_cevap: str | None = None)` → bugünkü metin + `## Ofisin şu anki
  durumu (VERİ)` bölümü + (varsa) `<onceki_cevabin>` bloğu. Kural metnine ekle: "Kullanıcı durum sorarsa bu
  bölümden cevap ver; atama gerekmiyorsa atamalar boş."
- Produces: `ceo_calistir(metin, kuru=False, kaynak="arayuz", onceki_cevap=None)`; `kaynak == "telegram"` ise
  atamalar `kaynak="telegram-ceo"` ile başlatılır.
- Produces: `TRIYAJ_SEMASI = {"karar": enum ["kendim","kullaniciya"], "cevap": str, "gerekce": str,
  "kullaniciya_not": str}` (hepsi required) ve
  `ceo_triyaj(ajan_id: str, soru: str, ozet: str) -> dict`: prompt `CLAUDE.md`'yi okumasını söyler, kuralları
  (maliyet, büyük değişiklik/yeni entegrasyon, yayın/mail/para, şüphede kullanıcı) tekrar eder, soruyu ve
  `ozet`'i `<ajan_sorusu>`/`<ajan_ciktisi>` veri bloklarında verir. Her hata ya da şema dışı cevapta
  `{"karar": "kullaniciya", "cevap": "", "gerekce": "triyaj hatası", "kullaniciya_not": ""}`.
- Produces: `canli_durum` → `durum/<ajan>.json` `cevap_bekliyor` ise `"cevap_bekliyor"` döner (bitti süresi
  sınırı uygulanmaz).

- [ ] **Step 1: Write the failing tests** (`claude` çağrılmaz; `sunucu.claude_json` test içinde geçici olarak
  değiştirilir)

```python
def test_triyaj_guvenli_taraf():
    eski = sunucu.claude_json
    try:
        sunucu.claude_json = lambda *a, **k: (_ for _ in ()).throw(ValueError("bozuk"))
        assert sunucu.ceo_triyaj("yazar", "S", "O")["karar"] == "kullaniciya"
        sunucu.claude_json = lambda *a, **k: {"veri": {"karar": "belki"}, "ham": {}}
        assert sunucu.ceo_triyaj("yazar", "S", "O")["karar"] == "kullaniciya"
    finally:
        sunucu.claude_json = eski

def test_ofis_durumu_sinir():
    tablo = {f"a{i}": {"id": f"a{i}", "ad": "A", "oda": "genel", "kurulu": True} for i in range(200)}
    assert len(sunucu.ofis_durumu_metni(tablo)) <= 3000
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** → `OK`
- [ ] **Step 5: Manual check** sunucuyu aç, arayüzden CEO'ya "şu an kim ne yapıyor?" yaz → cevap ajan
  durumlarını anlatmalı, atama olmamalı.
- [ ] **Step 6: Commit** `git commit -am "feat: CEO ofis durumu, triyaj ve sürdürmeli görev"`

---

### Task 5: `akis.py` — olay izleyici (triyaj ve bildirim)

**Files:**
- Create: `akis.py`
- Modify: `sunucu.py` (`main()` içinde `akis.Izleyici(...).baslat()`)
- Modify: `test_ofis.py`

**Interfaces:**
- Consumes: `sorular.*` (Task 3), `sunucu.gorev_baslat`, `sunucu.ceo_triyaj`, `sunucu.IstekHatasi` (Task 4).
- Produces: `class Izleyici(gorev_baslat, triyaj, bildir)`; `bildir(metin: str, hedef: dict | None) -> None`
  (Telegram yoksa no-op; Task 6 bağlar). `Izleyici.bildir` sonradan atanabilir alandır.
- Produces: `Izleyici.olay_isle(olay: dict) -> None` (test edilebilir çekirdek) ve `Izleyici.baslat()`
  (iş parçacığı; `olaylar.jsonl`'i ofsetle izler, ofset `durum/izleyici-ofset.json`'da; ilk açılışta dosya
  sonundan başlar; 1 sn aralık; hata sunucuyu düşürmez).
- `olay_isle` kuralları (`tur == "kosu_bitti"`):
  1. `devam_al(ajan)` doluysa `gorev_baslat(**istek)`.
  2. `durum == "hata"` → `bildir("⚠ <ajan> hata: <hata>", {"tip": "kosu", ...})`.
  3. `soru` varsa: `soru_ekle`; `tur != "diger"` ya da `otomatik_sayi(session_id) >= 3` → kullanıcıya; aksi
     halde `triyaj(ajan, soru, ozet)`. `kendim` → `karar_ekle`, `otomatik_artir`, `soru_guncelle(durum="ceo")`,
     `gorev_baslat(ajan, kaynak=<olaydaki kaynak>, devam={"session_id", "cevap", "cevap_kaynak": "ceo"})`
     (409 → `devam_birak`). Kullanıcıya → `soru_guncelle(durum="kullanicida")`, `bildir("❓ <ajan> soruyor:
     <soru>\n\nCEO notu: <not>\n\n<ozet>", {"tip": "soru", ...})`.
  4. Soru yok, başarılı ve `kaynak in ("telegram", "telegram-ceo")` → `bildir("✓ <ajan> bitti: <ozet>",
     {"tip": "kosu", ...})`.
  `tur == "ceo_bitti"` ve `durum == "hata"` → `bildir("⚠ CEO plan çıkaramadı: <hata>", None)`.

- [ ] **Step 1: Write the failing tests** (sahte `gorev_baslat`/`triyaj`/`bildir` listeye yazar)

```python
def test_onemli_soru_triyajsiz_kullaniciya(): ...   # soru_tur="maliyet" → triyaj çağrılmaz, bildir 1 kez, tip "soru"
def test_diger_soru_ceo_kendim(): ...               # triyaj kendim → gorev_baslat devam cevap_kaynak "ceo", kararlar.jsonl 1 satır
def test_otomatik_sinir_3(): ...                    # aynı session için otomatik_sayi=3 → triyaj çağrılmaz, kullanıcıya
def test_mesgul_ajana_devam_kuyruga(): ...          # gorev_baslat 409 atar → devam_al(ajan) dolu; sonraki kosu_bitti onu başlatır
def test_hata_bildirilir_arayuz_sonucu_bildirilmez(): ...  # kaynak "buton" başarılı → bildir yok; durum hata → bildir var
```

  Her testte beklenen çağrılar `assert cagrilar == [...]` ile tam liste olarak doğrulanır.

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** → `OK`
- [ ] **Step 5: Commit** `git add akis.py sunucu.py test_ofis.py && git commit -m "feat: soru triyajı ve bildirim izleyicisi"`

---

### Task 6: `telegram.py` — bot, yönlendirme, rapor

**Files:**
- Create: `telegram.py`
- Modify: `sunucu.py` (`main()`: `TELEGRAM = telegram.Yonetici(gorev_baslat, ceo_calistir)`;
  `izleyici.bildir = TELEGRAM.bildir`; `TELEGRAM.baslat()` — token yoksa bot başlamaz, "Telegram kapalı" loglanır)
- Modify: `test_ofis.py`

**Interfaces:**
- Consumes: `sorular.*`, `sunucu.gorev_baslat`, `sunucu.ceo_calistir`, `sunucu.IstekHatasi`, `ortak.ajanlari_yukle`.
- Produces: `kisalt(metin: str, sinir: int = 4096, ek: str = "") -> str` (sığmıyorsa kesip `…\n<ek>` ekler,
  sonuç ≤ sinir).
- Produces: `yonlendir(metin: str, yanit_hedefi: dict | None, tablo: dict) -> dict` — saf fonksiyon:
  - `^/baslat\s+(\d{6})$` → `{"tip": "eslestir", "kod": "<6 hane>"}`
  - `yanit_hedefi` tip `soru`/`kosu` → `{"tip": "devam", "ajan", "session_id", "cevap": metin, "soru_id"?}`
  - tip `rapor` ve metin `^\s*(\d+)\s+(.+)` → o maddeye `devam`; numarasız → `ceo`
  - tip `ceo` → `{"tip": "ceo", "metin", "onceki_cevap": hedef["cevap"]}`
  - `^@([a-z0-9-]{1,40})\s+(.+)` → ajan tabloda ve kurulu ise `{"tip": "ajan", "ajan", "prompt"}`, değilse
    `{"tip": "hata", "mesaj": "bilinmeyen ya da kurulmamış ajan: @<id>"}`; `@ceo ...` → `ceo`
  - diğer → `{"tip": "ceo", "metin": metin, "onceki_cevap": None}`
- Produces: `rapor_zamani_mi(simdi: datetime, rapor_saati: tuple[int, int], son_rapor_iso: str | None) -> bool`
  (bugünün rapor anı geçtiyse ve son rapor o andan önceyse/yoksa True).
- Produces: `class Api(token)`: `cagir(metod: str, **param) -> dict` (`urllib`, JSON POST, `timeout=param
  timeout+10`; hata mesajında URL/token yok), `guncellemeler(ofset: int) -> list`, `gonder(chat_id, metin,
  yanit_id=None) -> int` (message_id; `kisalt` uygulanır).
- Produces: `class Yonetici(gorev_baslat, ceo_calistir)`: botun yaşam döngüsü; `baslat()` (`.env`'den ayar okur,
  token varsa Bot'u başlatır), `yeniden_baslat()` (eski iş parçacığını bir `threading.Event` ile bitirir,
  yenisini açar), `bildir(metin, hedef)` (bot yoksa no-op). Task 7 bunu genişletir.
- Produces: `class Bot(ayar, api, gorev_baslat, ceo_calistir)`: `bildir(metin, hedef)` (gönderir, hedef varsa
  `mesaj_esle`), `isle(guncelleme: dict) -> None`, `tur() -> None` (bir polling turu + rapor kontrolü),
  `baslat()` (iş parçacığı; ofset `durum/telegram-ofset.json`; açılışta `bekleyen_sorular()` içinde
  `telegram_mesaj_id`'si olmayanları gönderir; hata olursa 5→10→…→300 sn geri çekilme, aynı hata tipi bir kez
  loglanır).
- Produces: eşleştirme: `Bot.kod_uret() -> dict` (`{"kod": "482913", "bitis_ts": float}`, `secrets.randbelow`,
  10 dk; yenisi eskisini geçersiz kılar); `isle` içinde `eslestir` tipi, kod geçerli ve süresi dolmamışsa
  `ortak.env_yaz({"OFIS_TELEGRAM_KULLANICI": str(from.id)})`, `ayar["kullanici"]` ve `kullanici_adi`
  (first_name) güncellenir, kod silinir, "✓ Eşleşti" cevabı gider; yanlış kod → yok sayılır.
- `isle` davranışı: eşleşmemiş `from.id` → yok say (yalnız geçerli `/baslat <kod>` işlenir); `devam` →
  `otomatik_sifirla`, `soru_guncelle(durum="cevaplandi")` (soru_id varsa), `gorev_baslat(ajan, kaynak="telegram",
  devam={…, "cevap_kaynak": "kullanici"})`, 409 → `devam_birak` + "ajan meşgul, bitince devam edecek";
  `ajan` → `gorev_baslat(ajan, prompt=..., kaynak="telegram")` + "▶ <ajan> başladı"; `ceo` →
  `ceo_calistir(metin, kaynak="telegram", onceki_cevap=...)` → cevap + başlatılan/reddedilen listesi, hedef
  `{"tip": "ceo", "cevap"}`; `IstekHatasi` → mesajı kullanıcıya.
- Rapor: `tur()` sonunda `rapor_zamani_mi` True ise `rapor_derle()`; metin varsa
  `"📋 CEO kararları\n\n" + metin + "\n\nBir maddeye cevap için: Yanıtla → '<no> mesaj'"` gönderilir, hedef
  `{"tip": "rapor", "maddeler"}`; her durumda `rapor_isaretle(simdi)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_kisalt_4096():
    m = telegram.kisalt("*_[" * 3000, ek="cikti/x.md")
    assert len(m) <= 4096 and m.endswith("cikti/x.md")

def test_yonlendir():
    t = {"yazar": {"id": "yazar", "kurulu": True}, "eski": {"id": "eski", "kurulu": False}}
    assert telegram.yonlendir("ne yapıyorsunuz?", None, t)["tip"] == "ceo"
    assert telegram.yonlendir("@yazar taslak yaz", None, t) == {"tip": "ajan", "ajan": "yazar", "prompt": "taslak yaz"}
    assert telegram.yonlendir("onaylıyorum", {"tip": "soru", "soru_id": "k", "ajan": "yazar", "session_id": "s"}, t)["tip"] == "devam"
    r = {"tip": "rapor", "maddeler": [{"ajan": "yazar", "session_id": "s", "kosu_id": "k"}]}
    assert telegram.yonlendir("1 geri al", r, t)["session_id"] == "s"
    assert telegram.yonlendir("genel yorum", r, t)["tip"] == "ceo"

def test_yonlendir_bilinmeyen_ajan():
    t = {"eski": {"id": "eski", "kurulu": False}}
    assert telegram.yonlendir("@yok selam", None, t)["tip"] == "hata"
    assert telegram.yonlendir("@eski selam", None, t)["tip"] == "hata"

def test_rapor_zamani_mi():
    s = datetime(2026, 11, 6, 18, 1)
    assert telegram.rapor_zamani_mi(s, (18, 0), None)
    assert not telegram.rapor_zamani_mi(s, (18, 0), "2026-11-06T18:00:30+03:00")
    assert not telegram.rapor_zamani_mi(datetime(2026, 11, 6, 17, 59), (18, 0), None)

def test_yetkisiz_kullanici(): ...        # sahte api; from.id != kullanici → gorev_baslat/ceo çağrılmaz, gonder çağrılmaz
def test_eslestirme(): ...               # kod_uret; '/baslat <yanlış>' → yok say; doğru kod → kullanici kaydedilir,
                                          # kod tek kullanımlık; bitis_ts geçmişse doğru kod da reddedilir
def test_api_hatasi_dongu_dusurmez(): ... # api.guncellemeler OSError atar → bot.tur() istisna fırlatmaz, bekleme > 0
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** → `OK`
- [ ] **Step 5: Manual check** (gerçek bot): `.env`'e token yaz, sunucuyu aç, Python'dan `kod_uret()` ile kod
  al, bota `/baslat <kod>` yaz → "Eşleşti"; "ne üzerinde çalışıyorsunuz?" → CEO cevabı; `@<ajan> küçük bir dosya adı öner ve
  <soru tur="maliyet"> ile onay iste` → soru Telegram'a gelir; "Yanıtla → onaylıyorum" → ajan aynı oturumla
  devam eder, sonuç Telegram'a gelir.
- [ ] **Step 6: Commit** `git add telegram.py sunucu.py test_ofis.py && git commit -m "feat: Telegram botu, yönlendirme ve gün sonu raporu"`

---

### Task 7: Telegram paneli (web arayüzü)

**Files:**
- Modify: `telegram.py` (`Yonetici`'ye panel metotları)
- Modify: `sunucu.py` (`GET/POST /api/telegram`)
- Modify: `on-yuz/index.html` (üst çubuğa "Telegram" düğmesi + panel)
- Modify: `test_ofis.py`

**Interfaces:**
- Consumes: Task 1 `env_yaz`/`telegram_ayari`, Task 6 `Api`, `Bot.kod_uret`, `Yonetici.yeniden_baslat`.
- Produces: `Yonetici.durum() -> dict` → `{"durum": "kapali"|"gecersiz"|"eslesme_bekliyor"|"bagli",
  "bot": "@ad"|None, "token_son4": str|None, "kullanici_adi": str|None, "rapor_saati": "SS:DD",
  "son_hata": str|None, "kod": str|None, "kod_kalan_sn": int|None, "ortamdan": bool}` (token asla yok).
- Produces: `Yonetici.islem(veri: dict) -> dict` (sonuç `durum()`), hatada `ValueError(<Türkçe mesaj>)`:
  - `token`: `veri["token"]` `^\d+:[A-Za-z0-9_-]{30,}$` değilse hata; `Api(token).cagir("getMe")` başarısızsa
    "Token geçersiz" (kaydetmez); başarılıysa `env_yaz({"OFIS_TELEGRAM_TOKEN": token,
    "OFIS_TELEGRAM_KULLANICI": None})`, `yeniden_baslat()`, otomatik `kod_uret()`.
  - `kod`: bot yoksa hata; `kod_uret()`.
  - `rapor_saati`: `^([01]\d|2[0-3]):[0-5]\d$` değilse hata; `env_yaz`.
  - `test`: eşleşme yoksa hata; eşleşen hesaba "Ajan Ofisi test mesajı ✓".
  - `kaldir`: `env_yaz` ile üç `OFIS_TELEGRAM_*` silinir, bot durur.
  - `ortamdan` True iken `token`/`kaldir` → hata "ortam değişkeninden geliyor, panelden değiştirilemez".
- Produces: `GET /api/telegram` → `durum()`; `POST /api/telegram` → 200 `islem()` / 400 `{"hata"}`.
- Panel (ön yüz): mevcut panel stilini kullanır; durum rozeti, bot adı, token girişi (`type="password"`,
  kaydedilince temizlenir), eşleştirme kodu büyük yazıyla + "Bota `/baslat <kod>` yazın" + geri sayım,
  eşleşmiş hesap adı, rapor saati (`<input type="time">`), "Test mesajı gönder", "Bağlantıyı kaldır"
  (onay sorar). Eşleşme beklenirken `GET /api/telegram` 3 sn'de bir sorulur; başka zaman yalnız panel açılınca.
  Metinler `textContent` ile basılır. `?demo=1`'de panel "demo modunda kapalı" der, istek atmaz.

- [ ] **Step 1: Write the failing tests** (sahte `Api`: `cagir("getMe")` sonucu testte belirlenir)

```python
def test_panel_token_dogrulama(tmp): ...   # bozuk biçim → ValueError; getMe hata → ValueError ve .env değişmez;
                                           # getMe ok → .env'de token var, durum()["durum"] == "eslesme_bekliyor", "kod" 6 hane
def test_panel_durum_token_sizdirmaz(tmp): ...  # json.dumps(durum()) içinde token geçmez; token_son4 == token[-4:]
def test_panel_rapor_saati(tmp): ...       # "25:00" → ValueError; "07:30" → .env OFIS_TELEGRAM_RAPOR_SAATI=07:30
def test_panel_kaldir(tmp): ...            # kaldir → .env'de OFIS_TELEGRAM_* yok, durum "kapali"
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** `Yonetici.durum/islem`, uçlar, panel · **Step 4: Run** → `OK`
- [ ] **Step 5: Manual check** (gerçek bot): `.env` olmadan sunucuyu aç → panel "kapalı"; token yapıştır → bot adı
  görünür ve kod çıkar; bota `/baslat <kod>` → panel 3 sn içinde "Eşleşti: <ad>"; "Test mesajı gönder" →
  telefona gelir; "Bağlantıyı kaldır" → bot cevap vermez. Spec'teki uçtan uca senaryo (CEO durumu, `@ajan`
  sorusu, Yanıtla ile onay) çalışır.
- [ ] **Step 6: Commit** `git commit -am "feat: Telegram web paneli ve eşleştirme kodu"`

---

### Task 8: Anayasa, arayüz, belgeler

**Files:**
- Modify: `CLAUDE.md` ("Sınırlar" altına "Karar yetkisi" bölümü)
- Modify: `on-yuz/index.html` (`kosu_bitti` işleyicisi ~satır 1217; sunucu durum eşlemesi ~satır 1430)
- Modify: `README.md` (Telegram bölümü + API tablosuna değişiklik yok)

**Interfaces:**
- Consumes: `kosu_bitti.soru`, `/api/ajanlar` `durum == "cevap_bekliyor"`.

- [ ] **Step 1: `CLAUDE.md`** — eklenecek bölüm (aynen):

```
## Karar yetkisi (ajan soruları)
Ajan soruları önce CEO'ya gelir. CEO yalnız küçük, geri alınabilir, maliyetsiz konularda kendisi karar verir
(dosya sırası, isimlendirme, küçük düzeltmenin yöntemi, test yazımı gibi). Şunlar HER ZAMAN kullanıcıya gider:
- Maliyete dokunan her şey: ücretli servis/API, abonelik, ek sunucu, token/model kullanımını belirgin artıran iş.
- Modüllerde büyük değişiklik: yeni entegrasyon (SMS, ödeme, yeni dış servis), mimari değişiklik, modülü baştan
  yazma, veri yapısı değişikliği.
- Yayın, mail gönderme, para.
Emin değilsen kullanıcıya sor. Kendi verdiğin her karar gün sonu raporunda kullanıcıya gider.
```

- [ ] **Step 2: Ön yüz** — `kosu_bitti` olayında `o.soru` varsa `sonOzet = '❓ ' + temizMetin(o.soru)`; sunucu
  durumu `cevap_bekliyor` gelirse ajan `bitti` gibi gösterilir ve ekranda `CEVAP BEKLİYOR` yazar.
- [ ] **Step 3: README** — "Telegram köprüsü" bölümü: kurulum (BotFather → paneldeki token kutusu →
  `/baslat <kod>`; isteyene `.env` alternatifi), yönlendirme
  (`@ajan`, Yanıtla, CEO), karar yetkisi, gün sonu raporu, kapalıyken gelen mesajlar otomatik işlenir,
  güvenlik (yalnız tek kullanıcı, token `.env`'de). Dosyalar tablosuna `telegram.py`, `akis.py`, `sorular.py`,
  `test_ofis.py`, `.env.example`.
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`; tarayıcıda `?demo=1` hâlâ çalışır.
- [ ] **Step 5: Commit** `git commit -am "docs: karar yetkisi, Telegram README, arayüzde cevap bekliyor"`
