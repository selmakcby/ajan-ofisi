# Telegram köprüsü — tasarım

Tarih: 2026-11-06 · Durum: onay bekliyor

## Amaç ve neden

Kullanıcı 7/24 bilgisayar başında değil. Ofise telefondan **direktif vermek**, ajanların **sorularına cevap
vermek** ve bir **aksilik** olduğunda haber almak istiyor. Önemsiz konularda CEO'nun kendisi karar vermesini,
verdiği kararları da **gün sonunda** Telegram'dan raporlamasını istiyor.

Başarı: telefonda Telegram'dan "@backend-gelistirici şunu düzelt" yazar, iş biter, sonuç telefona gelir. Bir ajan
"planı onaylıyor musunuz?" diye sorar; konu önemliyse soru telefona gelir, "onaylıyorum" denir, ajan kaldığı
yerden plana başlar. Önemsizse CEO karar verir, akşam raporda görünür.

## Hedefler

1. **Telegram botu = ofisin girişi.** Kullanıcı kendi oluşturduğu bir botla konuşur.
2. **Yönlendirme:**
   - Mesaj `@<ajan-id>` ile başlıyorsa → doğrudan o ajana görev (CEO atlanır).
   - Bot'un bir mesajına Telegram'da **"Yanıtla"** ile cevap verilirse → o mesajın ait olduğu ajana/soruya gider.
   - Diğer her mesaj → **CEO**.
3. **CEO ofisin durumunu bilir.** "Ne üzerinde çalışıyorsunuz?" gibi sorulara cevap verebilmesi için CEO
   çağrısına her seferinde ofisin anlık durumu verilir: her ajanın durumu (uyuyor / çalışıyor / cevap bekliyor),
   son koşularının özeti, cevap bekleyen sorular, bugün CEO'nun verdiği kararlar, açık terminal oturumları
   (`KOPRU.liste()`'den ajan, oturum adı, son araç). CEO aynı çağrıda iş de atayabilir (bugünkü `atamalar`).
4. **Ajan soru sorabilir ve cevapla kaldığı yerden devam eder.**
   - Ajan, kullanıcı kararı gerektiren bir şey olduğunda çıktısının sonuna `<soru>…</soru>` bloğu yazar
     (bugünkü `<hafiza_ekle>` gibi). Blok yoksa koşu "bitti" sayılır, varsa "cevap bekliyor".
   - Cevap gelince ajan **aynı Claude Code oturumunu** sürdürür (`claude -p --resume <session_id>`); önceki
     koşuda okuduğu dosyalar ve yazdığı plan bağlamdadır.
5. **Soru önce CEO'ya gider (triyaj).** CEO her soru için karar verir:
   - **kendim**: önemsiz → CEO cevabı yazar, ajan o cevapla devam eder, karar gün sonu raporuna kaydedilir.
     Kullanıcıya anında bildirim gitmez.
   - **kullanıcıya**: önemli ya da emin değil → soru, ajanın çıktısı ve CEO'nun 1-2 cümlelik notuyla
     Telegram'dan kullanıcıya gider.
6. **Kullanıcıya her zaman giden konular** (CEO kendisi karar veremez; `CLAUDE.md`'ye yazılır):
   - Maliyete dokunan her şey: ücretli servis/API, abonelik, ek sunucu, token/model kullanımını belirgin
     artıracak iş.
   - Modüllerde büyük değişiklik: yeni entegrasyon (SMS, ödeme, yeni dış servis — örnek: "SMS entegrasyonu
     yapalım mı?"), mimari değişiklik, modülü baştan yazma, veri yapısı değişikliği.
   - Var olan sınırlar: yayın, mail gönderme, para.
   - **Şüphede kullanıcıya sorulur.**
7. **Aksilik bildirimi:** Bir ajan koşusu `hata` ile biterse ya da CEO geçerli plan döndüremezse Telegram'a hemen
   kısa mesaj gider (ajan, kosu_id, hata satırı).
8. **Telegram'dan başlatılan işlerin sonucu** (doğrudan `@ajan` ya da Telegram'dan gelen CEO ataması) bitince
   özetiyle Telegram'a gönderilir. Arayüzden başlatılan işlerin sonucu Telegram'a gönderilmez (hata hariç).
9. **Gün sonu raporu:** CEO'nun gün içinde kendi verdiği kararlar (hangi ajan ne sordu, CEO ne cevap verdi,
   gerekçe) her gün `rapor_saati`'nde (varsayılan **18:00**) tek mesaj olarak gönderilir. Rapor **model
   çağırmadan** kayıtlardan derlenir. Rapordaki bir maddeye "Yanıtla" ile yazılırsa mesaj o ajana yeni görev
   olarak gider (yönlendirme kuralı 2 ile aynı mekanizma). O gün karar yoksa rapor gönderilmez.

10. **Telegram web arayüzünden yönetilir.** Uygulama GitHub'da herkese açık dağıtılacak; teknik olmayan bir
    kullanıcı da `.env` düzenlemeden bağlanabilmeli. Arayüzde bir **Telegram paneli**:
    - **Token:** kullanıcı BotFather'dan aldığı token'ı yapıştırır; sunucu `getMe` ile doğrular, geçerliyse
      kaydeder ve botun kullanıcı adını gösterir (ör. "@ajanofisi_bot bağlandı"); geçersizse kaydetmez, hata
      gösterir.
    - **Eşleştirme:** panel 6 haneli, tek kullanımlık, **10 dakika** geçerli bir kod gösterir ("Bota
      `/baslat 482913` yazın"). Bu kodu gönderen Telegram hesabı ofisin sahibi olarak kaydedilir; panelde
      "Eşleşti: <ad>" görünür. Yanlış/süresi geçmiş kod hiçbir şey yapmaz. Eşleşme yeni kodla değiştirilebilir.
      (Bu, önceki `/kimlik` adımının yerini alır.)
    - **Durum:** bağlı / bağlantı yok / token geçersiz / eşleşme bekleniyor; son hata.
    - **Rapor saati** değiştirilebilir. **"Test mesajı gönder"** ve **"Bağlantıyı kaldır"** düğmeleri.
    - Token tarayıcıya **geri gönderilmez**; panelde yalnız son 4 karakteri görünür.
    - Panelden yapılan değişiklik **sunucu yeniden başlatılmadan** uygulanır (bot durur/başlar).

## Hedef dışı

- Arayüzden (tarayıcıdan) soru cevaplama. Arayüz soruyu "CEO soruyor" kartında özet olarak gösterir; cevap
  Telegram'dan verilir. Sonra eklenebilir.
- Birden fazla Telegram kullanıcısı, grup sohbetleri, sesli mesaj, dosya/fotoğraf alma.
- Telegram dışı kanallar (WhatsApp, Slack, mail).
- Kullanıcı bilgisayarı kapalıyken çalışma. Bot, `sunucu.py` açıkken çalışır.

## Kesin olmaması gerekenler (anti-hedefler)

- Kullanıcıdan başkasının bota yazıp ajan koşturabilmesi.
- CEO'nun maliyet ya da büyük modül değişikliği kararını kendi vermesi.
- Boştayken model çağrılması. Telegram'ı dinlemek (long polling) ve gün sonu raporu **0 token**'dır; model
  yalnız kullanıcı yazınca, ajan soru sorunca ya da koşu başlayınca çağrılır.
- Bot token'ının repoya, loga, olay akışına ya da ajanların okuyabileceği bir yere düşmesi.
- Yeni Python bağımlılığı.

## Kısıtlar

- **Yalnız Python standart kütüphanesi** (`urllib.request`, `json`, `threading`). Proje bu ilkeyle yazılmış.
- **Windows ve Linux/macOS'ta çalışır** (bir önceki commit'te yapılan platform ayrımı korunur).
- Sunucu hâlâ yalnız `127.0.0.1`'e bağlanır. Telegram'a bağlantı **dışa doğru** long polling'dir
  (`getUpdates`, `timeout=50`); webhook, açık port ya da dış adres yoktur.
- Bugünkü güvenlik ilkeleri sürer: prompt shell'e string olarak birleşmez (stdin), girdi en fazla 4000 karakter,
  dış içerik veridir.
- Telegram mesaj sınırı 4096 karakter: uzun çıktılar kısaltılıp sonuna çıktı dosyasının yolu yazılır.

## Kullanıcının verdiği kararlar

- Telegram bağlantısı web arayüzünden yönetilir (token, eşleştirme kodu, durum, rapor saati, test, kaldır).
- Uygulama GitHub'da herkese açık dağıtılır: kurulum teknik olmayan kullanıcı için kolay, varsayılanlar güvenli.
- **Sunucu kapalıyken gelen mesajlar** (Telegram 24 saat saklar): sunucu açılınca **sorulmadan, geliş
  sırasıyla otomatik işlenir**. Long polling ofseti `durum/telegram-ofset.json`'da saklanır; aynı mesaj iki kez
  işlenmez.
- `@` yok → CEO; `@ajan` → doğrudan ajan.
- Soru → önce CEO; önemsizse CEO karar verir, önemliyse kullanıcıya.
- Önemli = maliyet + büyük modül değişikliği / yeni entegrasyon (+ yayın, mail, para).
- CEO'nun kararları gün sonunda Telegram'dan raporlanır.
- Aksilikte ajanlar kullanıcıya Telegram'dan ulaşır.

## Benim kararlarım (asistanın çağrısı, kullanıcı itiraz edebilir)

- **Yapılandırma:** bot token'ı ve kullanıcının Telegram kimliği proje kökündeki `.env` dosyasında
  (`OFIS_TELEGRAM_TOKEN`, `OFIS_TELEGRAM_KULLANICI`); ortam değişkeni varsa o önceliklidir. `.env` zaten
  `.gitignore`'da ve `varsayilan_yasak_araclar` ajanların `.env` okumasını yasaklıyor. `.env` küçük bir elle
  yazılmış ayrıştırıcıyla okunur (`ANAHTAR=deger` satırları). Rapor saati de aynı dosyada:
  `OFIS_TELEGRAM_RAPOR_SAATI=18:00` (boşsa 18:00). Şablon: `.env.example`. Token yoksa Telegram özelliği kapalıdır, sunucu eskisi
  gibi çalışır.
- **Ayarların saklanması:** panel de `.env`'e yazar (tek kaynak; ajanların okuması zaten yasak, repoya
  girmez). Sunucu yalnız `OFIS_TELEGRAM_*` satırlarını günceller/siler, diğer satırlara dokunmaz. `.env` elle
  düzenlemek de mümkündür; `.env.example` kalır ama zorunlu değildir. Ortam değişkeni varsa panel değeri
  göstermekle yetinir ve "ortam değişkeninden geliyor, panelden değiştirilemez" der.
- **Kimlik doğrulama:** yalnız eşleşmiş hesabın (`message.from.id == OFIS_TELEGRAM_KULLANICI`) mesajları
  işlenir; diğerleri sessizce yok sayılır (yalnız geçerli `/baslat <kod>` istisnadır). Eşleştirme kodu
  bellekte tutulur, dosyaya yazılmaz; sunucu yeniden başlarsa yeni kod üretilir.
- **Panel uçları:** `GET /api/telegram` (durum, bot kullanıcı adı, token'ın son 4 karakteri, eşleşen hesap adı,
  rapor saati, son hata, eşleştirme kodu varsa kendisi ve kalan süresi) ve `POST /api/telegram`
  (`{"islem": "token"|"kod"|"rapor_saati"|"test"|"kaldir", ...}`). Mevcut Host/Origin korumasının arkasında,
  yalnız `127.0.0.1`.
- **Oturum saklama:** ajan koşularından `--no-session-persistence` kaldırılır (sürdürmek için gerekli). CEO
  çağrılarında kalır. `result` olayındaki `session_id` durum dosyasına ve koşu bitiş olayına yazılır.
- **Soru durumu:** soru soran koşu bitince ajanın durumu `cevap_bekliyor` olur; `durum/<ajan>.json` soruyu,
  `session_id`'yi ve `kosu_id`'yi tutar. Ajan bu durumdayken yeni bir görev alabilir (yeni oturum açılır);
  bekleyen soru yerinde kalır ve "Yanıtla" ile hâlâ cevaplanabilir.
- **Bekleyen sorular kaydı:** `durum/sorular.json`: `{soru_id: {ajan, kosu_id, session_id, soru, durum,
  telegram_mesaj_id, otomatik_cevap_sayisi}}`. Telegram mesaj kimliği → soru eşlemesi buradan kurulur; bot
  yeniden başlasa da "Yanıtla" çalışır.
- **Sonsuz döngü koruması:** aynı iş zincirinde CEO en fazla **3** kez kendi cevap verir; dördüncü soru
  doğrudan kullanıcıya gider.
- **Meşgul ajana cevap:** cevaplanan sorunun ajanı o an başka bir koşudaysa cevap reddedilmez, **ajan başına
  tek bekleyen devam** olarak saklanır ve ajanın koşusu bitince otomatik başlar; kullanıcıya "ajan meşgul,
  bitince devam edecek" denir.
- **Kararların kaydı:** CEO'nun kendi verdiği her karar `durum/kararlar-<gün>.jsonl`'e (ajan, soru, cevap,
  gerekçe, kosu_id, zaman) eklenir; rapor buradan derlenir. Gönderilen rapor `durum/rapor-<gün>.gonderildi`
  ile işaretlenir; sunucu rapor saatinden sonra açılırsa o günün raporu açılışta gönderilir.
- **CEO triyaj çağrısı:** ayrı, araçsız bir `claude -p --json-schema` çağrısı; şema
  `{"karar": "kendim"|"kullaniciya", "cevap": str, "gerekce": str, "kullaniciya_not": str}`. Girdi: `CLAUDE.md`
  kuralları, ajanın sorusu ve çıktısının son kısmı (veri olarak etiketli). Şema bozuk gelirse güvenli taraf:
  **kullanıcıya**.
- **Olay tetikleyicisi:** triyaj, sonuç ve hata bildirimleri `sunucu.py` içinde çalışan tek bir arka plan iş
  parçacığından yapılır; bu iş parçacığı `olaylar.jsonl`'i (SSE'nin yaptığı gibi) ofsetle izler ve
  `kosu_bitti` / `ceo_bitti` olaylarına tepki verir. Böylece koşucu süreci Telegram'ı bilmez.
- **Telegram'dan gelen koşunun işaretlenmesi:** `gorev_baslat`'a giden `kaynak` alanı `telegram` olur; CEO
  ataması Telegram'dan geldiyse `telegram-ceo`. Sonuç bildirimi bu alana bakar.
- **Görev şablonu:** `kosucu.py`'deki `GOREV_SABLONU`'na `<soru>` kuralı eklenir: "Kullanıcının kararı gereken
  bir noktaya geldiysen işi orada bırak, sonuna `<soru>tek, açık soru</soru>` yaz." Devam koşusunda prompt,
  cevabı `<cevap kaynak="kullanici|ceo">…</cevap>` olarak verir.
- **Arayüz:** `canli_durum` yeni `cevap_bekliyor` durumunu döndürür; ön yüz bunu en az "bitti" gibi gösterir.
  Ayrı bir görsel (soru balonu vb.) inşa edenin kararıdır.
- **Dosya düzeni:** yeni modül `telegram.py` (Telegram API çağrıları, long polling döngüsü, yönlendirme,
  bildirim ve rapor). CEO prompt/triyaj fonksiyonları `sunucu.py`'de kalır.

### Gözden geçirme sonrası netleşenler (asistanın çağrısı)

- **Rapora cevap:** rapor tek mesajdır ve maddeler numaralıdır. Rapora "Yanıtla" ile `2 metin` yazılırsa
  metin 2. maddenin ajanına gider (o koşunun oturumunu sürdürür). Numarasız cevap CEO'ya gider.
- **Telegram kapalıyken sorular:** `<soru>` kuralı ve CEO triyajı Telegram'dan bağımsız çalışır. CEO
  "kendim" derse ajan devam eder. "kullaniciya" derse soru `cevap_bekliyor` olarak kalır ve arayüzdeki kartta
  görünür; Telegram açılınca bekleyen sorular kullanıcıya gönderilir. Koşucu Telegram'ın açık olup olmadığını
  bilmez.
- **"Kullanıcıya her zaman" kuralı iki katmanlı:**
  1. Ajan sorusunu sınıflandırır: `<soru tur="maliyet|buyuk-degisiklik|yayin-mail-para|diger">`. `tur`
     `diger` dışında bir değerse ya da etiket eksik/bozuksa soru **CEO'ya hiç sorulmadan** kullanıcıya gider
     (kodla, model kararı olmadan).
  2. Yalnız `diger` sorular CEO triyajına girer. CEO de kurallara göre kullanıcıya yükseltebilir.
- **Bildirime verilen cevap:** ajanın sonuç ya da hata mesajına "Yanıtla" ile yazılan metin, o koşunun
  oturumunu sürdürür ("şunu da düzelt" doğal çalışır). Bu yüzden bot'un her ajan mesajı için
  `telegram_mesaj_id → {ajan, kosu_id, session_id}` saklanır (`durum/telegram-mesajlar.json`, son 500 kayıt).
  CEO'nun cevabına yazılan metin yeniden CEO'ya gider; önceki CEO cevabı prompt'a bağlam olarak eklenir.
- **"Aynı iş zinciri":** aynı `session_id`'nin ardışık sürdürmeleri. Otomatik cevap sayacı `session_id`
  başına tutulur; kullanıcı bir kez cevap verince sayaç sıfırlanır.
- **Rapor kapsamı:** "son rapordan bu yana". Rapor saatinden sonra verilen kararlar bir sonraki rapora girer.
  Kararlar tek bir `durum/kararlar.jsonl`'de durur; son gönderilen raporun zamanı `durum/rapor-son.json`'da
  tutulur.

## İnşa edenin kararına bırakılanlar

- Telegram mesajlarının biçimi (emoji, kalın yazı, kısaltma uzunluğu), raporun düzeni.
- Long polling hata/yeniden deneme aralıkları (ağ yokken sunucu düşmemeli, logu boğmamalı).
- Ofis durumu özetinin CEO prompt'una giren tam biçimi ve uzunluk sınırı.
- `/durum`, `/ajanlar` gibi ek bot komutları (gerekmez; CEO'ya düz soru aynı işi görür).
- Testler: proje stilinde, `assert` tabanlı küçük bir self-check (yönlendirme ayrıştırıcısı, `<soru>`
  ayıklama, `.env` okuma, rapor derleme, kimlik doğrulama reddi).
