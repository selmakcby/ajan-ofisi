# Sunucu sürümü (Docker Compose) ve Claude bağlantısı — tasarım

Tarih: 2026-11-06 · Durum: onay bekliyor · Temel dal: `main` (`18a809b`) · Dal: `sunucu-surumu`

## Amaç ve neden

Ajan Ofisi bugün kullanıcının kendi bilgisayarında çalışıyor; bilgisayar kapalıyken ne ajanlar ne de Telegram
köprüsü çalışıyor. Kullanıcı aynı uygulamayı **kendi sunucusunda, Docker Compose ile** çalıştırmak istiyor: sürekli
açık, bilgisayardan bağımsız, telefondan (Telegram) ve tarayıcıdan erişilebilir. Satış/çok müşterili kullanım değil;
lisans (PolyForm Noncommercial) aynen kalır.

Başarı: Kullanıcı sunucuda `docker compose up -d` çalıştırır, `docker compose logs` içindeki kurulum kodunu görür,
tarayıcıda (kendi alan adı ve HTTPS'iyle) sihirbazı açar: kod → ad → hesap → **Claude bağlantısı (API anahtarı ya da
abonelik)** → ajanlar → ofis. Konteyner yeniden başlasa da hesap, ajanlar, hafıza, çıktılar ve soru soran ajanların
oturumları kaybolmaz. Aynı kod kullanıcının Windows bilgisayarında bugünkü gibi çalışmaya devam eder.

## Hedefler

### 1. Docker Compose ile çalışma
- Repoda `Dockerfile`, `docker-compose.yml`, `.dockerignore`. `docker compose up -d` tek komutla kalkar,
  `restart: unless-stopped`.
- İmaj: Python 3.12 (yalnız stdlib) + Node.js + Claude Code CLI (`@anthropic-ai/claude-code`, npm). Uygulama root
  olmayan bir kullanıcıyla çalışır.
- **Tüm kalıcı veri tek bir volume'da (`/veri`):** hesap ve oturumlar, `ajanlar.json`, `.env` (Telegram/Claude
  ayarları), `durum/`, `kosular/`, `cikti/`, `hafiza/`, `olaylar.jsonl`, `calisma/` ve Claude Code'un kendi oturum
  kayıtları (soru soran ajanın `--resume` ile devam edebilmesi için). Kod imajda kalır.
- Sağlık kontrolü: girişsiz `GET /api/saglik` → `{"durum": "ok"}`; Compose `healthcheck` bunu kullanır.
- Ajanlar sunucuda yalnız ofisin içindeki `calisma/<ajan>` klasörlerinde çalışır (dışarıdan proje bağlanmaz).

### 2. Ağ ve erişim (TLS/alan adı kullanıcıda)
- Konteyner içinde uygulama `0.0.0.0`'a bağlanır (`OFIS_HOST`). Compose portu varsayılan olarak
  `127.0.0.1:8796:8796` açar; kullanıcı önüne kendi ters vekilini (nginx, Traefik, Caddy…) koyar. Compose'a TLS
  katmanı eklenmez.
- `OFIS_ALAN_ADI` (ör. `ofis.alanadiniz.com`): Host/Origin denetimi localhost'a ek olarak bu adı kabul eder
  (DNS rebinding ve başka sitelerden istek koruması sürer).
- `OFIS_ALAN_ADI` tanımlıysa oturum çerezi `Secure` olur (TLS'i vekil sonlandırır).

### 3. İlk kurulumu sahiplenme koruması
- Uygulama internete açıkken hesap açılmadan önceki ilk dakikalarda adresi bilen biri sihirbazı tamamlayıp ofisi
  sahiplenebilir. Bunu önlemek için: hesap yoksa ve uygulama localhost dışında dinliyorsa (`OFIS_HOST` ≠
  `127.0.0.1`), sunucu açılışta tek kullanımlık **kurulum kodu** üretir ve yalnız sunucu günlüğüne (stdout) yazar.
- Sihirbazın ilk adımı bu kodu ister; kod doğrulanmadan hiçbir kurulum adımı (ad, hesap) çalışmaz. Hesap açılınca
  kod geçersizleşir. Yerel kullanımda (`127.0.0.1`) kod istenmez — bugünkü davranış.

### 4. Claude bağlantısı (sihirbazda yeni adım + panel)
- Sihirbaz: (kurulum kodu →) ad → hesap → **Claude** → ajanlar → ofis.
- Üç seçenek:
  1. **API anahtarı** (`sk-ant-…`): kaydetmeden önce Anthropic'e ücretsiz bir istekle (`GET /v1/models`)
     doğrulanır; geçersizse kaydedilmez.
  2. **Claude aboneliği**: kullanıcının kendi bilgisayarında `claude setup-token` ile aldığı uzun ömürlü token.
     Biçim denetlenir; ücretsiz doğrulama yolu olmadığı için isteğe bağlı **"Bağlantıyı dene"** düğmesi çok kısa bir
     `claude -p` çağrısı yapar (birkaç token harcar; kullanıcıya bu söylenir).
  3. **Bu bilgisayardaki Claude Code girişini kullan**: bugünkü yerel davranış (ayar yok). Sunucuda (Docker)
     görünmez.
- Sonradan değiştirmek için üst çubukta **Claude** paneli (Telegram paneliyle aynı kalıp): bağlantı türü, anahtarın
  son 4 karakteri, "Bağlantıyı dene", "Kaldır". Anahtar/token tarayıcıya **asla** geri gönderilmez.
- Ayar `.env`'de (`OFIS_CLAUDE_API_KEY` ya da `OFIS_CLAUDE_TOKEN`); ajan/CEO/triyaj `claude` süreçlerine sırasıyla
  `ANTHROPIC_API_KEY` ya da `CLAUDE_CODE_OAUTH_TOKEN` olarak verilir. Telegram ayarları süreçlere hâlâ verilmez.
- Bağlantı yoksa ve yerel giriş de yoksa ofis açılır ama CEO/ajan çağrısı anlaşılır bir hatayla döner ("Claude
  bağlantısı kurulmadı: Claude panelinden ekle").

### 5. Koşu modu
- Ajan koşuları: Windows → konsol penceresi (bugünkü), tmux varsa → tmux (bugünkü), ikisi de yoksa (Docker) →
  **arka plan süreci** (pencere yok; çıktı yine `kosular/<id>.log`, ilerleme yine ofis ekranında).
- Terminal köprüsü (bilgisayardaki Claude Code oturumlarını gösteren özellik) sunucuda kapalı:
  `OFIS_TERMINAL_KOPRUSU=0`.

## Hedef dışı
- Çok müşterili kullanım, faturalama, lisans değişikliği.
- Compose içinde TLS/alan adı/ters vekil (kullanıcıda).
- Dışarıdan proje klasörü ya da git deposu bağlama (ajanlar `calisma/` içinde).
- Birden fazla kullanıcı/rol; e-posta ile şifre sıfırlama (sunucuda `docker compose exec ofis python sunucu.py
  --sifre-sifirla` yeter).
- Yedekleme aracı (volume'un yedeği kullanıcıda; README'de tek satır örnek).

## Anti-hedefler
- Hesap açılmadan önce internetten gelen birinin ofisi sahiplenebilmesi.
- API anahtarı/token'ın tarayıcıya, loga, olay akışına ya da repoya düşmesi.
- Konteyner yeniden başlayınca hesap, ajan, hafıza, çıktı ya da bekleyen soru oturumlarının kaybolması.
- Yerel (Windows) kullanımın bozulması ya da yerelde ek adım gerektirmesi.
- Root olarak çalışma; yeni Python bağımlılığı.

## Kısıtlar
- Yalnız Python stdlib; testler `python test_ofis.py` (+ node). Windows ve Linux.
- Mevcut güvenlik katmanları sürer: giriş kapısı, Host/Origin, kaba kuvvet beklemesi, `varsayilan_yasak_araclar`.

## Kullanıcının verdiği kararlar
- Amaç satış değil, kendi sunucusunda çalıştırmak; lisans aynen kalır.
- Erişim (alan adı, HTTPS, ters vekil) kullanıcıda.
- Ajanlar yalnız `calisma/` klasörlerinde çalışır.
- Claude bağlantısı: API anahtarı ya da abonelik, kurulum sihirbazında.

## Benim kararlarım (asistanın çağrısı)
- **Ortam değişkenleri:** `OFIS_VERI` (veri kökü; yoksa kod klasörü — bugünkü davranış), `OFIS_HOST` (varsayılan
  `127.0.0.1`), `OFIS_PORT` (var), `OFIS_ALAN_ADI`, `OFIS_TERMINAL_KOPRUSU` (varsayılan açık). Compose'da
  `OFIS_VERI=/veri`, `OFIS_HOST=0.0.0.0`, `OFIS_TERMINAL_KOPRUSU=0`, `HOME=/veri/ev` (Claude Code oturum kayıtları
  volume'da kalsın).
- **Veri yolları:** `ortak.py`'deki `AJANLAR_DOSYASI`, `OLAYLAR`, `DURUM_DIZINI`, `KOSU_DIZINI`, `CIKTI_DIZINI`,
  `HAFIZA_DIZINI`, `ENV_DOSYASI`, `port` dosyası ve göreli `cwd` çözümü (`calisma/<id>`) `VERI`'ye bağlanır. Kod,
  `CLAUDE.md`, `sablonlar/`, `on-yuz/` kodun yanında kalır; CEO çağrıları kod klasöründe (`CLAUDE.md`'yi okur) koşar.
- **Kurulum kodu:** 8 hane, `secrets`, yalnız bellekte; her açılışta (hesap yoksa) yenisi; günlükte belirgin bir
  kutu içinde ve hangi komutla görüleceğiyle (`docker compose logs ofis`). Yanlış kod denemeleri giriş kaba kuvvet
  sayacına eklenir.
- **API anahtarı doğrulaması** stdlib `urllib` ile; ağ yoksa anlaşılır hata ("Anthropic'e ulaşılamadı; ağı
  kontrol et"), anahtar kaydedilmez. Hata mesajlarında anahtar yer almaz.
- **"Bağlantıyı dene"**: `claude -p --model haiku --no-session-persistence --tools ""` ile "Yalnız OK yaz" isteği,
  30 sn zaman aşımı; sonuç ve (varsa) `total_cost_usd` panelde gösterilir.
- **Arka plan koşusu**: `subprocess.Popen(..., start_new_session=True, stdout/err → kosular/<id>.konsol.log)`;
  meşgul denetimi bugünkü gibi pid ile.
- **İmaj**: `python:3.12-slim` + NodeSource Node 22 + `npm i -g @anthropic-ai/claude-code@latest` (sürüm build
  argümanıyla sabitlenebilir); kullanıcı `ofis` (uid 1000); `/veri` sahibi bu kullanıcı.
- **README**: "Sunucuda çalıştırma" bölümü — `.env` örneği (`OFIS_ALAN_ADI`), `docker compose up -d`,
  `docker compose logs ofis` ile kurulum kodu, nginx/Caddy için örnek vekil satırı, yedek için tek satır.
- **Testler**: veri kökünün yer değiştirmesi, Host/Origin'de alan adı kabulü, `Secure` çerez, kurulum kodu
  (yokken 403, yanlışken 403 + sayaç, doğruyken akış), Claude ayarlarının panel uçları (anahtar sızmaz, sahte
  doğrulayıcıyla), alt süreç ortamına doğru değişkenin konması (Telegram'ın konmaması), arka plan koşu modunun
  seçimi, `/api/saglik` girişsiz. Docker imajının kendisi elle denenir (`docker compose up --build`, sihirbaz, bir
  ajan koşusu).

### Gözden geçirme sonrası netleşenler (asistanın çağrısı)
- **`CLAUDE.md` veri klasöründe:** `VERI/CLAUDE.md` yoksa açılışta koddaki şablondan kopyalanır; CEO çağrıları ve
  triyaj `VERI`'de koşar (oradaki `CLAUDE.md`'yi okur). Ajanların `calisma/<id>` klasörleri `VERI` altında olduğu
  için ajanlar bu kuralları bugünkü gibi üst klasörden alır. Sunucuda düzenlenebilir, imaj yenilenince kaybolmaz.
  Yerelde `VERI` = kod klasörü olduğu için davranış değişmez.

- **Kullanıcı kararı — sunucuda ajanlar kısıtlı** (`OFIS_SUNUCU=1`, Compose'da açık; yerelde kapalı, bugünkü
  davranış). Amaç: web'den okuduğu bir talimatla kandırılan bir ajan Claude anahtarını ya da hesap/oturum
  dosyalarını ele geçirip dışarı sızdıramasın.
  - **Ayrı kullanıcı:** uygulama `ofis` (uid 1000) olarak çalışır; ajan `claude` süreçleri `ajan` (uid 1001)
    kullanıcısıyla başlatılır (`sudo -u ajan`, sudoers'ta yalnız `claude` ikilisi için, parolasız; anahtar
    `--preserve-env` ile yalnız ilgili değişken). Gizli dosyalar (`hesap.json`, `oturumlar.json`, `.env`) `VERI/gizli/`
    altında, sahibi `ofis`, izin 0700: `ajan` kullanıcısı hiçbir araçla okuyamaz. `calisma/` ve `ev-ajan/` (Claude Code
    oturum kayıtları, `--resume` için) `ajan`'a ait. CEO/triyaj çağrıları araçsız olduğu için `ofis` olarak kalır.
  - **Komut yetkisi daraltılır:** sunucuda "Komut çalıştırabilir" serbest `Bash` vermez; yalnız güvenli kalıplar:
    `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git add:*)`, `Bash(git commit:*)`,
    `Bash(ls:*)`, `Bash(npm test:*)`, `Bash(pytest:*)`, `Bash(python -m pytest:*)`. `ajanlar.json`'da serbest `Bash`
    yazan eski ajanlar koşuda bu kalıplara indirgenir. Ek yasaklar: `Bash(env:*)`, `Bash(printenv:*)`,
    `Read(/proc/**)` (süreç ortamından anahtar okunmasın).
  - **Çalışma klasörü `VERI/calisma` dışında olamaz:** formda reddedilir; dosyada dışarıyı gösteren ajan
    "kurulmadı" sayılır ve koşturulmaz.
  - Arayüzde (Ajanlar formu) sunucu modunda yetki açıklaması buna göre değişir ("Komut: yalnız git ve test
    komutları").

## İnşa edenin kararına bırakılanlar
- Claude panelinin ve sihirbaz adımının görsel düzeni (mevcut stil).
- Dockerfile katman sırası, `.dockerignore` içeriği.
- README'deki vekil örneğinin hangi sunucu için olacağı.
