![Ajan Ofisi](docs/kapak.jpg)

# Ajan Ofisi

Claude Code ajanlarını 3D bir ofiste gösteren yerel arayüz. Her ajan bir masada oturan bir kedi; iş gelince uyanır,
çalışırken ekranında ne yaptığı görünür, bitince çıktısı "CEO soruyor" kartına düşer ve kedi yeniden uyur.
Boştayken hiçbir model çağrılmaz: **0 token**.

![Ajan Ofisi demo modu](docs/ekran.png)

- **Arayüz:** three.js ile prosedürel 3D ofis (fotoğraf ya da model dosyası yok), tıklanınca meme pozuna geçen kediler,
  oda/ajan panelleri, canlı akış, token sayacı, Web Audio ile küçük sesler, demo modu.
- **Sunucu:** yalnız Python standart kütüphanesi, yalnız `127.0.0.1`. Ajanları `claude -p` ile koşturur.
- **Bağımlılık:** Python 3.10+, [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude` komutu), `tmux` (yalnız ofisten görev verirken; kendi oturumlarını izlemek için
  tmux gerekmez, düz terminal, VS Code ya da masaüstü uygulaması da görünür).
  Ön yüz three.js'i CDN'den (unpkg) yükler.

## Hızlı deneme (hiçbir şey bağlamadan)

```bash
cd on-yuz && python3 -m http.server 8000
# tarayıcıda: http://127.0.0.1:8000/?demo=1
```

`?demo=1` arka uca hiç istek atmaz; örnek ajanlar (`on-yuz/demo-veri.json`) kendiliğinden iş alıp bitirir.
Alt kutuya "blog taslağı yaz" gibi bir şey yazarsan sahte CEO işi uygun ajana dağıtır. `?oto=0` otomatik koşuları
kapatır, `?hafif=1` düşük çözünürlük ve küçük gölgeyle çizer. (Ön yüz ES modülü kullandığı için dosyayı çift tıklayıp
`file://` ile açmak çalışmaz; yukarıdaki gibi basit bir sunucu yeter.)

## Kurulum

1. **Sunucuyu başlat.**
   ```bash
   python3 sunucu.py            # http://127.0.0.1:8796, doluysa sonraki boş port (./port dosyasına yazılır)
   tmux attach -t ofis          # koşan ajanları canlı izle (her koşu ayrı pencere)
   # Windows: tmux gerekmez; her koşu kendi konsol penceresinde açılır.
   ```
2. **Tarayıcıda aç:** `http://127.0.0.1:8796`. İlk açılışta **kurulum sihirbazı** gelir:
   1. **Adın** (selamlamada görünür) ve isteğe bağlı ofis adı.
   2. **Hesap:** kullanıcı adı + şifre (en az 8 karakter). Hesabı açınca giriş yapılmış olursun.
   3. **Ajanlar:** "Boş başla" ya da bir **sektör şablonu** seç; şablonun ajanlarından istediklerini işaretleyip ekle.
   4. **Ofise gir.**
3. Sonraki her açılışta **giriş ekranı** gelir. Ajan eklemek, düzenlemek, silmek için üstteki **Ajanlar** sekmesini
   kullan: ad, oda (var olan ya da yeni oda + görünüm) ve "ne iş yapar" yeter; çalışma klasörü, model, yetkiler,
   hazır görevler "Gelişmiş" bölümünde. Çalışma klasörünü boş bırakırsan ofisin içinde `calisma/<ajan>/` açılır.
   Silinen ajanın hafızası ve çıktıları diskte kalır; CEO silinemez.

Bir kediye tıkla → panelden hazır görev ver, ya da alttaki kutudan CEO'ya derdini anlat.

### Sunucuda çalıştırma (Docker Compose)
Ofisi bilgisayarından bağımsız, sürekli açık bir sunucuda çalıştırmak için (Telegram köprüsü de kesintisiz çalışır):

```bash
git clone https://github.com/rmkola/ajan-ofisi.git && cd ajan-ofisi
echo "OFIS_ALAN_ADI=ofis.alanadiniz.com" > .env     # vekilinin kullandığı adres (HTTPS)
docker compose up -d --build
docker compose logs ofis                             # ilk açılışta KURULUM KODU burada
```

- **Erişim sende:** uygulama yalnız `127.0.0.1:8796`'ya açılır; önüne kendi ters vekilini koy ve HTTPS'i orada
  sonlandır. Örnek (Caddy): `ofis.alanadiniz.com { reverse_proxy 127.0.0.1:8796 }` · nginx:
  `proxy_pass http://127.0.0.1:8796; proxy_set_header Host $host; proxy_buffering off;` (canlı olay akışı için).
  `OFIS_ALAN_ADI` tanımlıyken oturum çerezi `Secure` olur ve yalnız bu adres (ve localhost) kabul edilir.
- **İlk kurulum kodu:** uygulama internete açıkken hesap açılmadan önce adresi bulan biri ofisi sahiplenemesin diye
  sihirbaz, sunucu günlüğündeki tek kullanımlık 8 haneli kodu ister. Hesap açılınca kod geçersizleşir.
- **Claude bağlantısı:** sihirbazda ya da üstteki **Claude** panelinden: **API anahtarı** (kaydetmeden önce ücretsiz
  doğrulanır) ya da **Claude aboneliği** (kendi bilgisayarında `claude setup-token` çalıştır, çıkan `sk-ant-oat…`
  metnini yapıştır). "Bağlantıyı dene" çok kısa bir çağrıyla birkaç token harcar. Anahtar tarayıcıya geri gönderilmez.
- **Veriler** tek bir Docker volume'unda (`ofis-veri` → `/veri`): hesap, ajanlar, hafıza, çıktılar, ayarlar,
  `CLAUDE.md` (sunucuda düzenlenebilir) ve Claude oturum kayıtları. Güncelleme: `git pull && docker compose up -d
  --build` (veri kalır). Yedek: `docker run --rm -v ajan-ofisi_ofis-veri:/veri -v "$PWD":/yedek alpine tar czf
  /yedek/ofis-yedek.tgz -C /veri .`
- **Sunucuda ajanlar kısıtlı.** Amaç: web'den okuduğu bir talimatla kandırılan bir ajan Claude anahtarını ya da
  hesabını ele geçiremesin.
  - Ajanların `claude` süreçleri ayrı bir kullanıcıyla (`ajan`) çalışır; hesap/oturum/ayar dosyalarını
    (`/veri/gizli`) işletim sistemi düzeyinde okuyamaz.
  - "Komut çalıştırabilir" yetkisi sunucuda **yalnız `ls`** verir (git ve test komutları, ajanın kendi yazdığı kodu
    çalıştırabildiği için kapalı); `env`, `printenv` ve `/proc` okumak yasaktır.
  - Ajanlar kendi klasörlerine Claude Code ayarı (`.claude/`), `.mcp.json` ya da git hook'u yazamaz; yazsalar da
    sunucuda proje ayarları yüklenmez.
  - Ajanlar yalnız `calisma/<ajan>` klasörlerinde çalışır.
  - Bilmen gerekenler: Claude anahtarı ajanın `claude` sürecinin ortamında durur; okunması yukarıdaki araç yasaklarıyla
    engellenir (Claude Code'un izin kurallarına dayanır). Ajanlar `gizli/` dışındaki ofis verilerini (ajan listesi,
    çıktılar, hafıza, günlükler) okuyabilir ve birbirlerinin `calisma/` klasörüne yazabilir. Yanlış şifre/kod
    beklemesi küresel olduğu için adresi bilen biri girişini birkaç dakika geciktirebilir (ele geçiremez).
- **Şifre sıfırlama:** `docker compose exec ofis python sunucu.py --sifre-sifirla`
- Yalnız Compose dosyasındaki **named volume** desteklenir (bind mount'ta klasör sahiplikleri kurulmaz; konteyner
  açıklayıcı bir hatayla durur).
- Sunucuda koşular pencere açmadan arka planda çalışır (ham çıktı `/veri/kosular/<id>.konsol.log`); terminal köprüsü
  (bilgisayarındaki Claude Code oturumlarını gösteren özellik) sunucuda kapalıdır.

### Eğlence odası ve kedi yatakları
Ofiste her zaman bir **Eğlence Odası** vardır (ajan atanmaz): PlayStation'lı TV, kanepe, bilardo, iki tavla masası,
çay-kahve köşesi ve koltuklar. **Gündüz (08:00–19:59)** işi olmayan kediler masadan kalkıp buraya zıplar; kimi oyun
oynar, kimi bilardo ya da tavla başındadır, ara sıra başlarının üstünde "Miyaw", "Mır mır" balonları çıkar. Yerler 3
dakikada bir değişir. **Gece (20:00–07:59)** boştaki kediler masada değil, kendi odalarının yatağında uyur. İş gelince
kedi masasına döner, bitince yine molaya/yatağa gider. Hepsi tarayıcıda olur: model çağrısı yok, **0 token**.
Denemek için adrese `?saat=23` (gece) ya da `?saat=12` (gündüz) ekleyebilirsin.

### Sektör şablonları
Kurulumda ya da **Ajanlar → Şablondan ekle** ile: **Yazılım ekibi**, **Influencer / içerik üreticisi**, **Dijital
pazarlama ajansı**, **E-ticaret mağazası**, **Küçük işletme ön büro**, **Eğitim / online kurs**, **Danışmanlık / ajans
hesap yönetimi**. Her biri 4-7 ajan, 2-4 oda ve ajan başına 2-3 hazır görevle gelir; ofiste zaten olan ajan ikinci kez
eklenmez. Şablonlar `sablonlar/<id>.json` dosyalarıdır; kendi şablonunu aynı biçimde ekleyebilirsin.

### Giriş ve şifre
- Tek kullanıcı: ofisin sahibi. Şifre düz metin saklanmaz (`hashlib.scrypt`, tuzlu), `durum/hesap.json` (0600).
- Oturum, JavaScript'in okuyamadığı (`HttpOnly`) ve başka sitelerden gönderilmeyen (`SameSite=Strict`) bir çerezle
  30 gün sürer; **Çıkış** düğmesi oturumu kapatır.
- 5 yanlış denemeden sonra her deneme arasında artan bekleme (en çok 5 dakika).
- **Şifreni unuttuysan** sunucunun çalıştığı bilgisayarda: `python3 sunucu.py --sifre-sifirla` (tüm oturumlar kapanır).
- Demo modu (`?demo=1`) girişsiz çalışır, arka uca hiç istek atmaz.

### Elle yapılandırma (ileri düzey)
Arayüz yerine dosyayla çalışmak istersen `ajanlar.json`'ı doğrudan düzenleyebilirsin (`ajanlar.example.json` örnek;
dosya yoksa sunucu yalnız CEO'lu bir tane oluşturur). `cwd` göreliyse ofis klasörüne göre çözülür; `~`
kullanabilirsin. Klasörü olmayan ajan "kurulmadı" sayılır ve koşturulmaz. `ajanlar.json` ve `kopru.json`
`.gitignore`'dadır; her arayüz kaydında bir önceki hâl `ajanlar.json.bak` olarak tutulur. Terminal köprüsü için
isteğe bağlı: `cp kopru.example.json kopru.json`.

### Odalar ve ajan sayısı
- **İstediğin kadar ajan, istediğin kadar oda.** Ofis `ajanlar.json`'dan kurulur: ajanın `oda` alanına ne yazarsan o oda
  açılır. Yalnız ajanı olan odalar sahnede görünür; CEO odası her zaman ortadadır. 1 ajanla da 30 ajanla da maket
  kadraja sığar.
- **Oda listede yoksa otomatik açılır.** Ad id'den türer (`ses-studyosu` → "Ses Studyosu"), renk id'ye göre sabit bir
  pastel setten gelir. `odalar` listesine yazarsan `ad`, `aciklama`, `not` senin yazdığın olur; listedeki sıra sahnedeki
  sırayı belirler. Oda id'si harf, rakam, `_` ve `-`, en çok 40 karakter; `oda` alanı boşsa ajan "Genel" odasına oturur.
- **Hazır temalar (görünüm):** `ceo`, `yazi`, `kod`, `tasarim`, `sosyal`, `arastirma`, `gun-sonu`, `atolye`, `bakim`,
  `posta`, `veri`. Odanın `odalar` kaydına `"tema": "veri"` yazarsan oda o temanın rengi ve eşyalarıyla (raf, ilham
  panosu, sunucu rafları…) gelir; `tema` yoksa oda id'si bir tema adıysa o kullanılır. Aynı temayı birden çok oda
  kullanabilir. Arayüzde yeni oda eklerken "Görünüm" seçicisi bunu yazar.
- **Masalar kendiliğinden dizilir.** Oda ajan sayısına göre genişler; 4'ten fazla ajan olunca masalar iki sıra olur.
  Masanın yerini elle vermek istersen ajana `"yer": {"x": 1.2, "lz": 1.2, "ayak": true}` ekle (`x` oda ortasına göre,
  `lz` derinlik, `ayak` ekran ayaklı).

En küçük `ajanlar.json` (3 ajan, 2 iş odası; `cwd` ve prompt'ları kendine göre doldur):
```json
{
  "varsayilan_yasak_araclar": ["Read(**/.env)", "Read(**/.env.*)", "Read(~/.env)", "Bash(rm:*)", "Bash(git push:*)", "Bash(curl:*)", "Bash(open:*)"],
  "ajanlar": [
    { "id": "ceo", "ad": "CEO", "oda": "ceo", "cwd": ".", "model": "sonnet", "ne_zaman": "istek",
      "ne_zaman_metin": "Sen konuşunca", "aciklama": "İşi ajanlara dağıtır.", "izinli_araclar": [], "hazir_gorevler": [] },
    { "id": "yazar", "ad": "Yazar", "oda": "yazi", "cwd": "~/notlar", "model": "sonnet", "ne_zaman": "istek",
      "ne_zaman_metin": "İstek gelince", "aciklama": "Notlardan taslak çıkarır.", "izinli_araclar": ["Read", "Glob", "Grep"],
      "hazir_gorevler": [{ "etiket": "Taslak yaz", "prompt": "<kendi prompt'un>" }] },
    { "id": "muhasebeci", "ad": "Muhasebeci", "oda": "muhasebe", "cwd": "~/faturalar", "model": "haiku", "ne_zaman": "istek",
      "ne_zaman_metin": "İstek gelince", "aciklama": "Faturaları özetler.", "izinli_araclar": ["Read", "Glob"],
      "hazir_gorevler": [{ "etiket": "Ay özeti", "prompt": "<kendi prompt'un>" }] }
  ]
}
```
Burada `muhasebe` hazır tema değil; oda kendiliğinden açılır (`odalar`'a `{"id": "muhasebe", "ad": "Muhasebe",
"tema": "veri"}` eklersen veri temasıyla gelir). Güvenlik yasakları (`.env` okuma, `rm`, `git push`, `curl`, `open`)
dosyada olmasa da her ajana eklenir; `varsayilan_yasak_araclar`'a yazdıkların bunlara eklenir.

`CLAUDE.md` CEO'nun anayasasıdır; ofisinin kurallarını oraya yaz.

## Mimari

```
tarayıcı (on-yuz/)  ──GET/POST──▶  sunucu.py (127.0.0.1)  ──tmux new-window──▶  kosucu.py  ──stdin──▶  claude -p
       ▲                               │   ▲                                         │
       └──────── SSE: olaylar ─────────┘   └──── olaylar.jsonl ◀── ilerleme, usage, bitiş ┘
                                        kopru.py (salt okuma) ◀── ~/.claude/sessions + transkriptler
```

### CEO = ana yapılandırma
Bu klasör CEO'dur. Proje klasörleri **taşınmaz**; `ajanlar.json` her ajanın `cwd`'sini, modelini, izinli/yasak
araçlarını ve hazır görevlerini tutar. CEO araçsız tek bir `claude -p --json-schema` çağrısıdır: isteği okur,
`{"cevap": "...", "atamalar": [{"ajan", "prompt"}]}` döndürür. Sunucu JSON'u doğrular (bilinmeyen ajan, kurulmamış
klasör, boş/uzun prompt, en fazla 5 atama); bozuksa **hiçbir koşu başlamaz**. `tetik_kelime` alanı olan bir ajan
(ör. posta) yalnız istekte o kelime geçince atanabilir.

### Her ajan = bir proje klasörü
Ajan kendi `cwd`'sinde çalışır ve `oda` alanındaki odaya oturur. Odalar ajanlardan türer: CEO ortada, diğerleri
üst sıra, CEO'nun iki yanı ve alt sıraya dengeli dağılır; kaide, ışık ve kamera bu yerleşime göre hesaplanır
(bkz. "Odalar ve ajan sayısı").

### Ofis koşusu: iş gelince uyanır, boşta 0 token
Buton (`POST /api/gorev`) ya da CEO bir koşu isteyince sunucu argümanları `kosular/<id>.arg.json`'a yazar ve tmux
`ofis` oturumunda yeni pencerede `kosucu.py`'yi başlatır. Koşucu:
- ajan ayarını argüman dosyasından değil `ajanlar.json`'dan okur;
- `hafiza/<ajan>.md`'yi görev şablonuna gömer, prompt'u `claude -p`'ye **stdin'den** verir;
- stream-json'u `kosular/<id>.log`'a yazar, ilerleme olaylarını `olaylar.jsonl`'e düşer;
- sonucu `cikti/<ajan>/<id>.md`'ye koyar; çıktıdaki `<hafiza_ekle>` bloğunu tarihli madde olarak hafızaya ekler.

Sunucu `olaylar.jsonl`'i SSE ile ön yüze akıtır. Hiçbir zamanlayıcı, döngü ya da "nabız" model çağırmaz; kedi
uyurken harcama sıfırdır. `"yalin": true` olan ajan genel CLAUDE.md/kurallar/MCP yüklenmeden koşar (küçük işlerde
bağlam ve token belirgin azalır).

### Terminal köprüsü: kendi açtığın Claude Code oturumları
`kopru.py` sunucuda 2 saniyelik bir iş parçacığıdır ve **salt okur**: `~/.claude/sessions/<pid>.json` canlı oturumları,
`~/.claude/projects/<cwd>/<oturum>.jsonl` transkripti verir; transkript ofsetle yalnız yeni satırlardan okunur.
**Açtığın her oturum ofiste görünür**, `kopru.json` olmasa da. `kopru.json` yalnız hangi oturumun hangi ajanda
görüneceğini seçer. Sıra: `pencere` (tmux pencere adı) > `cwd` (klasörün kendisi ya da bir üst klasörü; alt klasörde
açtığın oturum da eşlenir) > `varsayilan`. `varsayilan` yazılmazsa eşleşmeyen oturum ilk ajanda görünür; `""` yazarsan
eşleşmeyenler gizlenir. `gizle` listesindeki parçayı taşıyan oturum hiçbir eşlemeyle gösterilmez. Ofisin kendi
`claude -p` koşuları ve diğer etkileşimsiz koşular varsayılana düşmez.

**Kediye (ya da yanındaki yavruya) basınca** panelde "Şu an" bölümü açılır: o ajana bağlı her oturum, ne yaptığı ve
o oturumun alt-ajanları (görev başlığı, tür, model, son araç; son 30 dakika). Alt-ajan bilgisi
`<oturum>/subagents/agent-*.meta.json` ve transkript kuyruğundan okunur, mesaj metni okunmaz.

Kapsam: düz terminal, VS Code / IDE terminali ve tmux (`~/.claude/sessions`); Claude masaüstü uygulaması ve diğer
terminal dışı girişler (transkript taraması).

**Oturumum yanlış ajanda / hiç görünmüyor:** sunucu günlüğüne bak. Eşlenemeyen her oturum için bir kez
`köprü: oturum hiçbir ajana eşlenmedi (cwd=…, tmux penceresi=…)` satırı ve eklenecek eşleme yazılır. tmux pencereye
ad vermezsen adı `claude` / `claude.exe` olur; `pencere` eşlemesi kullanıyorsan pencereyi adlandır (`Ctrl-b ,`) ya da
`cwd` eşlemesine geç.

**Claude masaüstü uygulaması:** masaüstündeki Code oturumları `~/.claude/sessions`'a kayıt bırakmaz, yalnız transkript
yazar. Köprü 10 saniyede bir, son 30 dakikada mesaj yazılmış ve `entrypoint`'i `claude-desktop` olan transkriptleri de
açık oturum sayar. Masaüstünde tmux penceresi olmadığından bu oturumlar `cwd` eşlemesiyle (ya da `varsayilan` ile) bağlanır
(`pencere` eşlemesi terminale özgüdür); ofiste "masaüstü · <klasör>" adıyla görünür, 30 dakika mesaj gelmezse kapanır.

Olay akışına giden tek şey: **araç adı + kısa hedef** (dosya adı, arama deseni, araç açıklaması, Bash'in ilk kelimesi;
`FOO=bar` atamaları atlanır), "yeni görev aldı" bilgisi ve **usage** sayıları. **Mesaj metni, prompt, dosya içeriği
asla okunmaz, saklanmaz, loglanmaz.** Köprü Claude Code ayarlarına ya da hook'lara dokunmaz.

### Token sayacı
`token_sayac.py` ajan başına günlük token'ı `durum/token-<gün>.json`'da tutar; ofis koşusu ve terminal oturumu ayrı
sayılır, `message.id` ile tekilleştirilir (aynı mesaj iki kez sayılmaz), kayıtlar "ekle" değil "yerine koy" ile yazılır.
Dört alan gösterilir: girdi, çıktı, önbelleğe yazılan, **önbellekten okunan**. Önbellekten okunan token, her turda
yeniden okunan bağlamdır (CLAUDE.md, önceki mesajlar); yeni işlenen iş değildir ve çok daha ucuz faturalanır, ama
toplamda en büyük sayı odur. Maliyet sekmesi yalnız `claude -p`'nin bildirdiği `total_cost_usd` toplamını gösterir
(API liste fiyatı karşılığı; abonelikte faturaya yansıyan tutar değildir).

### Telegram köprüsü: ofisi telefondan yönet
Bilgisayar başında değilken ofise Telegram'dan yazarsın; ajanlar soru sorunca ya da bir şey ters gidince sana
Telegram'dan ulaşır. Dinlemek **0 token**'dır (Telegram'a dışa doğru long polling; açık port, webhook yok).

**Kurulum (2 dakika, dosya düzenlemeden):**
1. Telegram'da **@BotFather**'a `/newbot` yaz, botuna ad ver; verdiği token'ı kopyala.
2. Ofisi aç, sağ üstteki **Telegram** düğmesine bas, token'ı yapıştır, **Kaydet**. Sunucu token'ı Telegram'a
   sorarak doğrular; botun adı görünür.
3. Panel 6 haneli bir kod gösterir (10 dakika geçerli). Kendi botuna `/baslat <kod>` yaz. Panel "Bağlı" olur.
   Bot artık **yalnız senin hesabını** dinler; başkalarının mesajlarına cevap bile vermez.

Panelden gün sonu rapor saatini değiştirebilir, test mesajı gönderebilir, bağlantıyı kaldırabilirsin. Ayarlar
`.env`'e yazılır (repoya girmez, ajanların okuması yasak); token tarayıcıya geri gönderilmez. İstersen
`.env.example`'ı `.env` olarak kopyalayıp elle de kurabilirsin.

**Kullanım:**
- Düz mesaj → **CEO**. "Ne üzerinde çalışıyorsunuz?" gibi durum sorularına ofisin anlık durumuna bakarak
  cevap verir, gerekirse iş dağıtır.
- `@backend-gelistirici şu endpoint'i hızlandır` → CEO atlanır, **doğrudan o ajana** gider; bitince sonuç gelir.
- Bot'un bir mesajına **Yanıtla** ile yazarsan o işe döner: ajanın sorusuna cevap verirsen ajan **aynı oturumu
  kaldığı yerden sürdürür** (okuduğu dosyalar, yazdığı plan bağlamda kalır); sonuca "şunu da düzelt" dersen aynı
  işe devam eder.
- Sunucu kapalıyken yazdıkların (Telegram 24 saat saklar) sunucu açılınca sırayla, sorulmadan işlenir.

**Soru soran ajan ve CEO'nun karar yetkisi:** ajan kararın gereken bir noktaya gelince işi bırakır ve
`<soru tur="…">` ile sorar. `maliyet`, `buyuk-degisiklik`, `yayin-mail-para` türündeki sorular CEO'ya hiç
sorulmadan **sana** gelir. Diğerlerinde CEO, `CLAUDE.md`'deki "Karar yetkisi" kurallarına göre ya kendisi cevap
verir (ajan devam eder) ya da soruyu notuyla sana iletir; emin değilse sana sorar. CEO aynı işte en fazla 3 kez
kendi cevap verir, 4. soru sana gelir. Cevap beklerken ajan token harcamaz; arayüzde "cevap bekliyor" görünür.

**Aksilik ve rapor:** bir koşu hatayla biterse hemen haber gelir. CEO'nun kendi verdiği kararlar her gün rapor
saatinde (varsayılan 18:00) numaralı tek mesaj olarak gelir; rapora Yanıtla ile `2 geri al` yazarsan 2. maddenin
ajanına döner. Rapor model çağırmadan kayıtlardan derlenir.

### API
| Uç | Ne |
|---|---|
| `GET /api/oturum` · `POST /api/oturum` | oturum durumu (kurulum gerekli mi, giriş var mı) · `{"islem": "giris"\|"cikis"}` — girişsiz açık |
| `POST /api/kurulum` | sihirbaz adımları `{"adim": "ad"\|"hesap"\|"bitir"}` — hesap açılmadan önce girişsiz, sonra oturum ister |
| `GET /api/ajanlar` | ajanlar + `kurulu`, `durum`, `son_kosu`, `odalar`, `ayarlar` (cwd ve görev prompt'ları gönderilmez) |
| `GET /api/ajanlar/<id>` | düzenleme formu için tek ajanın tüm alanları + `yetkiler` |
| `POST /api/ajanlar` | `{"islem": "ekle"\|"guncelle"\|"sil"\|"sablon", …}`; doğrulama hatası 400, çalışan ajanı silme 409 |
| `POST /api/odalar` | `{"islem": "ekle"\|"guncelle", "ad", "tema", "aciklama"}` |
| `GET /api/sablonlar` | sektör şablonları (ad, açıklama, odalar, ajanlar; prompt'lar hariç) |
| `POST /api/gorev` | `{"ajan": id, "etiket": "<hazır görev>"}` ya da `{"ajan": id, "prompt": "..."}` → 202; çalışıyorsa 409 |
| `POST /api/ceo` | `{"metin": "...", "kuru": false}` → `{cevap, atamalar, baslatilan, reddedilen}`; `kuru: true` yalnız plan |
| `GET /api/olaylar?son=N` | SSE; son N olayı tekrar oynatır, sonra canlı |
| `GET /api/terminaller` | köprüdeki oturumlar (ajan, oda, oturum adı, durum, son araç, son hedef) |
| `GET /api/token` | bugünkü ajan başına token |
| `GET /api/sayac` | bugünkü koşu sayısı, aktif ajan, koşu başına süre/usage/maliyet |
| `GET /api/hafiza` | `hafiza/<ajan>.md` başına madde sayısı ve son 3 madde |
| `GET /api/telegram` | Telegram bağlantı durumu (token hiç dönmez, yalnız son 4 karakter) |
| `POST /api/telegram` | `{"islem": "token"\|"kod"\|"rapor_saati"\|"test"\|"kaldir", …}` |

## Güvenlik notları
- **Giriş zorunlu.** Statik sayfa ve `/api/oturum`, `/api/kurulum` dışındaki tüm `/api/*` uçları (canlı olay akışı ve
  Telegram paneli dahil) oturum ister; yoksa 401. Hesap açılınca kurulumun girişsiz adımları kapanır.
- **Yalnız `127.0.0.1`.** `Host` ve `Origin` başlıkları yalnız localhost/127.0.0.1 kabul edilir (DNS rebinding ve
  başka sitelerden istek atılmasına karşı). Sunucuyu `0.0.0.0`'a açma, ağa yayınlama.
- **Prompt shell'e string olarak birleşmez.** Komutlar liste argümanıyla kurulur, prompt `claude`'a stdin'den gider.
  Ajan id'si beyaz liste + desenle (`^[a-z0-9-]{1,40}$`), oda id'si harf/rakam/`_`/`-` ve en çok 40 karakter,
  girdi 4000 karakterle sınırlı, gövde 16 KB.
- **Dış içerik = veri.** Görev şablonu ve CEO prompt'u kullanıcı isteğini ve dosya/web/mail içeriğini etiketli
  veri olarak verir; içindeki "şunu yap" cümleleri talimat sayılmaz. Bu tek başına koruma değildir: asıl sınır
  `izinli_araclar`'ı dar tutmaktır.
- **Varsayılan yasaklar** her ajana eklenir: `.env` okuma, `rm`, `git push`, `curl`, `open`.
- **Mail gönderme, yayın, para kullanıcıda.** Hiçbir ajana bu yetki verilmez; çıktı taslaktır, onay "CEO soruyor"
  kartından gelir.
- Ön yüz ajan metinlerini `textContent` ile basar (HTML olarak yorumlanmaz).
- Çalışma verisi (`olaylar.jsonl`, `durum/`, `kosular/`, `cikti/`, `hafiza/*.md`) `.gitignore`'dadır; repoya koyma.

## Dosyalar
| Dosya | Ne |
|---|---|
| `sunucu.py` | HTTP + SSE sunucusu, giriş kapısı, CEO çağrısı, koşu başlatma (`--sifre-sifirla`) |
| `hesap.py` | hesap, şifre özeti (scrypt), oturumlar, kaba kuvvet beklemesi |
| `claude_baglanti.py` | Claude bağlantısı: API anahtarı/abonelik, doğrulama, panel işlemleri |
| `Dockerfile`, `docker-compose.yml`, `docker/giris.sh` | sunucu sürümü (Docker Compose) |
| `ajan_yonetimi.py` | `ajanlar.json` üzerinde doğrulanmış ajan/oda ekle-düzenle-sil, şablondan ekleme |
| `sablonlar/` | sektör şablonları (`<id>.json`) |
| `kosucu.py` | tek ajan koşusu (tmux penceresinde) |
| `kopru.py` | terminal köprüsü (salt okuma) |
| `token_sayac.py` | günlük token sayacı |
| `ortak.py` | yollar, ajan tablosu, olay günlüğü, `.env` okuma/yazma |
| `telegram_kopru.py` | Telegram botu: long polling, yönlendirme, eşleştirme, gün sonu raporu, panel |
| `akis.py` | olay izleyici: ajan soruları için CEO triyajı, aksilik/sonuç bildirimleri |
| `sorular.py` | sorular, CEO kararları, Telegram mesaj eşlemesi, devam kuyruğu (`durum/` altında) |
| `test_ofis.py` | bağımlılıksız self-check: `python test_ofis.py` |
| `.env.example` | Telegram ayarları şablonu (panel kullanılıyorsa gerekmez) |
| `ajanlar.example.json`, `kopru.example.json` | boş şablonlar |
| `CLAUDE.md` | CEO anayasası şablonu |
| `on-yuz/` | `index.html` (sahne + paneller), `kedi.js` (prosedürel kedi), `meme.js` (meme pozları), `portre.js` (panel avatarları), `dekor.js` (oda eşyaları), `demo-veri.json` |

## Lisans
[PolyForm Noncommercial 1.0.0](LICENSE). Kısaca:

- ✅ İndir, kendi bilgisayarında çalıştır, kendi ajanlarını bağla.
- ✅ Tasarımı istediğin gibi değiştir; ticari olmayan şekilde paylaşabilirsin (bu lisans ve telif notu korunarak).
- ❌ Satmak, ücretli bir ürüne/kursa/şablon paketine koymak ya da müşteriye ücretli hizmet olarak kurmak yasak.

Ticari kullanım için izin istersen GitHub üzerinden yaz. Bağlayıcı olan [LICENSE](LICENSE) metnidir.

---

## English (short)

**Ajan Ofisi** ("Agent Office") is a local 3D dashboard for Claude Code agents. Each agent is a procedurally modelled cat
at a desk: it wakes up when work arrives, shows what it is doing on its screen, drops its output into a review card
and goes back to sleep. Nothing runs while idle: **0 tokens**.

- **Try it without connecting anything:** `cd on-yuz && python3 -m http.server 8000`, open
  `http://127.0.0.1:8000/?demo=1`. Demo mode makes no backend requests.
- **Set up:** run `python3 sunucu.py` (stdlib only, binds to `127.0.0.1:8796`) and open it in the browser. A setup
  wizard asks your name, creates your account (scrypt-hashed password, HttpOnly session cookie, every API behind
  login) and lets you start empty or from a sector template (software, influencer, digital marketing, e-commerce,
  small-business front office, online course, consulting). Add, edit and remove agents and rooms later in the
  **Ajanlar** tab. Forgot the password: `python3 sunucu.py --sifre-sifirla`.
- **Architecture:** this folder is the "CEO" (main config). Every agent is a project folder (`cwd`). Office runs use
  `claude -p` in a tmux window, prompt via stdin, events streamed to the UI over SSE. The CEO is a single tool-less
  `claude -p --json-schema` call whose JSON plan is validated before anything starts.
- **Terminal bridge:** read-only view of Claude Code sessions you opened yourself, via `~/.claude/sessions` and the
  session transcript. Only tool name, a short target (file name, pattern) and usage numbers are forwarded; message
  text, prompts and file contents are never read into the event log or stored. Claude desktop app sessions don't
  register in `~/.claude/sessions`, so transcripts with `entrypoint: claude-desktop` and a message in the last
  30 minutes are picked up too; they map by `cwd` only (no tmux window name on desktop). Every interactive session
  shows up even without `kopru.json`: mapping order is tmux window name > `cwd` (folder or any parent) >
  `varsayilan` (defaults to the first agent; `""` hides unmapped sessions). Unmapped sessions are logged once
  with the mapping line to add. Works in a plain terminal, an IDE terminal or tmux; desktop app and other non-terminal
  entrypoints are found by transcript scan. Clicking an agent lists its live sessions and their subagents (task title,
  type, model, last tool) from `subagents/*.meta.json`; message text is never read.
- **Token counter:** per-agent daily usage, de-duplicated by message id; "cache read" tokens are re-read context,
  not new work.
- **Security:** localhost only (Host/Origin checked), no string concatenation into a shell, external content is
  treated as data, sending mail / publishing / spending money always stays with the user.

UI text is Turkish. License: PolyForm Noncommercial 1.0.0 — free for personal and other noncommercial use, modify as you like; selling or commercial use is not permitted.
