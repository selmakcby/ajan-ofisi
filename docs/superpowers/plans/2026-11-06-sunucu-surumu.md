# Sunucu Sürümü Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajan Ofisi'nin Docker Compose ile sunucuda çalışan sürümü: tek veri volume'u, kurulum kodu, alan adı/Secure
çerez, sihirbazda ve panelde Claude bağlantısı (API anahtarı/abonelik), arka plan koşuları ve sunucuda kısıtlı ajanlar
(ayrı kullanıcı, daraltılmış Bash, `calisma/` dışı yasak). Yerel kullanım değişmez.

**Architecture:** Davranış ortam değişkenleriyle seçilir (`OFIS_VERI`, `OFIS_HOST`, `OFIS_ALAN_ADI`, `OFIS_SUNUCU`,
`OFIS_TERMINAL_KOPRUSU`). `ortak.py` yolları ve sunucu kurallarını, yeni `claude_baglanti.py` Claude ayarını/doğrulamayı
taşır; `kosucu.py` koşu modunu ve `sudo -u ajan` sarmalamasını yapar; Docker dosyaları kullanıcıları/izinleri kurar.

**Tech Stack:** Python 3.12 stdlib, Node 22 + `@anthropic-ai/claude-code`, Docker Compose, sudo.

**Spec:** `docs/superpowers/specs/2026-11-06-sunucu-surumu-design.md`

## Global Constraints
- Yalnız stdlib; testler `python test_ofis.py` (+node). Windows + Linux. Yerelde (`OFIS_*` yokken) davranış aynı.
- Anahtar/token tarayıcıya, loga, olaya, hata mesajına düşmez; panel yalnız son 4 karakteri döner.
- Sunucu modunda (`OFIS_SUNUCU=1`): gizli dosyalar `VERI/gizli/` (0700), ajan süreçleri `sudo -u ajan`, serbest `Bash`
  yok (izinli kalıplar spec'teki liste), ek yasak `Bash(env:*)`, `Bash(printenv:*)`, `Read(/proc/**)`, `cwd` yalnız
  `VERI/calisma/` altında.
- Kurulum kodu: 8 hane, bellekte, yalnız stdout; `OFIS_HOST` ≠ `127.0.0.1` ve hesap yokken istenir.

## Review Focus
1. **Volume sahipliği/izinleri** (ilk `up`, yeniden başlatma, imaj yenileme): `ofis` yazabilmeli, `ajan` `calisma/`'ya
   yazabilmeli, `gizli/`'yi okuyamamalı. Test: Task 6 elle (konteynerde `sudo -u ajan cat /veri/gizli/.env` → izin yok).
2. **Ters vekil arkasında Host/Origin** (`Host: ofis.alanadi.com`, `Origin: https://ofis.alanadi.com`) → kabul; başka
   alan → 403. Test: Task 2 `test_alan_adi_kabul`.
3. **Kurulum kodu kaba kuvveti** → yanlış kod giriş sayacına eklenir, 6. denemeden sonra 429. Test: Task 2.
4. **Eski `ajanlar.json`'da serbest `Bash` ya da dış `cwd`** → sunucuda indirgenir / kurulmadı. Test: Task 4.
5. **Anthropic'e ulaşılamaması / yanlış anahtar** → kaydedilmez, anlaşılır mesaj, anahtar mesajda yok. Test: Task 3.

---

### Task 1: Veri kökü, gizli dizin, CLAUDE.md tohumu, sağlık ucu
**Files:** `ortak.py`, `hesap.py`, `sunucu.py`, `kosucu.py`, `kopru.py`, `test_ofis.py`
**Interfaces (Produces):**
- `ortak.VERI = os.environ.get("OFIS_VERI") or KOK`; `AJANLAR_DOSYASI`, `OLAYLAR`, `DURUM_DIZINI`, `KOSU_DIZINI`,
  `CIKTI_DIZINI`, `HAFIZA_DIZINI`, `port` dosyası, `cwd_coz` göreli kökü → `VERI`. `kosucu.YALIN_DIZIN` → `VERI/durum`.
- `ortak.SUNUCU = os.environ.get("OFIS_SUNUCU") == "1"`; `ortak.gizli_dizin() -> str` (`VERI/gizli` sunucuda, yoksa
  `DURUM_DIZINI`); `ortak.env_dosyasi() -> str` (`gizli_dizin()/.env` sunucuda, yoksa `VERI/.env`). `env_oku/env_yaz/
  telegram_ayari` varsayılan yolu `env_dosyasi()`. `hesap.py` dosyaları `gizli_dizin()` altında.
- `ortak.claude_md_tohumla() -> None`: `VERI != KOK` ve `VERI/CLAUDE.md` yoksa koddakini kopyalar. CEO/triyaj
  `claude_json` `cwd=ortak.VERI`.
- `GET /api/saglik` girişsiz → `{"durum": "ok"}`.
- [ ] Testler: `test_veri_koku_ortamdan` (alt süreçte `OFIS_VERI=tmp` → yollar tmp altında, `OFIS_SUNUCU=1` → gizli
  yollar), `test_claude_md_tohum`, `test_saglik_girissiz` (HTTP). RED → uygula → GREEN → commit.

### Task 2: Ağ — OFIS_HOST, alan adı, Secure çerez, kurulum kodu
**Files:** `sunucu.py`, `test_ofis.py`
**Interfaces:** `HOST = os.environ.get("OFIS_HOST", "127.0.0.1")`; `ALAN_ADI = os.environ.get("OFIS_ALAN_ADI", "")`;
`IZINLI_HOST`/`IZINLI_ORIGIN` alan adını (tam eşleşme, isteğe bağlı port; Origin `http(s)://`) da kabul eder;
`cerez()` alan adı varsa `; Secure` ekler. `KURULUM_KODU: str | None` — `main()`'de `HOST != "127.0.0.1"` ve hesap
yoksa `secrets` ile 8 hane, kutu içinde stdout'a. `POST /api/kurulum` her adımda (hesap yokken ve kod varsa)
`veri["kod"]`'u `hmac.compare_digest` ile denetler; yanlış/eksik → 403 + `hesap.giris_hatasi()`, beklemedeyse 429.
`GET /api/oturum` hesap yokken `"kod_gerekli": bool` döner.
- [ ] Testler: `test_alan_adi_kabul`, `test_secure_cerez`, `test_kurulum_kodu` (kodsuz 403, yanlış 403, 7. deneme 429,
  doğru → akış; kod yokken eski davranış). RED → GREEN → commit.

### Task 3: Claude bağlantısı (arka uç)
**Files:** Create `claude_baglanti.py`; Modify `ortak.py` (`alt_surec_ortami`), `sunucu.py` (uçlar), `test_ofis.py`
**Interfaces:** `claude_baglanti.durum(env_yolu=None) -> dict` → `{"tur": "api"|"abonelik"|"yerel"|"yok", "son4",
"sunucu": bool}` (yerelde ayar yoksa `"yerel"`, sunucuda `"yok"`); `islem(veri, dogrulayici=api_dogrula,
deneyici=baglanti_dene) -> dict` (`anahtar`/`token`/`dene`/`kaldir`; hata `ValueError`); `api_dogrula(anahtar) -> None`
(`GET https://api.anthropic.com/v1/models`, `x-api-key`, `anthropic-version: 2023-06-01`; 401 → "Anahtar geçersiz",
ağ → "Anthropic'e ulaşılamadı"; mesajda anahtar yok); `baglanti_dene() -> dict` (`claude -p --model haiku
--no-session-persistence --tools "" --output-format json`, "Yalnız OK yaz", 30 sn) → `{"tamam", "yanit",
"maliyet_usd"}`. Biçimler: API `^sk-ant-[A-Za-z0-9_-]{20,}$`, token `^sk-ant-oat[A-Za-z0-9_-]{20,}$`.
`.env` anahtarları `OFIS_CLAUDE_API_KEY` / `OFIS_CLAUDE_TOKEN` (biri yazılınca diğeri silinir). `ortak.alt_surec_
ortami()` bunları `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` olarak ekler, `OFIS_*`'ı çıkarır.
Uçlar: `GET /api/claude` → `durum()`, `POST /api/claude` → `islem()` (400). Oturum yanıtına `"sunucu": SUNUCU`.
- [ ] Testler: `test_claude_api_anahtari` (sahte doğrulayıcı: geçersiz → .env değişmez; geçerli → kaydedilir, son4,
  anahtar yanıtta yok), `test_claude_token_bicim`, `test_claude_ortama_gecer` (api → `ANTHROPIC_API_KEY`, telegram
  yok), `test_claude_dogrulama_hatasi_anahtar_sizdirmaz`, `test_claude_girissiz_401`. RED → GREEN → commit.

### Task 4: Koşu modu ve sunucu kısıtları
**Files:** `kosucu.py`, `sunucu.py` (`gorev_baslat`), `ortak.py`, `ajan_yonetimi.py`, `kopru.py`, `test_ofis.py`
**Interfaces:** `ortak.kosu_modu() -> "konsol"|"tmux"|"arka"` (win32 → konsol; tmux bulunursa → tmux; yoksa arka);
`gorev_baslat` arka modda `Popen(..., start_new_session=True, stdout/err → kosular/<id>.konsol.log)`.
`ortak.SUNUCU_BASH = [spec'teki 9 kalıp]`, `ortak.SUNUCU_YASAK = ["Bash(env:*)", "Bash(printenv:*)", "Read(/proc/**)"]`;
`ortak.sunucu_araclari(izinli: list) -> list` (serbest `"Bash"` → `SUNUCU_BASH`, diğer `Bash(...)` kalıpları da yalnız
listedekiler kalır); `ortak.yasakli_araclar` sunucuda `SUNUCU_YASAK`'ı da ekler. `ortak.calisma_icinde(cwd) -> bool`;
sunucuda `ajanlari_yukle` dışarıyı gösteren ajanı `kurulu=False` yapar (CEO hariç), `ajan_yonetimi` formda reddeder.
`kosucu.komut_kur` sunucuda komutun başına `["sudo", "-n", "-u", "ajan", "--preserve-env=HOME,ANTHROPIC_API_KEY,
CLAUDE_CODE_OAUTH_TOKEN,DISABLE_AUTOUPDATER", "--"]` ekler ve `HOME=VERI/ev-ajan`; sunucuda oluşturulan
`calisma/<id>`, `cikti/<id>`, `durum/yalin-cwd` klasörleri `0o2770`. `OFIS_TERMINAL_KOPRUSU=0` → köprü başlatılmaz.
- [ ] Testler: `test_kosu_modu`, `test_sunucu_araclari`, `test_sunucu_cwd_disari_kurulmadi`, `test_sunucu_komut_sudo`,
  `test_yerelde_kisit_yok`. RED → GREEN → commit.

### Task 5: Ön yüz — kurulum kodu, Claude adımı ve paneli, sunucu yetki metni
**Files:** `on-yuz/index.html`
- Sihirbaz: `oturum.kod_gerekli` ise 1. adımda kod alanı; her `/api/kurulum` isteğine `kod` eklenir. Hesaptan sonra
  **Claude** adımı (üç seçenek; yerel seçenek `!oturum.sunucu` iken; "Bağlantıyı dene"; "Şimdilik atla"). Üst çubukta
  **Claude** düğmesi + panel (`/api/claude`). Ajanlar formunda sunucu modunda "Komut çalıştırabilir (yalnız git ve
  test komutları)".
- [ ] Elle (Playwright, yerel sunucu `OFIS_HOST=0.0.0.0`): kod sorulur, Claude adımı görünür, panel son4 gösterir,
  yanlış anahtar hatası. Commit.

### Task 6: Docker
**Files:** Create `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `docker/giris.sh`; Modify `README.md`
- `python:3.12-slim` + NodeSource 22 + `npm i -g @anthropic-ai/claude-code` + `sudo` + `git`; gruplar/kullanıcılar
  `ekip`(1500), `ofis`(1000), `ajan`(1001); sudoers: `ofis ALL=(ajan) NOPASSWD:SETENV: <claude yolu>`; `/veri`
  `ofis:ekip 0750`; giriş betiği dizinleri ve izinleri kurar (`gizli` 0700, `calisma`/`cikti` 2770, `ev-ajan` ajan
  0700 — sudo ile), `umask 027`, `exec python sunucu.py`. Ortam: `OFIS_VERI=/veri`, `OFIS_HOST=0.0.0.0`,
  `OFIS_SUNUCU=1`, `OFIS_TERMINAL_KOPRUSU=0`, `DISABLE_AUTOUPDATER=1`. Compose: port `127.0.0.1:8796:8796`, volume
  `ofis-veri:/veri`, `env_file` isteğe bağlı (`OFIS_ALAN_ADI`), healthcheck `/api/saglik`, `restart: unless-stopped`.
- [ ] Elle: `docker compose up -d --build`; günlükte kod; tarayıcıda sihirbaz; konteynerde `sudo -u ajan cat
  /veri/gizli/.env` → izin yok, `ajan` `calisma/x`'e yazabiliyor; yeniden başlatmada veri kalıyor. README "Sunucuda
  çalıştırma". Commit.
