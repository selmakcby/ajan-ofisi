# İlk kurulum, giriş ve ajan yönetimi — tasarım

Tarih: 2026-11-06 · Durum: onay bekliyor · Temel dal: `telegram-koprusu` (PR #1 henüz birleşmedi)

## Amaç ve neden

Uygulama GitHub'da herkese açık dağıtılacak. Bugün kurmak için `ajanlar.example.json`'ı kopyalayıp JSON elle
düzenlemek gerekiyor; teknik olmayan biri bunu yapamaz. İndiren kişi uygulamayı ilk açtığında **adım adım bir
kurulum sihirbazı** görmeli, ajanlarını tarayıcıdan **ekleyip çıkarabilmeli**, isterse **sektör şablonundan**
hazır bir ofisle başlamalı. Uygulama ileride (B: Docker) bir sunucuya konacağı için **giriş ekranı** şimdiden
gerekiyor: adresi bilen başka biri ofise girip ajan çalıştıramamalı.

Başarı: Uygulamayı ilk kez açan kullanıcı JSON görmeden adını yazar, hesabını açar, "Dijital pazarlama ajansı"
şablonunu seçer, giriş yapar ve ofisinde ajanlarını görür. Sonradan "Ajanlar" sayfasından yeni bir oda ve ajan
ekler; ajan hemen ofiste belirir.

## Kapsam

Bu iş "A"dır. Kapsam dışı ve sonraya (B) bırakılanlar: **Claude bağlantısı** (API anahtarı/abonelik ayarı —
bugünkü `claude` CLI modeline dokunulmaz) ve **Docker Compose**.

## Hedefler

### 1. İlk kurulum sihirbazı
Hesap yoksa (ilk çalıştırma) uygulama ofis yerine sihirbazı açar. Adımlar:
1. **Adın** — selamlamadaki ad (`ayarlar.kullanici`). İsteğe bağlı ofis adı (`ayarlar.marka`, varsayılan
   "Ajan Ofisi").
2. **Hesap** — kullanıcı adı + şifre (+ şifre tekrar). Tek kullanıcı: ofisin sahibi.
3. **Ajanlar** — "Boş başla (yalnız CEO)" ya da bir **sektör şablonu** seç; şablonun ajanları ve odaları
   listelenir, istenmeyenin işareti kaldırılabilir. Sonra (aynı adımda ya da sonradan) tek tek ajan eklenip
   çıkarılabilir — bu adım, Ajanlar sayfasının aynısını kullanır.
4. **Bitti → Giriş** — kullanıcı az önce açtığı hesapla giriş yapar ve ofise girer.

Sihirbaz yarıda kalırsa (sayfa kapanırsa) kaldığı adımdan devam eder; hesap açılmadan önceki adımlar
yeniden yapılabilir. Hesap açıldıktan sonra sihirbaz yalnız giriş yapmış kullanıcıya açıktır.

**Mevcut kurulumlar:** `ajanlar.json`'ı olan ama hesabı olmayan kullanıcı uygulamayı güncelleyince sihirbaz
açılır; var olan ad, marka, ajanlar ve odalar korunur, adımlarda dolu gelir; yalnız hesap açtırır.

### 2. Hesap ve giriş
- Giriş yapmadan hiçbir veri ya da işlem ucu çalışmaz: `/api/*` (SSE `/api/olaylar` ve `/api/telegram`
  dahil). Yalnız şunlar girişsiz açıktır: giriş/sihirbaz sayfasının statik dosyaları, `/api/oturum` (durum,
  giriş, çıkış) ve hesap açılmadan önceki sihirbaz uçları.
- Arayüzde "Çıkış" düğmesi.
- Şifre unutulursa: sunucunun çalıştığı bilgisayarda `python sunucu.py --sifre-sifirla` (etkileşimli yeni
  şifre). Uzaktan sıfırlama yok.
- Demo modu (`?demo=1`) girişsiz çalışmaya devam eder (arka uca istek atmaz).

### 3. Ajanlar sayfası
Ofisin üst çubuğunda yeni bir **"Ajanlar"** sekmesi/sayfası (sihirbazın 3. adımıyla aynı bileşen):
- Ajan listesi: ad, oda, açıklama; düzenle / sil.
- **Ekle/düzenle formu — temel alanlar (herkese görünür):**
  - **Ad** (zorunlu). `id` addan türetilir (Türkçe karakterler sadeleşir, `^[a-z0-9-]{1,40}$`, çakışırsa
    sonuna sayı); kullanıcı görmez.
  - **Oda** — var olan odalardan seç ya da **"Yeni oda"**: ad yazılır, isteğe bağlı görünüm (hazır temalar:
    `yazi`, `kod`, `tasarim`, `sosyal`, `arastirma`, `gun-sonu`, `atolye`, `bakim`, `posta`, `veri`) seçilir.
  - **Ne iş yapar** (açıklama; CEO işi dağıtırken bunu okur).
- **"Gelişmiş" bölümü (kapalı gelir):**
  - **Çalışma klasörü** — boşsa ofisin içinde ajana özel klasör (`calisma/<ajan-id>/`) kendiliğinden açılır;
    isteyen var olan bir proje klasörünün yolunu yazar (klasör yoksa uyarı, ajan "kurulmadı" sayılır).
  - **Model** — Sonnet / Haiku / Opus (varsayılan Sonnet).
  - **Yetkiler** — anlaşılır seçenekler: "Yalnız okuyabilir" (`Read, Glob, Grep`), "Dosya yazabilir"
    (+ `Write, Edit`), "Komut çalıştırabilir" (+ `Bash`), "Web'e bakabilir" (+ `WebSearch, WebFetch`).
    Varsayılan: yalnız okuyabilir. Altında araç listesi elle düzenlenebilir (gizli, açılır).
  - **Hazır görevler** — etiket + prompt listesi (ekle/sil).
  - Yalın mod, tetik kelime (bugünkü alanlar).
- `varsayilan_yasak_araclar` (`.env` okuma, `rm`, `git push`, `curl`, `open`) her ajanda zorunlu; arayüzden
  kaldırılamaz.
- **Silme** onay sorar. Ajan yalnız ofisten çıkar; hafızası (`hafiza/<id>.md`) ve çıktıları (`cikti/<id>/`)
  diskte kalır. **CEO silinemez.** Çalışan ajan silinemez (önce bitmesi beklenir).
- **Odalar:** ajanı kalmayan oda sahneden kalkar (bugünkü davranış); oda listesinde adı/açıklaması
  düzenlenebilir.
- Değişiklik `ajanlar.json`'a yazılır ve sunucu yeniden başlamadan ofise yansır (sunucu dosyayı her istekte
  zaten okuyor; ön yüz kaydedince sahneyi yeniden kurar).

### 4. Sektör şablonları
Kurulumda ve Ajanlar sayfasında ("Şablondan ekle") seçilebilir. Şablon: odalar + ajanlar (ad, oda, açıklama,
model, yetki seçeneği, 2-3 hazır görev). Şablondan eklemede **aynı `id`'li ajan iki kez eklenmez**; eklenen
her ajan sonra düzenlenebilir. Şablon ajanlarının çalışma klasörü boş gelir (ofis içinde otomatik klasör).
Şablonlar:
- **Yazılım ekibi**
- **Influencer / içerik üreticisi**
- **Dijital pazarlama ajansı**
- **E-ticaret mağazası** (ürün açıklamaları, müşteri yazışması, stok/sipariş özetleri)
- **Küçük işletme ön büro** (fatura/gider özeti, teklif ve yazışma taslakları)
- **Eğitim / online kurs** (ders planı, quiz, öğrenci soruları)
- **Danışmanlık / ajans hesap yönetimi** (müşteri raporları, sunum taslakları)

Her şablonda 4-7 ajan, 2-4 oda. Şablon ajanlarının prompt'ları `CLAUDE.md` sınırlarına uyar (yayın/mail/para
yok, çıktı taslaktır).

## Hedef dışı
- Claude bağlantısı ayarı (API anahtarı/abonelik) — B.
- Docker Compose — B.
- Birden fazla kullanıcı, roller, e-posta ile şifre sıfırlama, iki adımlı doğrulama.
- Uygulamayı ağa açmak: sunucu yine yalnız `127.0.0.1`'e bağlanır (B değiştirecek).
- Şablon pazarı/indirme; kullanıcının kendi şablonunu kaydetmesi.

## Anti-hedefler
- Giriş yapmamış birinin herhangi bir ajan çalıştırabilmesi, ajan listesini/çıktıları görebilmesi.
- Şifrenin düz metin ya da hızlı özetle (sha256 vb.) saklanması; şifre ya da oturum anahtarının loga/olaya
  düşmesi.
- Mevcut kullanıcının güncellemeyle ajanlarını/odalarını kaybetmesi.
- Teknik olmayan kullanıcının bir ajan eklemek için klasör yolu, araç adı ya da JSON görmek zorunda kalması.
- Yeni Python bağımlılığı.

## Kısıtlar
- Yalnız Python standart kütüphanesi; ön yüz tek dosya düzeni (`on-yuz/`) ve mevcut stil korunur.
- Windows ve Linux/macOS'ta çalışır.
- Mevcut Host/Origin korumaları sürer; giriş bunların **üstüne** eklenir.
- Telegram köprüsü (PR #1) aynen çalışmaya devam eder.

## Kullanıcının verdiği kararlar
- Sihirbaz adımları: ad → hesap → ajanlar (şablon seçilebilir) → giriş.
- Giriş, ileride sunucuya konacağı için gerekli.
- Claude bağlantısı ve Docker sonraya (B); bağlantı modeline dokunulmaz.
- Ajan formunda teknik alanlar "gelişmiş" olarak isteğe bağlı görünür; ajan eklerken oda seçilir ya da
  yeni oda eklenir.
- Sektörler: yazılım, influencer, dijital pazarlama + önerilen e-ticaret, küçük işletme ön büro, eğitim,
  danışmanlık.

## Benim kararlarım (asistanın çağrısı)
- **Hesap dosyası:** `durum/hesap.json` (gitignore'daki `durum/` altında): `{kullanici_adi, sifre_ozeti,
  tuz, parametreler, olusturma}`. Özet: `hashlib.scrypt` (n=2^14, r=8, p=1, 32 bayt, 16 bayt rastgele tuz);
  karşılaştırma `hmac.compare_digest`. Dosya izinleri 0600.
- **Oturum:** giriş başarılıysa rastgele 32 baytlık anahtar (`secrets.token_urlsafe`), sunucuda yalnız
  **özeti** saklanır (`durum/oturumlar.json`: özet → bitiş zamanı). Çerez: `ofis_oturum`, `HttpOnly`,
  `SameSite=Strict`, `Path=/`, 30 gün; şimdilik `Secure` yok (yalnız http://127.0.0.1; B'de HTTPS ile
  eklenir). Çıkış oturumu siler. Şifre sıfırlama tüm oturumları siler.
- **Kaba kuvvet:** kullanıcı adı başına değil, **genel** sayaç: 5 hatalı denemeden sonra her deneme
  arasında artan bekleme (2, 4, 8 … en çok 300 sn), başarılı girişte sıfırlanır; bekleme süresince 429 döner.
- **Durum değiştiren istekler (POST):** mevcut Origin denetimi + `SameSite=Strict` çerez + JSON Content-Type
  şartı CSRF'e karşı yeterli sayılır.
- **Sihirbaz durumu:** hesap yoksa `/api/oturum` → `{"kurulum": true, "adim": ...}`; ön yüz buna göre
  sihirbazı ya da girişi gösterir. Hesap açılmadan önce sihirbaz uçları (ad, şablon seçimi) girişsiz
  çalışır — sunucu yalnız `127.0.0.1`'de olduğu için kabul edilebilir; hesap açıldığı an kapanır.
- **`ajanlar.json` yoksa** sunucu artık düşmez: yalnız CEO'lu en küçük yapılandırmayı oluşturur ve sihirbaz
  açılır. `ajanlar.example.json` kalır ama gerekmez.
- **Yazma güvenliği:** `ajanlar.json` yazımı süreç içi kilit + `.tmp` + `os.replace`; kaydetmeden önce
  doğrulama (id deseni, oda deseni, zorunlu alanlar, ajan sayısı ≤ 60, prompt ≤ 4000). Bozuk yazım ofisi
  düşürmesin diye önceki dosya `ajanlar.json.bak` olarak tutulur.
- **Şablon dosyaları:** `sablonlar/<id>.json` (repoda, her biri `{ad, aciklama, odalar, ajanlar}`). Sunucu
  `GET /api/sablonlar` ile listeler.
- **Uçlar:** `GET/POST /api/oturum` (durum, giriş, çıkış), `POST /api/kurulum` (adım verileri, hesap açma),
  `GET /api/sablonlar`, `POST /api/ajanlar` (`{"islem": "ekle"|"guncelle"|"sil"|"sablon", ...}`),
  `POST /api/odalar` (ekle/düzenle). `GET /api/ajanlar` bugünkü gibi `cwd` ve prompt'ları göndermez; Ajanlar
  sayfası için düzenleme ayrıntısı ayrı uçtan (`GET /api/ajanlar/<id>`) gelir.
- **Ön yüz düzeni:** giriş ve sihirbaz, ofis sahnesinin üstünde tam ekran bir katman olarak `index.html`
  içinde; Ajanlar sayfası mevcut `#sayfa` bölümünü kullanır (Odalar/Hafıza sekmeleri gibi).
- **Testler:** `test_ofis.py`'ye: şifre özeti/doğrulama, oturum anahtarı süresi ve silinmesi, kaba kuvvet
  beklemesi, girişsiz `/api/*` reddi (HTTP seviyesinde, gerçek `ThreadingHTTPServer` ile), id türetme,
  ajan ekle/güncelle/sil doğrulamaları, şablondan eklemede tekrar engeli, `ajanlar.json` yoksa en küçük
  yapılandırma, mevcut kurulumun korunması.

### Gözden geçirme sonrası netleşenler (asistanın çağrısı)
- **Sihirbaz ve oturum:** Girişsiz çalışan **yalnız 1. adımdır** (ad, marka). **Hesap açmak kullanıcıyı
  otomatik giriş yaptırır** (oturum çerezi o anda verilir); 3. adım (ajanlar/şablon) oturum ister; 4. adım
  "Kurulum tamam → Ofise gir" olur. Sonraki her açılışta giriş ekranı gelir. Böylece hesap açılmadan
  önceki pencerede kimse `ajanlar.json`'a yazamaz. `/api/oturum` → `{"kurulum": true, "adim": "ad"|"hesap"}`
  hesap yokken; hesap varsa `{"kurulum": false, "giris": bool, "sihirbaz_bitti": bool}`
  (`ayarlar.kurulum_tamam` ile işaretlenir; mevcut kurulumda hesap açılınca 3. adım dolu gelir).
- **Oda görünümü:** `odalar` girdilerine isteğe bağlı **`tema`** alanı eklenir (hazır tema id'lerinden biri).
  Ön yüz temayı önce `tema`'dan, yoksa bugünkü gibi oda id'sinden alır; böylece mevcut dosyalar aynen çalışır
  ve aynı temalı birden çok oda olabilir. Şablon odaları da `tema` kullanır. README'deki biçim buna göre
  güncellenir.
- **Ajan alanları:** ad değişince `id` değişmez. Güncelleme, formda görünmeyen alanları (`yer`, `ne_zaman`,
  elle yazılmış araçlar…) korur. Yeni ajana `ne_zaman: "istek"`, `ne_zaman_metin: "İstek gelince"`
  varsayılanı verilir (CEO prompt'u bu alanı okur). Sunucu `varsayilan_yasak_araclar`'ı dosyada eksik olsa da
  her koşuda ekler.

## İnşa edenin kararına bırakılanlar
- Sihirbaz ve giriş ekranının görsel tasarımı (mevcut stil içinde).
- Şablon ajanlarının tam metinleri (açıklama, hazır görev prompt'ları) — sınırlar yukarıda.
- Oda görünümü seçicisinin biçimi.
- Ajanlar sayfasında liste düzeni, arama/filtre olup olmaması.
