# İlk Kurulum, Giriş ve Ajan Yönetimi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** İlk açılışta kurulum sihirbazı (ad → hesap → ajanlar/şablon → ofise gir), her açılışta giriş, ve
tarayıcıdan ajan/oda ekleme-düzenleme-silme ile 7 sektör şablonu.

**Architecture:** `hesap.py` şifre özeti, oturumlar ve kaba kuvvet beklemesini; `ajan_yonetimi.py`
`ajanlar.json` üzerinde doğrulanmış ekle/güncelle/sil, oda işlemleri ve şablondan eklemeyi yapar. `sunucu.py`
tüm `/api/*` uçlarını oturum kapısının arkasına alır ve yeni uçları açar. Ön yüz, modülün en başında
`/api/oturum`'a bakar; gerekirse giriş/sihirbaz katmanını gösterir ve iş bitince sayfayı yeniden yükler.

**Tech Stack:** Python 3.10+ stdlib (`hashlib.scrypt`, `secrets`, `hmac`, `http.cookies`), vanilla JS
(`on-yuz/index.html`), JSON şablonlar.

**Spec:** `docs/superpowers/specs/2026-11-06-kurulum-ajan-yonetimi-design.md`

## Global Constraints

- Yalnız Python standart kütüphanesi; testler `test_ofis.py` (düz `assert`, `python test_ofis.py` → `OK`).
- Windows ve Linux/macOS. Mevcut satır sonları korunur. Temel dal `telegram-koprusu`.
- Sunucu yalnız `127.0.0.1`; mevcut Host/Origin denetimi sürer, giriş onun üstüne eklenir.
- Girişsiz açık olanlar yalnız: statik dosyalar, `GET/POST /api/oturum`, `POST /api/kurulum` (adım kuralları
  içeride). Diğer tüm `/api/*` (SSE ve `/api/telegram` dahil) oturumsuz → 401.
- Şifre: `hashlib.scrypt` n=16384, r=8, p=1, dklen=32, 16 bayt tuz; karşılaştırma `hmac.compare_digest`.
  Şifre en az 8 karakter; kullanıcı adı `^[\w.-]{3,40}$`.
- Oturum çerezi: `ofis_oturum=<token>; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000` (30 gün); sunucuda
  yalnız token'ın sha256 özeti saklanır. `Secure` yok (B'de).
- Kaba kuvvet: genel sayaç; 5 hatadan sonra bekleme 2, 4, 8 … en çok 300 sn; bekleme sürerken 429.
- `hesap.json`, `oturumlar.json` `durum/` altında, izin 0600 (`ortak.ENV_IZIN`).
- `ajanlar.json` yazımı: kilit + doğrulama + `ajanlar.json.bak` + `.tmp` + `os.replace`; ≤ 60 ajan, prompt
  ≤ 4000 (`ortak.MAKS_GIRDI`).
- CEO silinemez; çalışan ajan silinemez (409). `varsayilan_yasak_araclar` arayüzden kaldırılamaz ve
  koşucu her koşuda ekler.
- Göreli `cwd` `ortak.KOK`'a göre çözülür; boş `cwd` → `calisma/<id>` (oluşturulur; `calisma/` gitignore'da).
- Demo modu (`?demo=1`) girişsiz ve arka uçsuz çalışmaya devam eder.

## Review Focus

1. **Mevcut kurulumun yükseltilmesi** (ajanlar.json var, hesap yok) → hiçbir ajan/oda/ayar kaybolmaz,
   sihirbaz dolu gelir. Test: Task 4 `test_mevcut_kurulum_korunur`.
2. **Süresi dolmuş/bozuk/silinmiş oturum çerezi** → 401 ve ön yüz giriş ekranına döner, istisna yok. Test:
   Task 1 `test_oturum_suresi_dolar`, Task 4 `test_bozuk_cerez_401`.
3. **Türkçe/garip ajan adları** ("Şeyma'nın Asistanı", "!!!", aynı ad iki kez) → geçerli, çakışmasız id.
   Test: Task 2 `test_id_turet`.
4. **Bozuk istek ya da elle bozulmuş ajanlar.json** → doğrulama hatası 400, dosya değişmez; okunamayan dosyada
   sunucu düşmez. Test: Task 2 `test_gecersiz_kayit_dosyayi_degistirmez`.
5. **Silinen ajana sonradan gelen iş** (Telegram Yanıtla, kuyruktaki devam, hazır görev düğmesi) → 404, çökme
   yok. Test: Task 5 `test_silinen_ajana_gorev_404`.

---

### Task 1: `hesap.py` — şifre, oturum, kaba kuvvet

**Files:** Create `hesap.py`; Modify `test_ofis.py`

**Interfaces:**
- Produces (yollar çağrı anında `ortak.DURUM_DIZINI`'nden):
  - `hesap_var() -> bool`
  - `hesap_olustur(kullanici_adi: str, sifre: str) -> None` — zaten varsa ya da kural dışıysa `ValueError(<Türkçe>)`
  - `dogrula(kullanici_adi: str, sifre: str) -> bool`
  - `kullanici_adi() -> str | None`
  - `sifre_sifirla(yeni: str) -> None` — kural denetimi + tüm oturumları siler
  - `oturum_ac() -> str` (ham token, `secrets.token_urlsafe(32)`), `oturum_gecerli(token: str | None) -> bool`,
    `oturum_kapat(token: str | None) -> None`, `OTURUM_SN = 30 * 86400`
  - `giris_bekleme() -> int` (kalan sn), `giris_hatasi() -> None`, `giris_basarili() -> None` (bellek içi sayaç)

- [ ] **Step 1: Write the failing tests**

```python
def test_hesap_olustur_dogrula():
    import hesap
    assert not hesap.hesap_var()
    for ad, sifre in (("ab", "12345678"), ("ramazan", "kisa"), ("a b c", "12345678")):
        try:
            hesap.hesap_olustur(ad, sifre); raise AssertionError((ad, sifre))
        except ValueError:
            pass
    hesap.hesap_olustur("ramazan", "gizli-sifre-1")
    assert hesap.hesap_var() and hesap.kullanici_adi() == "ramazan"
    assert hesap.dogrula("ramazan", "gizli-sifre-1") and not hesap.dogrula("ramazan", "yanlis-sifre")
    assert not hesap.dogrula("baskasi", "gizli-sifre-1")
    assert "gizli-sifre-1" not in open(os.path.join(ortak.DURUM_DIZINI, "hesap.json"), encoding="utf-8").read()
    try:
        hesap.hesap_olustur("ikinci", "12345678"); raise AssertionError("ikinci hesap")
    except ValueError:
        pass

def test_oturum_suresi_dolar():
    import hesap
    t = hesap.oturum_ac()
    assert hesap.oturum_gecerli(t) and not hesap.oturum_gecerli("uydurma") and not hesap.oturum_gecerli(None)
    assert t not in open(os.path.join(ortak.DURUM_DIZINI, "oturumlar.json"), encoding="utf-8").read()
    eski, hesap.OTURUM_SN = hesap.OTURUM_SN, -1
    try:
        assert not hesap.oturum_gecerli(hesap.oturum_ac())
    finally:
        hesap.OTURUM_SN = eski
    hesap.oturum_kapat(t); assert not hesap.oturum_gecerli(t)

def test_sifre_sifirla_oturumlari_siler():
    import hesap
    hesap.hesap_olustur("ramazan", "gizli-sifre-1"); t = hesap.oturum_ac()
    hesap.sifre_sifirla("yeni-sifre-22")
    assert not hesap.oturum_gecerli(t) and hesap.dogrula("ramazan", "yeni-sifre-22")

def test_kaba_kuvvet_beklemesi():
    import hesap
    hesap.giris_basarili()
    for _ in range(5):
        assert hesap.giris_bekleme() == 0; hesap.giris_hatasi()
    assert hesap.giris_bekleme() == 0          # ilk 5 hata beklemesiz
    hesap.giris_hatasi()                       # 6. hata → 2 sn bekleme
    assert 1 <= hesap.giris_bekleme() <= 2
    hesap.giris_basarili(); assert hesap.giris_bekleme() == 0
```

  (Kural: ilk 5 hata beklemesiz; 6. hatadan itibaren `2**(hata-5)` sn, en çok 300.)

- [ ] **Step 2: Run** `python test_ofis.py hesap oturum sifre kaba` → FAIL (modül yok)
- [ ] **Step 3: Implement** `hesap.py` (dosya yazımı `.tmp` + `os.chmod(ortak.ENV_IZIN)` + `os.replace`, modül içi `threading.Lock`; süresi dolan oturumlar okurken temizlenir)
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`
- [ ] **Step 5: Commit** `git add hesap.py test_ofis.py && git commit -m "feat: hesap, oturum ve kaba kuvvet koruması"`

---

### Task 2: `ajan_yonetimi.py` — doğrulanmış ajan/oda işlemleri

**Files:** Create `ajan_yonetimi.py`; Modify `ortak.py` (`ajanlari_yukle`, sabitler), `kosucu.py` (yasak
birleştirme), `.gitignore` (`calisma/`); Modify `test_ofis.py`

**Interfaces:**
- Produces in `ortak.py`:
  - `VARSAYILAN_YASAK = ["Read(**/.env)", "Read(**/.env.*)", "Read(~/.env)", "Bash(rm:*)", "Bash(git push:*)", "Bash(curl:*)", "Bash(open:*)"]`
  - `en_kucuk_yapilandirma() -> dict` → `{"surum": 2, "ayarlar": {"kullanici": "", "marka": "Ajan Ofisi"}, "odalar": [], "varsayilan_yasak_araclar": VARSAYILAN_YASAK, "ajanlar": [<CEO: ajanlar.example.json'daki CEO girdisi>]}`
  - `ajanlari_yukle()`: dosya yoksa `en_kucuk_yapilandirma()`'yı yazar ve onu döndürür (artık
    `YapilandirmaHatasi` atmaz); göreli `cwd`'yi `KOK`'a göre çözer (`"."` → `KOK`).
  - `yasakli_araclar(veri: dict) -> list[str]` — `VARSAYILAN_YASAK ∪ veri["varsayilan_yasak_araclar"]` (sıra korunur, tekrar yok); `kosucu.kos` bunu kullanır.
- Produces in `ajan_yonetimi.py` (hepsi `ValueError(<Türkçe mesaj>)` ile reddeder; her değişiklik `kaydet` ile yazılır):
  - `YETKILER = {"okuma": ["Read", "Glob", "Grep"], "yazma": ["Write", "Edit"], "komut": ["Bash"], "web": ["WebSearch", "WebFetch"]}`; `MODELLER = ("sonnet", "haiku", "opus")`; `TEMALAR = ("ceo", "yazi", "kod", "tasarim", "sosyal", "arastirma", "gun-sonu", "atolye", "bakim", "posta", "veri")`
  - `id_turet(ad: str, mevcut: set[str]) -> str` — Türkçe harf sadeleştirme (ç→c, ğ→g, ı→i, İ→i, ö→o, ş→s, ü→u), küçük harf, `[^a-z0-9]+` → `-`, kenar `-` kırpılır, 40 karakter; boşsa `"ajan"`; çakışırsa `-2`, `-3` …
  - `oku() -> dict` (ham `ajanlar.json`, `ortak.ajanlari_yukle()` üzerinden), `kaydet(veri: dict) -> None` (`dogrula` + kilit + `.bak` + `.tmp` + `os.replace`), `dogrula(veri: dict) -> None`
  - `ajan_ekle(alanlar: dict) -> dict`, `ajan_guncelle(ajan_id: str, alanlar: dict) -> dict`, `ajan_sil(ajan_id: str) -> None` (`"ceo"` → hata; meşgul denetimi sunucuda)
  - `ajan_ayrinti(ajan_id: str) -> dict` (düzenleme formu için: ham alanlar + türetilmiş `yetkiler: list[str]`)
  - `oda_ekle(ad: str, tema: str | None = None, aciklama: str = "") -> dict`, `oda_guncelle(oda_id: str, alanlar: dict) -> dict`
  - `alanlar` anahtarları: `ad` (zorunlu, ≤ 60), `oda` (var olan oda id) **ya da** `yeni_oda: {"ad", "tema"?}`,
    `aciklama` (≤ 500), `cwd` (boş → `calisma/<id>` oluşturulur), `model` (`MODELLER`, varsayılan
    `"sonnet"`), `yetkiler` (`YETKILER` anahtarları, varsayılan `["okuma"]`) ya da `izinli_araclar` (ham liste;
    ikisi birden gelirse `izinli_araclar` kazanır), `hazir_gorevler` (`[{"etiket" ≤ 60, "prompt" ≤ 4000}]`, ≤ 10),
    `yalin` (bool), `tetik_kelime` (≤ 40). Yeni ajana `ne_zaman: "istek"`, `ne_zaman_metin: "İstek gelince"`.
    Güncelleme formda olmayan alanları (`yer`, `ne_zaman`…) korur; `id` değişmez.

- [ ] **Step 1: Write the failing tests**

```python
def test_id_turet():
    import ajan_yonetimi as ay
    assert ay.id_turet("Şeyma'nın Asistanı", set()) == "seymanin-asistani"
    assert ay.id_turet("!!!", set()) == "ajan"
    assert ay.id_turet("Blog Yazarı", {"blog-yazari"}) == "blog-yazari-2"
    assert ay.id_turet("x" * 80, set()) == "x" * 40

def test_ajanlar_json_yoksa_en_kucuk(tmp):
    ortak.AJANLAR_DOSYASI = os.path.join(tmp, "ajanlar.json")
    veri, tablo = ortak.ajanlari_yukle()
    assert list(tablo) == ["ceo"] and tablo["ceo"]["kurulu"] and os.path.exists(ortak.AJANLAR_DOSYASI)

def test_ajan_ekle_guncelle_sil(tmp):
    import ajan_yonetimi as ay
    _ajanlar(tmp)
    a = ay.ajan_ekle({"ad": "Blog Yazarı", "yeni_oda": {"ad": "Yazı Masası", "tema": "yazi"}, "aciklama": "Taslak yazar."})
    assert a["id"] == "blog-yazari" and a["izinli_araclar"] == ["Read", "Glob", "Grep"]
    _, tablo = ortak.ajanlari_yukle()
    assert tablo["blog-yazari"]["kurulu"]  # calisma/blog-yazari oluşturuldu
    veri = ay.oku()
    assert {"id": a["oda"], "ad": "Yazı Masası", "tema": "yazi", "aciklama": ""} in veri["odalar"]
    ay.ajan_guncelle("blog-yazari", {"ad": "Baş Yazar", "yetkiler": ["okuma", "yazma"], "model": "haiku"})
    b = ay.ajan_ayrinti("blog-yazari")
    assert b["ad"] == "Baş Yazar" and b["model"] == "haiku" and b["yetkiler"] == ["okuma", "yazma"]
    ay.ajan_sil("blog-yazari")
    assert "blog-yazari" not in ortak.ajanlari_yukle()[1]
    for kotu in (lambda: ay.ajan_sil("ceo"), lambda: ay.ajan_ekle({"ad": ""}),
                 lambda: ay.ajan_ekle({"ad": "X", "oda": "olmayan-oda"}),
                 lambda: ay.ajan_ekle({"ad": "X", "model": "gpt"}),
                 lambda: ay.ajan_ekle({"ad": "X", "yeni_oda": {"ad": "Y", "tema": "uydurma"}})):
        try:
            kotu(); raise AssertionError("kabul edildi")
        except ValueError:
            pass

def test_gecersiz_kayit_dosyayi_degistirmez(tmp):
    import ajan_yonetimi as ay
    _ajanlar(tmp)
    once = open(ortak.AJANLAR_DOSYASI, encoding="utf-8").read()
    veri = ay.oku(); veri["ajanlar"].append({"id": "Kötü Id", "ad": "x"})
    try:
        ay.kaydet(veri); raise AssertionError("bozuk kayıt yazıldı")
    except ValueError:
        pass
    assert open(ortak.AJANLAR_DOSYASI, encoding="utf-8").read() == once

def test_yasakli_araclar_her_zaman():
    assert ortak.yasakli_araclar({"varsayilan_yasak_araclar": ["Bash(sudo:*)"]})[:7] == ortak.VARSAYILAN_YASAK
    assert "Bash(sudo:*)" in ortak.yasakli_araclar({"varsayilan_yasak_araclar": ["Bash(sudo:*)"]})
    assert ortak.yasakli_araclar({}) == ortak.VARSAYILAN_YASAK
```

  `_ajanlar(tmp)` yardımcısı ajanlar.json'a `"odalar": []` ekleyecek şekilde genişletilir.

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** `python test_ofis.py` → `OK` (eski testler dahil)
- [ ] **Step 5: Commit** `git commit -am "feat: doğrulanmış ajan/oda yönetimi" ` (+ `git add ajan_yonetimi.py`)

---

### Task 3: Sektör şablonları

**Files:** Create `sablonlar/{yazilim,influencer,dijital-pazarlama,e-ticaret,on-buro,egitim,danismanlik}.json`;
Modify `ajan_yonetimi.py`; Modify `test_ofis.py`

**Interfaces:**
- Şablon biçimi: `{"ad": str, "aciklama": str, "odalar": [{"id", "ad", "aciklama", "tema"}], "ajanlar": [{"id", "ad", "oda", "aciklama", "model", "yetkiler", "hazir_gorevler": [{"etiket", "prompt"}]}]}`;
  4-7 ajan, 2-4 oda, her ajanda 2-3 hazır görev; prompt'lar yayın/mail/para yapmaz, çıktı taslaktır; `cwd` yok.
- Produces: `ajan_yonetimi.sablon_listesi() -> list[dict]` (`{"id", "ad", "aciklama", "odalar", "ajanlar": [{"id", "ad", "oda", "aciklama"}]}`, `ad`'a göre sıralı)
- Produces: `ajan_yonetimi.sablondan_ekle(sablon_id: str, ajan_idleri: list[str] | None = None) -> dict` →
  `{"eklenen": [id], "atlanan": [id]}`; var olan id atlanır; var olan oda id'si yeniden kullanılır; yalnız seçili
  ajanların odaları eklenir; tek `kaydet`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sablonlar_gecerli():
    import ajan_yonetimi as ay
    liste = ay.sablon_listesi()
    assert {s["id"] for s in liste} == {"yazilim", "influencer", "dijital-pazarlama", "e-ticaret", "on-buro", "egitim", "danismanlik"}
    for s in liste:
        ham = json.load(open(os.path.join(ortak.KOK, "sablonlar", s["id"] + ".json"), encoding="utf-8"))
        assert 4 <= len(ham["ajanlar"]) <= 7 and 2 <= len(ham["odalar"]) <= 4, s["id"]
        odalar = {o["id"] for o in ham["odalar"]}
        for a in ham["ajanlar"]:
            assert a["oda"] in odalar and a["model"] in ay.MODELLER and set(a["yetkiler"]) <= set(ay.YETKILER), (s["id"], a["id"])
            assert 2 <= len(a["hazir_gorevler"]) <= 3 and ortak.AJAN_ID_DESENI.match(a["id"]) and "cwd" not in a
        assert all(o.get("tema") in ay.TEMALAR for o in ham["odalar"])

def test_sablondan_ekle_tekrarsiz(tmp):
    import ajan_yonetimi as ay
    _ajanlar(tmp)
    ilk = ay.sablondan_ekle("yazilim")
    assert ilk["eklenen"] and not ilk["atlanan"]
    ikinci = ay.sablondan_ekle("yazilim")
    assert not ikinci["eklenen"] and sorted(ikinci["atlanan"]) == sorted(ilk["eklenen"])
    _, tablo = ortak.ajanlari_yukle()
    assert all(tablo[i]["kurulu"] for i in ilk["eklenen"])

def test_sablondan_secili_ajanlar(tmp):
    import ajan_yonetimi as ay
    _ajanlar(tmp)
    hepsi = [a["id"] for a in next(s for s in ay.sablon_listesi() if s["id"] == "influencer")["ajanlar"]]
    sonuc = ay.sablondan_ekle("influencer", hepsi[:1])
    assert sonuc["eklenen"] == hepsi[:1]
    try:
        ay.sablondan_ekle("olmayan"); raise AssertionError
    except ValueError:
        pass
```

  (`test_ofis.py` başına `import json` eklenir.)

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** fonksiyonlar + 7 şablon dosyası (Türkçe, sektöre özgü
  ajanlar; ör. yazılım: Ürün Yöneticisi, Backend, Frontend, Test, Dokümantasyon, Kod İnceleyici) ·
  **Step 4: Run** → `OK`
- [ ] **Step 5: Commit** `git add sablonlar ajan_yonetimi.py test_ofis.py && git commit -m "feat: 7 sektör şablonu"`

---

### Task 4: Sunucu — oturum kapısı, giriş, kurulum uçları, şifre sıfırlama

**Files:** Modify `sunucu.py`; Modify `test_ofis.py`

**Interfaces:**
- Consumes: Task 1 `hesap.*`, Task 2 `ajan_yonetimi.oku/kaydet`.
- Produces: `Isleyici._json(kod, veri, cerez: str | None = None)` (varsa `Set-Cookie` başlığı);
  `Isleyici._token() -> str | None` (`Cookie` başlığından `ofis_oturum`, `http.cookies.SimpleCookie`);
  `ACIK_UCLAR = {("GET", "/api/oturum"), ("POST", "/api/oturum"), ("POST", "/api/kurulum")}`; kapı
  `do_GET`/`do_POST`'ta `_guvenlik`'ten hemen sonra: `/api/` ile başlayan ve açık olmayan istek oturumsuzsa
  `401 {"hata": "giriş gerekli"}`.
- `GET /api/oturum` → hesap yoksa `{"kurulum": true, "adim": "ad" if not ayarlar.kullanici else "hesap",
  "ayarlar": {"kullanici", "marka"}}`; hesap varsa `{"kurulum": false, "giris": bool,
  "sihirbaz_bitti": bool(ayarlar.kurulum_tamam), "kullanici_adi": <yalnız giriş varsa>}`.
- `POST /api/oturum`: `{"islem": "giris", "kullanici_adi", "sifre"}` → bekleme varsa `429 {"hata", "bekle_sn"}`;
  yanlışsa `401` + `giris_hatasi()`; doğruysa `200` + çerez + `giris_basarili()`. `{"islem": "cikis"}` →
  oturum silinir, çerez `Max-Age=0`.
- `POST /api/kurulum`: `{"adim": "ad", "kullanici", "marka"}` → hesap yoksa girişsiz, varsa oturum ister;
  `ayarlar`'a yazar (kullanici ≤ 40, marka ≤ 40). `{"adim": "hesap", "kullanici_adi", "sifre"}` → yalnız hesap
  yokken; oluşturur ve **çerezle giriş yaptırır**; hesap varsa 409. `{"adim": "bitir"}` → oturum ister;
  `ayarlar.kurulum_tamam = true`.
- `main()`: `--sifre-sifirla` argümanıyla `getpass` ile iki kez sorup `hesap.sifre_sifirla`, çıkar (sunucu
  açılmaz); hesap yoksa "önce arayüzden kurulum yap" der. `ajanlari_yukle` artık eksik dosyada düşmez.

- [ ] **Step 1: Write the failing tests** (gerçek HTTP; yardımcı `_sunucu(tmp)`: `_ajanlar(tmp)`, 
  `ThreadingHTTPServer(("127.0.0.1", 0), sunucu.Isleyici)` arka planda; `istek(yontem, yol, govde=None)` →
  `(durum, json, set_cookie)`; çerezi saklayıp sonraki isteklere `Cookie` olarak ekler; `Host: 127.0.0.1:<port>`;
  test sonunda `shutdown()`)

```python
def test_girissiz_api_401(tmp):
    s = _sunucu(tmp)
    try:
        for yol in ("/api/ajanlar", "/api/telegram", "/api/sayac", "/api/olaylar"):
            assert s.istek("GET", yol)[0] == 401, yol
        assert s.istek("POST", "/api/gorev", {"ajan": "yazar", "prompt": "x"})[0] == 401
        assert s.istek("GET", "/api/oturum")[1]["kurulum"] is True
        assert s.ham("GET", "/").status == 200  # statik sayfa açık
    finally:
        s.kapat()

def test_kurulum_akisi_ve_giris(tmp):
    s = _sunucu(tmp)
    try:
        assert s.istek("POST", "/api/kurulum", {"adim": "ad", "kullanici": "Ramazan", "marka": "CW"})[0] == 200
        d, v, cerez = s.istek("POST", "/api/kurulum", {"adim": "hesap", "kullanici_adi": "ramazan", "sifre": "gizli-sifre-1"})
        assert d == 200 and "HttpOnly" in cerez and "SameSite=Strict" in cerez and "Max-Age=2592000" in cerez
        assert s.istek("GET", "/api/ajanlar")[0] == 200       # otomatik giriş
        assert s.istek("POST", "/api/kurulum", {"adim": "hesap", "kullanici_adi": "x2", "sifre": "12345678"})[0] == 409
        assert s.istek("POST", "/api/kurulum", {"adim": "bitir"})[0] == 200
        s.istek("POST", "/api/oturum", {"islem": "cikis"})
        assert s.istek("GET", "/api/ajanlar")[0] == 401
        assert s.istek("POST", "/api/kurulum", {"adim": "ad", "kullanici": "Saldırgan"})[0] == 401  # hesap var
        assert s.istek("POST", "/api/oturum", {"islem": "giris", "kullanici_adi": "ramazan", "sifre": "yanlis-sifre"})[0] == 401
        assert s.istek("POST", "/api/oturum", {"islem": "giris", "kullanici_adi": "ramazan", "sifre": "gizli-sifre-1"})[0] == 200
        o = s.istek("GET", "/api/oturum")[1]
        assert o == {"kurulum": False, "giris": True, "sihirbaz_bitti": True, "kullanici_adi": "ramazan"}
        assert ortak.ajanlari_yukle()[0]["ayarlar"]["kullanici"] == "Ramazan"
    finally:
        s.kapat()

def test_bozuk_cerez_401(tmp):
    s = _sunucu(tmp)
    try:
        s.cerez = "ofis_oturum=uydurma; x=;;"
        assert s.istek("GET", "/api/ajanlar")[0] == 401
    finally:
        s.kapat()

def test_giris_kaba_kuvvet_429(tmp):
    import hesap
    s = _sunucu(tmp)
    try:
        hesap.hesap_olustur("ramazan", "gizli-sifre-1"); hesap.giris_basarili()
        kodlar = [s.istek("POST", "/api/oturum", {"islem": "giris", "kullanici_adi": "ramazan", "sifre": "yanlis-sifre"})[0] for _ in range(7)]
        assert kodlar[:6] == [401] * 6 and kodlar[6] == 429
    finally:
        hesap.giris_basarili(); s.kapat()

def test_mevcut_kurulum_korunur(tmp):
    s = _sunucu(tmp)  # _ajanlar: yazar + ceo, ayarlar yok
    try:
        once = ortak.ajanlari_yukle()[0]
        s.istek("POST", "/api/kurulum", {"adim": "hesap", "kullanici_adi": "ramazan", "sifre": "gizli-sifre-1"})
        sonra = ortak.ajanlari_yukle()[0]
        assert [a["id"] for a in sonra["ajanlar"]] == [a["id"] for a in once["ajanlar"]]
    finally:
        s.kapat()
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** → `OK` (Telegram/akış testleri dahil)
- [ ] **Step 5: Commit** `git commit -am "feat: giriş kapısı, kurulum uçları ve şifre sıfırlama"`

---

### Task 5: Sunucu — ajan, oda ve şablon uçları

**Files:** Modify `sunucu.py`; Modify `test_ofis.py`

**Interfaces:**
- Consumes: Task 2/3 `ajan_yonetimi.*`, `ortak.ajan_mesgul`.
- `GET /api/sablonlar` → `{"sablonlar": sablon_listesi()}`
- `GET /api/ajanlar/<id>` → `ajan_ayrinti(id)` (yoksa 404) — düzenleme formu için `cwd`, araçlar, prompt'lar dahil
  (giriş arkasında).
- `POST /api/ajanlar`: `{"islem": "ekle", "ajan": {...}}` → 200 ajan; `{"islem": "guncelle", "id", "ajan"}`;
  `{"islem": "sil", "id"}` (meşgulse 409); `{"islem": "sablon", "sablon", "ajanlar": [id] | null}` → 200
  `{"eklenen", "atlanan"}`. `ValueError` → 400 `{"hata"}`.
- `POST /api/odalar`: `{"islem": "ekle", "ad", "tema"?, "aciklama"?}`; `{"islem": "guncelle", "id", "ad"?, "aciklama"?, "tema"?}`.

- [ ] **Step 1: Write the failing tests** (`_sunucu(tmp)` + `s.giris()` yardımcısı: hesap oluşturup giriş yapar)

```python
def test_ajan_uclari(tmp):
    s = _sunucu(tmp); s.giris()
    try:
        d, a, _ = s.istek("POST", "/api/ajanlar", {"islem": "ekle", "ajan": {"ad": "Muhasebeci", "yeni_oda": {"ad": "Muhasebe"}}})
        assert d == 200 and any(x["id"] == a["id"] for x in s.istek("GET", "/api/ajanlar")[1]["ajanlar"])
        assert "cwd" not in next(x for x in s.istek("GET", "/api/ajanlar")[1]["ajanlar"] if x["id"] == a["id"])
        assert "cwd" in s.istek("GET", f"/api/ajanlar/{a['id']}")[1]
        assert s.istek("POST", "/api/ajanlar", {"islem": "sil", "id": "ceo"})[0] == 400
        ortak.durum_yaz(a["id"], {"durum": "calisiyor", "pid": os.getpid()})
        assert s.istek("POST", "/api/ajanlar", {"islem": "sil", "id": a["id"]})[0] == 409
        ortak.durum_yaz(a["id"], {"durum": "bitti"})
        assert s.istek("POST", "/api/ajanlar", {"islem": "sil", "id": a["id"]})[0] == 200
        r = s.istek("POST", "/api/ajanlar", {"islem": "sablon", "sablon": "egitim", "ajanlar": None})[1]
        assert r["eklenen"] and s.istek("GET", "/api/sablonlar")[0] == 200
        assert s.istek("POST", "/api/odalar", {"islem": "ekle", "ad": "Arşiv", "tema": "veri"})[0] == 200
        assert s.istek("POST", "/api/ajanlar", {"islem": "ekle", "ajan": {"ad": ""}})[0] == 400
    finally:
        s.kapat()

def test_silinen_ajana_gorev_404(tmp):
    import sunucu
    s = _sunucu(tmp); s.giris()
    try:
        a = s.istek("POST", "/api/ajanlar", {"islem": "ekle", "ajan": {"ad": "Geçici"}})[1]
        s.istek("POST", "/api/ajanlar", {"islem": "sil", "id": a["id"]})
        try:
            sunucu.gorev_baslat(a["id"], prompt="x"); raise AssertionError
        except sunucu.IstekHatasi as e:
            assert e.kod == 404
    finally:
        s.kapat()
```

- [ ] **Step 2: Run** → FAIL · **Step 3: Implement** · **Step 4: Run** → `OK`
- [ ] **Step 5: Commit** `git commit -am "feat: ajan, oda ve şablon uçları"`

---

### Task 6: Ön yüz — giriş ekranı, kurulum sihirbazı, çıkış

**Files:** Modify `on-yuz/index.html`

**Interfaces:**
- Consumes: Task 4 uçları; Task 5 `GET /api/sablonlar`, `POST /api/ajanlar {"islem": "sablon"}`.
- Modülün en başında (`ajanlariYukle`'den önce, `DEMO` değilse): `const oturum = await getJSON('/api/oturum')`.
  - `oturum.kurulum` ya da (`giris` ve `!sihirbaz_bitti`) → sihirbaz katmanı; `!giris` → giriş katmanı.
    İkisinde de modül `await new Promise(() => {})` ile durur (sahne kurulmaz); iş bitince `location.reload()`.
- Sihirbaz (tam ekran katman, `id="kurulum"`, mevcut `cam` stili), 4 adım ve üstte adım göstergesi:
  1. **Adın** — ad + ofis adı (dolu gelir) → `POST /api/kurulum {"adim": "ad"}`.
  2. **Hesap** — kullanıcı adı, şifre, şifre tekrar (eşleşme ve ≥ 8 ön yüzde de denetlenir) →
     `{"adim": "hesap"}`. Hesap zaten varsa (mevcut kurulum, giriş yapılmış) bu adım atlanır.
  3. **Ajanlar** — kartlar: "Boş başla" + 7 şablon (ad, açıklama, ajan adları); şablon seçilince ajanları
     onay kutusuyla listelenir → `POST /api/ajanlar {"islem": "sablon"}`. Var olan ajanlar (mevcut kurulum)
     üstte listelenir. "Ajan ekle/düzenle" Task 7'deki Ajanlar sayfası bileşenini (`ajanlarSayfasi()`) burada da
     açar.
  4. **Hazır** — "Ofise gir" → `{"adim": "bitir"}` → `location.reload()`.
- Giriş katmanı (`id="giris"`): kullanıcı adı + şifre; 401 → "Kullanıcı adı ya da şifre yanlış"; 429 →
  "Çok fazla deneme, <bekle_sn> sn sonra tekrar dene"; başarı → `location.reload()`.
- Üst çubuğa "Çıkış" düğmesi (`id="cikisDugme"`, demo'da gizli) → `POST /api/oturum {"islem": "cikis"}` → reload.
- `getJSON`/`postJSON` 401 alırsa (oturum süresi doldu) `location.reload()` (giriş ekranına döner).
- Tüm kullanıcı metinleri `textContent` ile basılır.

- [ ] **Step 1: Manual check (RED)** — sunucuyu temiz bir `durum/` ile aç (`OFIS_PORT=8860`, geçici
  `OFIS_AJANLAR` ile boş klasör) → sayfa ofisi boş/hatalı gösterir (sihirbaz yok).
- [ ] **Step 2: Implement** katmanlar, akış ve çıkış.
- [ ] **Step 3: Manual check (Playwright)** — Expected: (a) ilk açılış sihirbaz 1. adım; (b) ad → hesap →
  şablon "Dijital pazarlama ajansı" seç → bitir → ofiste şablon ajanları görünür; (c) Çıkış → giriş ekranı;
  yanlış şifre mesajı; doğru şifre → ofis; (d) `?demo=1` girişsiz açılır; (e) konsolda hata yok.
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`
- [ ] **Step 5: Commit** `git commit -am "feat: giriş ekranı ve kurulum sihirbazı"`

---

### Task 7: Ön yüz — Ajanlar sayfası ve oda teması

**Files:** Modify `on-yuz/index.html`

**Interfaces:**
- Consumes: Task 5 uçları.
- Üst çubuğa sekme: `<button data-sekme="ajanlar">Ajanlar</button>`; `sekmeAc('ajanlar')` →
  `ajanlarSayfasi()` (async, `#sayfa` içeriği döndürür; sihirbaz 3. adımda da kullanılır).
- Sayfa: ajan listesi (ad, oda adı, açıklama; Düzenle / Sil — CEO'da Sil yok), "Ajan ekle", "Şablondan ekle"
  (şablon + onay kutuları; sonuçta "N eklendi, M zaten vardı").
- Form: temel alanlar (Ad, Oda seçimi + "Yeni oda…" → ad + tema seçici `TEMALAR` listesinden, Ne iş yapar);
  `<details>` "Gelişmiş": Çalışma klasörü (boş = otomatik), Model (`sonnet`/`haiku`/`opus`), Yetkiler (4 onay
  kutusu: Yalnız okuyabilir [zorunlu işaretli], Dosya yazabilir, Komut çalıştırabilir, Web'e bakabilir),
  Hazır görevler (etiket + prompt satırları, ekle/sil), Yalın mod, Tetik kelime.
- Kaydet/Sil/Şablon sonrası `location.reload()` (sahne yeniden kurulur); hata → `tost(veri.hata)`.
- Sil onayı: "‹ad› ofisten çıkarılsın mı? Hafızası ve çıktıları diskte kalır." 409 → "Ajan şu an çalışıyor;
  bitince tekrar dene."
- Oda teması: oda kurulumunda tema `oda.tema` varsa ondan, yoksa oda id'sinden alınır — `odaTema(tema ?? id)`
  ve `TEMA_DEKOR[o.tema ?? o.id]`; config'teki `ad`/`aciklama` yine temanın üstüne yazılır.

- [ ] **Step 1: Manual check (RED)** — ofiste "Ajanlar" sekmesi yok.
- [ ] **Step 2: Implement**
- [ ] **Step 3: Manual check (Playwright)** — Expected: (a) yeni oda "Muhasebe" (tema `veri`) ile "Muhasebeci"
  ekle → reload sonrası sahnede yeni oda veri-teması eşyalarıyla ve ajan masasıyla görünür; (b) düzenle → model
  Haiku, yetki "Dosya yazabilir" → kaydedilir, `GET /api/ajanlar/<id>` doğrular; (c) sil → sahneden kalkar,
  `hafiza/` ve `cikti/` duruyor; (d) CEO'da Sil yok; (e) "Şablondan ekle" ikinci kez → "zaten vardı"; (f)
  konsolda hata yok; (g) `?demo=1` çalışır (Ajanlar sekmesi demo'da salt okunur liste ya da gizli).
- [ ] **Step 4: Run** `python test_ofis.py` → `OK`
- [ ] **Step 5: Commit** `git commit -am "feat: Ajanlar sayfası ve oda teması"`

---

### Task 8: Belgeler

**Files:** Modify `README.md`, `ajanlar.example.json` (`odalar`'a `tema` örneği), `.gitignore` (zaten Task 2'de
`calisma/`)

- [ ] **Step 1:** README "Kendi ajanını nasıl bağlarsın" → "Kurulum": `python sunucu.py` → tarayıcıda sihirbaz
  (ad, hesap, şablon) → ofis; JSON ile elle kurulum "ileri düzey" alt başlığına iner. "Odalar ve ajan sayısı"na
  `tema` alanı. "Giriş ve şifre" bölümü (çerez, 30 gün, kaba kuvvet, `python sunucu.py --sifre-sifirla`).
  "Şablonlar" listesi. API tablosuna yeni uçlar. Dosyalar tablosuna `hesap.py`, `ajan_yonetimi.py`, `sablonlar/`.
  Güvenlik notlarına "tüm API giriş arkasında".
- [ ] **Step 2: Run** `python test_ofis.py` → `OK`
- [ ] **Step 3: Commit** `git commit -am "docs: kurulum sihirbazı, giriş, ajan yönetimi ve şablonlar"`
