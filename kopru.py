"""Canlı terminal köprüsü: kendi elle açtığın Claude Code oturumlarını ofis ajanlarına bağlar.

Salt okuma. ~/.claude/sessions/<pid>.json canlı oturumları, ~/.claude/projects/<cwd>/<sessionId>.jsonl
transkripti verir; transkript ofsetle tail edilir. Olay akışına YALNIZ araç adı + kısa hedef
(dosya adı, pattern, açıklama, Bash'in ilk kelimesi) ve "yeni görev aldı" bilgisi yazılır;
mesaj metni, prompt içeriği, dosya içeriği hiçbir zaman yazılmaz.
Eşleme: kopru.json (kopru.example.json'dan kopyala). `gizle` listesindeki parçayı cwd'sinde ya da tmux
oturum adında taşıyan oturum hiçbir eşlemeyle gösterilmez.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import ortak
import token_sayac

EV = os.path.expanduser("~")
OTURUM_DIZINI = os.path.join(EV, ".claude", "sessions")
PROJE_DIZINI = os.path.join(EV, ".claude", "projects")
ESLEME_DOSYASI = os.environ.get("OFIS_KOPRU", os.path.join(ortak.VERI, "kopru.json"))
ARALIK_SN = 2.0
CALISIYOR_SN = 20
MAKS_OKUMA = 2_000_000          # tek turda transkriptten okunacak en fazla bayt
ILK_KUYRUK = 256_000            # ilk görüşte son aracı bulmak için okunan kuyruk
DETAY_MAKS = 80
TMUX_TAZELE_SN = 6
TOKEN_OLAY_SN = 3.0             # ajan başına en fazla 1 token olayı / 3 sn
MASAUSTU_TAZELE_SN = 10         # masaüstü transkript taraması aralığı
MASAUSTU_ACIK_SN = 30 * 60      # transkripti bu kadar süredir yazılmayan masaüstü oturumu kapandı sayılır
MASAUSTU_BAS = 64_000           # entrypoint/cwd için okunan baş kısım
MASAUSTU_GIRIS = "claude-desktop"
KAYITLI_GIRIS = "cli"           # ~/.claude/sessions'a kayıt bırakan tek giriş (terminal, tmux, VS Code terminali)
ALT_KUYRUK = 256_000            # alt-ajanın son aracı için okunan kuyruk
ALT_MAKS = 8                    # oturum başına gösterilen en fazla alt-ajan
MESAJ_TURU = re.compile(r'"type"\s*:\s*"(user|assistant)"')


def gizli_mi(cwd, tmux_oturum, gizle):
    """kopru.json `gizle`: bu parçalardan birini cwd'sinde ya da tmux oturum adında taşıyan oturum asla gösterilmez."""
    c, t = (cwd or "").lower(), (tmux_oturum or "").lower()
    return any(isinstance(p, str) and p.strip() and (p.lower() in c or p.lower() == t) for p in (gizle or []))


def en_yakin(esleme, cwd):
    """cwd'nin kendisine ya da en yakın üst klasörüne yazılmış eşleme değeri (alt klasörde açılan oturum da eşlenir)."""
    yol = os.path.normpath(cwd or "/")
    while True:
        if yol in esleme:
            return esleme[yol]
        ust = os.path.dirname(yol)
        if ust == yol:
            return None
        yol = ust


def proje_klasoru(cwd):
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _temiz(s, n=DETAY_MAKS):
    s = re.sub(r"[\x00-\x1f]+", " ", str(s)).strip()
    return s[:n]


def arac_hedefi(ad, girdi):
    """kosucu.arac_ozeti ile aynı 'anahtar=değer' biçimi, ama yalnız güvenli kısa parça."""
    if not isinstance(girdi, dict):
        return ""
    if ad == "Bash":
        # yalnız ilk anlamlı komutun ilk kelimesi; "cd x &&" önekleri ve FOO=bar atamaları (sır olabilir) atlanır
        for parcacik in re.split(r"&&|\|\||;|\||\n", str(girdi.get("command") or "")):
            kelimeler = [w for w in parcacik.split() if "=" not in w]
            if kelimeler and kelimeler[0] not in ("cd", "export", "set", "source", "."):
                return "command=" + _temiz(os.path.basename(kelimeler[0]), 40)
        return ""
    for anahtar in ("file_path", "notebook_path", "path"):
        if girdi.get(anahtar):
            return "file_path=" + _temiz(os.path.basename(str(girdi[anahtar]).rstrip("/")), 60)
    if girdi.get("pattern"):
        return "pattern=" + _temiz(girdi["pattern"], 60)
    if girdi.get("description"):
        return "description=" + _temiz(girdi["description"], 60)
    if girdi.get("url"):
        return "url=" + _temiz(urlparse(str(girdi["url"])).hostname or "", 60)
    return ""


def yeni_prompt_mu(satir):
    """Kullanıcının yazdığı yeni prompt mu? (araç sonucu, meta, sistem enjeksiyonu değil)"""
    if satir.get("type") != "user" or satir.get("isMeta") or satir.get("isSidechain"):
        return False
    if "toolUseResult" in satir:
        return False
    icerik = (satir.get("message") or {}).get("content")
    if isinstance(icerik, str):
        return bool(icerik.strip()) and not icerik.lstrip().startswith("<")
    if isinstance(icerik, list):
        turler = {p.get("type") for p in icerik if isinstance(p, dict)}
        return "tool_result" not in turler and bool(turler & {"text", "image"})
    return False


def model_bul(ham):
    """Ham JSONL parçasındaki son assistant mesajının model kimliği (ör. claude-opus-5-5)."""
    son = None
    for satir in ham.splitlines():
        if '"model"' not in satir:
            continue
        try:
            d = json.loads(satir)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(d, dict) and d.get("type") == "assistant" and not d.get("isSidechain"):
            m = (d.get("message") or {}).get("model")
            if isinstance(m, str) and re.fullmatch(r"[a-z0-9.-]{3,60}", m) and m != "<synthetic>":
                son = m
    return son


def satirlari_coz(ham, yan_dal=False):
    """Ham JSONL parçasından (araç, hedef) olayları ve yeni-prompt bayrağını çıkarır.
    yan_dal=False: alt-ajan (isSidechain) satırları atlanır; alt-ajanın kendi transkripti için True."""
    araclar, yeni_gorev = [], False
    for satir in ham.splitlines():
        try:
            d = json.loads(satir)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(d, dict) or (d.get("isSidechain") and not yan_dal):
            continue
        if d.get("type") == "assistant":
            for p in (d.get("message") or {}).get("content") or []:
                if isinstance(p, dict) and p.get("type") == "tool_use":
                    ad = _temiz(p.get("name") or "araç", 60)
                    araclar.append((ad, arac_hedefi(ad, p.get("input"))))
        elif yeni_prompt_mu(d):
            yeni_gorev = True
    return araclar, yeni_gorev


def token_satirlari(ham):
    """Ham JSONL parçasından assistant usage'ları: [(yerel_tarih, message_id, usage)]. Metin okunmaz/saklanmaz."""
    sonuc = []
    for satir in ham.splitlines():
        if '"usage"' not in satir or '"assistant"' not in satir:
            continue
        try:
            d = json.loads(satir)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(d, dict) or d.get("type") != "assistant" or d.get("isSidechain"):
            continue
        m = d.get("message") or {}
        tarih = token_sayac.yerel_tarih(d.get("timestamp"))
        if tarih and isinstance(m.get("usage"), dict):
            sonuc.append((tarih, m.get("id"), m["usage"]))
    return sonuc


def token_besle(k, ham, yalniz_tarih=None):
    """Satırların usage'ını oturumun tarih başına tekilleştiricisine verir. Değişen tarihleri döndürür."""
    degisen = set()
    for tarih, mid, usage in token_satirlari(ham):
        if yalniz_tarih and tarih != yalniz_tarih:
            continue
        tekil = k["tekil"].setdefault(tarih, token_sayac.MesajTekil())
        if tekil.isle(mid, usage):
            degisen.add(tarih)
    return degisen


def transkript_basi(yol):
    """Transkriptin başından (entrypoint, cwd). Mesaj metni okunmaz; yalnız bu iki alan aranır."""
    try:
        with open(yol, "rb") as f:
            bas = f.read(MASAUSTU_BAS).decode("utf-8", "replace")
    except OSError:
        return None, None
    giris = re.search(r'"entrypoint"\s*:\s*"([a-z-]{1,40})"', bas)
    cwd = re.search(r'"cwd"\s*:\s*"((?:[^"\\]|\\.){1,1000})"', bas)
    if not giris or not cwd:
        return (giris.group(1) if giris else None), None
    try:
        cwd_deger = json.loads(f'"{cwd.group(1)}"')
    except json.JSONDecodeError:
        return giris.group(1), None
    return giris.group(1), cwd_deger


def son_mesaj_zamani(yol):
    """Transkriptteki son user/assistant satırının zamanı (epoch). Masaüstü uygulaması eski bir sohbeti açınca
    dosyaya yalnız meta satırı ekler; dosya mtime'ı yerine bu kullanılır. Metin okunmaz, yalnız type + timestamp."""
    try:
        with open(yol, "rb") as f:
            f.seek(max(0, os.path.getsize(yol) - ILK_KUYRUK))
            kuyruk = f.read().decode("utf-8", "replace")
    except OSError:
        return 0.0
    for satir in reversed(kuyruk.splitlines()):
        if '"timestamp"' not in satir or not MESAJ_TURU.search(satir):
            continue
        try:
            d = json.loads(satir)
            return datetime.fromisoformat(str(d["timestamp"]).replace("Z", "+00:00")).timestamp()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return 0.0


def gecmisi_tara(k, boyut):
    """Açılışta bir kez: transkripti baştan sona akıtarak YALNIZ bugünün usage'ını sayar (olay basmaz)."""
    bugun = ortak.bugun()
    with open(k["yol"], "rb") as f:
        okunan = 0
        for satir in f:
            okunan += len(satir)
            if okunan > boyut:
                break
            if b'"usage"' in satir:
                token_besle(k, satir.decode("utf-8", "replace"), yalniz_tarih=bugun)
    if bugun in k["tekil"]:
        k["token_bekleyen"].add(bugun)


def alt_ajan_ozeti(jsonl, meta_yol):
    """Alt-ajanın meta.json'undaki tür/görev başlığı/model + transkript kuyruğundan son araç. Mesaj metni okunmaz."""
    try:
        with open(meta_yol, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    son_arac = son_hedef = None
    try:
        boyut = os.path.getsize(jsonl)
        with open(jsonl, "rb") as f:
            f.seek(max(0, boyut - ALT_KUYRUK))
            parca = f.read().decode("utf-8", "replace")
        araclar, _ = satirlari_coz(parca.split("\n", 1)[-1] if boyut > ALT_KUYRUK else parca, yan_dal=True)
        if araclar:
            son_arac, son_hedef = araclar[-1]
    except OSError:
        parca = ""
    return {"tur": _temiz(meta.get("agentType") or "alt-ajan", 40), "gorev": _temiz(meta.get("description") or "", 80),
            "model": _temiz(meta.get("model") or model_bul(parca) or "", 40),
            "son_arac": son_arac, "son_hedef": son_hedef}


class Kopru:
    def __init__(self):
        self.kilit = threading.Lock()
        self.oturumlar = {}          # pid -> durum sözlüğü
        self.pencereler = {}         # "oturum:@id" -> pencere adı
        self.tmux_zaman = 0.0
        self.esleme = {}
        self.esleme_mtime = None
        self.ajanlar = {}
        self.token_zaman = {}        # ajan -> son token olayı zamanı
        self.masaustu = {}           # "masaustu:<sid>" -> sahte oturum kaydı (cwd, sessionId, name)
        self.masaustu_zaman = 0.0
        self.bas_onbellek = {}       # transkript yolu -> (entrypoint, cwd)
        self.zaman_onbellek = {}     # transkript yolu -> (mtime, son mesaj zamanı)
        self.uyarilan = set()        # eşlenmedi uyarısı verilmiş sessionId'ler
        self.alt_onbellek = {}       # alt-ajan transkripti -> (mtime, özet)

    # ---------- yapılandırma ----------
    def esleme_yukle(self):
        try:
            m = os.path.getmtime(ESLEME_DOSYASI)
        except OSError:
            self.esleme = {}
            return
        if m == self.esleme_mtime:
            return
        try:
            with open(ESLEME_DOSYASI, encoding="utf-8") as f:
                veri = json.load(f)
            self.esleme = veri if isinstance(veri, dict) else {}
        except (OSError, json.JSONDecodeError):
            self.esleme = {}
        self.esleme_mtime = m

    def tmux_tazele(self):
        if time.time() - self.tmux_zaman < TMUX_TAZELE_SN:
            return
        self.tmux_zaman = time.time()
        tmux = shutil.which("tmux") or "/opt/homebrew/bin/tmux"
        try:
            cikti = subprocess.run([tmux, "list-windows", "-a", "-F", "#{session_name}:#{window_id} #{window_name}"],
                                   capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return
        yeni = {}
        for satir in cikti.splitlines():
            anahtar, _, ad = satir.partition(" ")
            yeni[anahtar] = ad
        self.pencereler = yeni

    def ajan_bul(self, cwd, tmux_oturum, pencere_adi, etkilesimli=True):
        """(ajan, gizli): eşleme sırası tmux pencere adı > cwd (en yakın üst klasör dahil) > `varsayilan`
        (yazılmamışsa ilk ajan; "" yazılırsa eşleşmeyen oturum gizlenir). `claude -p` gibi etkileşimsiz
        koşular (ofisin kendi koşuları dahil) varsayılana düşmez, yalnız açık eşlemeyle görünür."""
        e = self.esleme
        if gizli_mi(cwd, tmux_oturum, e.get("gizle")):
            return None, True
        if cwd in {os.path.expanduser(x) for x in (e.get("atla_cwd") or [])}:
            return None, True
        cwd_esleme = {os.path.normpath(os.path.expanduser(k)): v for k, v in (e.get("cwd") or {}).items()}
        pencere_esleme = {os.path.normpath(os.path.expanduser(k)): v for k, v in (e.get("pencere") or {}).items()}
        pencereler = en_yakin(pencere_esleme, cwd)
        adaylar = ((pencereler or {}).get(pencere_adi or "") if isinstance(pencereler, dict) else None,
                   en_yakin(cwd_esleme, cwd), e.get("varsayilan", self.ilk_ajan()) if etkilesimli else None)
        for ajan in adaylar:
            if isinstance(ajan, str) and ajan != "ceo" and ajan in self.ajanlar:
                return ajan, False
        return None, False

    def ilk_ajan(self):
        """`varsayilan` yazılmamışsa eşleşmeyen oturum ilk ajanda görünür: hiçbir oturum sessizce kaybolmaz."""
        return next((a for a in self.ajanlar if a != "ceo"), None)

    def eslenmedi_uyar(self, sid, cwd, pencere_adi):
        """Eşlenemeyen oturum için sunucu günlüğüne oturum başına bir kez ipucu (yalnız klasör ve pencere adı)."""
        if sid in self.uyarilan:
            return
        self.uyarilan.add(sid)
        dosya = os.path.basename(ESLEME_DOSYASI)
        sys.stderr.write(f"köprü: oturum hiçbir ajana eşlenmedi (cwd={cwd}, tmux penceresi={pencere_adi or '-'}). "
                         f"{dosya} içine \"cwd\": {{\"{cwd}\": \"<ajan-id>\"}} ya da \"varsayilan\": \"<ajan-id>\" ekle.\n")
        sys.stderr.flush()

    # ---------- tarama ----------
    def canli_oturumlar(self):
        try:
            adlar = os.listdir(OTURUM_DIZINI)
        except OSError:
            return {}
        sonuc = {}
        for ad in adlar:
            if not re.fullmatch(r"\d+\.json", ad):
                continue
            pid = int(ad[:-5])
            if not ortak.surec_yasiyor(pid):
                continue
            try:
                with open(os.path.join(OTURUM_DIZINI, ad), encoding="utf-8") as f:
                    d = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(d, dict) and d.get("sessionId") and d.get("cwd"):
                sonuc[pid] = d
        sonuc.update(self.masaustu_oturumlari())
        return sonuc

    def masaustu_oturumlari(self):
        """Terminal dışı oturumlar (Claude masaüstü uygulaması, IDE eklentileri) ~/.claude/sessions'a kayıt bırakmaz;
        yalnız transkript yazar. Son MASAUSTU_ACIK_SN içinde mesaj yazılmış, entrypoint'i `cli` ya da `sdk-*`
        olmayan transkriptler açık oturum sayılır. tmux penceresi olmadığından `cwd` / `varsayilan` ile bağlanır."""
        if time.time() - self.masaustu_zaman < MASAUSTU_TAZELE_SN:
            return self.masaustu
        self.masaustu_zaman = time.time()
        sinir, yeni, gorulen = time.time() - MASAUSTU_ACIK_SN, {}, {}
        try:
            klasorler = list(os.scandir(PROJE_DIZINI))
        except OSError:
            return {}
        for klasor in klasorler:
            if not klasor.is_dir(follow_symlinks=False):     # klasör mtime'ı dosya yazılınca değişmez, filtrelenmez
                continue
            try:
                dosyalar = list(os.scandir(klasor.path))
            except OSError:
                continue
            for dosya in dosyalar:
                if not dosya.name.endswith(".jsonl") or dosya.stat().st_mtime < sinir:
                    continue
                sid = dosya.name[:-6]
                if not re.fullmatch(r"[A-Za-z0-9-]+", sid):
                    continue
                giris, cwd = self.bas_onbellek.get(dosya.path) or transkript_basi(dosya.path)
                if giris and cwd:            # eksik baş (yeni açılmış dosya) önbelleğe girmez, sonraki turda yeniden okunur
                    gorulen[dosya.path] = (giris, cwd)
                if not giris or giris == KAYITLI_GIRIS or giris.startswith("sdk") or not cwd \
                        or proje_klasoru(cwd) != klasor.name:
                    continue
                if self.mesaj_zamani(dosya) < sinir:      # yalnız meta satırı eklenmiş eski sohbet
                    continue
                kaynak = "masaüstü" if giris == MASAUSTU_GIRIS else giris.replace("claude-", "")
                yeni[f"masaustu:{sid}"] = {"sessionId": sid, "cwd": cwd, "entrypoint": giris,
                                           "name": f"{kaynak} · {os.path.basename(cwd) or cwd}"}
        self.bas_onbellek = gorulen
        self.zaman_onbellek = {y: v for y, v in self.zaman_onbellek.items() if y in gorulen}
        self.masaustu = yeni
        return yeni

    def mesaj_zamani(self, dosya):
        """son_mesaj_zamani, dosya mtime'ı değişmedikçe önbellekten."""
        mtime = dosya.stat().st_mtime
        onceki = self.zaman_onbellek.get(dosya.path)
        if not onceki or onceki[0] != mtime:
            onceki = (mtime, son_mesaj_zamani(dosya.path))
            self.zaman_onbellek[dosya.path] = onceki
        return onceki[1]

    def kayit_kur(self, pid, d, ajan, tmux_oturum, pencere_adi):
        cwd, sid = d["cwd"], str(d["sessionId"])
        yol = os.path.join(PROJE_DIZINI, proje_klasoru(cwd), f"{sid}.jsonl") \
            if re.fullmatch(r"[A-Za-z0-9-]+", sid) else None
        k = {"pid": pid, "sid": sid, "yol": yol, "ofset": 0, "son_satir_ts": 0.0,
             "ajan": ajan, "oda": self.ajanlar[ajan]["oda"], "oturum_adi": _temiz(d.get("name") or f"pid-{pid}", 60),
             "pencere_adi": _temiz(pencere_adi or "", 60), "tmux_oturum": tmux_oturum,
             "son_arac": None, "son_hedef": None, "model": None, "durum": None, "yayinlanan": None,
             "tekil": {}, "token_bekleyen": set()}
        if yol and os.path.exists(yol):
            boyut = os.path.getsize(yol)
            gecmisi_tara(k, boyut)
            k["ofset"] = boyut
            k["son_satir_ts"] = os.path.getmtime(yol)
            with open(yol, "rb") as f:          # yalnız son aracı öğrenmek için; olay yazılmaz
                f.seek(max(0, boyut - ILK_KUYRUK))
                parca = f.read().decode("utf-8", "replace")
            araclar, _ = satirlari_coz(parca.split("\n", 1)[-1] if boyut > ILK_KUYRUK else parca)
            k["model"] = model_bul(parca) or k["model"]
            if araclar:
                k["son_arac"], k["son_hedef"] = araclar[-1]
        k["token_ilk_yazildi"] = not k["token_bekleyen"]   # bugün geçmişi yoksa ilk canlı artış olay basar
        return k

    def oku(self, k):
        """Transkriptin yeni satırlarını okur; ofseti yalnız tam satır sonuna ilerletir."""
        if not k["yol"]:
            return [], False
        try:
            boyut = os.path.getsize(k["yol"])
        except OSError:
            return [], False
        if boyut < k["ofset"]:                  # dosya kısaldı (beklenmez): baştan değil sondan devam
            k["ofset"] = boyut
        if boyut == k["ofset"]:
            return [], False
        with open(k["yol"], "rb") as f:
            f.seek(k["ofset"])
            parca = f.read(min(boyut - k["ofset"], MAKS_OKUMA))
        son = parca.rfind(b"\n")
        if son < 0:
            return [], False
        k["ofset"] += son + 1
        k["son_satir_ts"] = time.time()
        metin = parca[:son].decode("utf-8", "replace")
        k["token_bekleyen"] |= token_besle(k, metin)
        k["model"] = model_bul(metin) or k["model"]
        return satirlari_coz(metin)

    @staticmethod
    def durum_hesapla(k, d):
        if time.time() - k["son_satir_ts"] < CALISIYOR_SN or d.get("status") == "busy":
            return "calisiyor"
        return "bekliyor"

    def disari(self, k):
        return {"ajan": k["ajan"], "oda": k["oda"], "oturum_adi": k["oturum_adi"],
                "pencere_adi": k["pencere_adi"], "durum": k["durum"], "son_arac": k["son_arac"],
                "son_hedef": k["son_hedef"], "model": k.get("model"),
                "zaman": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(k["son_satir_ts"] or time.time()))}

    def tur(self):
        self.esleme_yukle()
        _, self.ajanlar = ortak.ajanlari_yukle()
        self.tmux_tazele()
        canli = self.canli_oturumlar()
        olaylar = []
        with self.kilit:
            for pid in list(self.oturumlar):
                if pid not in canli or str(canli[pid]["sessionId"]) != self.oturumlar[pid]["sid"]:
                    k = self.oturumlar.pop(pid)
                    if k["yayinlanan"]:
                        olaylar.append({"tur": "terminal_durum", **self.disari({**k, "durum": "kapandi"})})
            for pid, d in canli.items():
                tmux = str(d.get("tmux") or "")
                tmux_oturum = tmux.split(":", 1)[0] if tmux else ""
                pencere_adi = self.pencereler.get(tmux.split(".", 1)[0], "") if tmux else ""
                etkilesimli = not str(d.get("entrypoint") or "").startswith("sdk")
                ajan, gizli = self.ajan_bul(d["cwd"], tmux_oturum, pencere_adi, etkilesimli)
                k = self.oturumlar.get(pid)
                if not ajan and not gizli and etkilesimli:
                    self.eslenmedi_uyar(str(d["sessionId"]), d["cwd"], pencere_adi)
                if not ajan:
                    if k:
                        self.oturumlar.pop(pid)
                        if k["yayinlanan"]:
                            olaylar.append({"tur": "terminal_durum", **self.disari({**k, "durum": "kapandi"})})
                    continue
                if not k or k["ajan"] != ajan:
                    k = self.kayit_kur(pid, d, ajan, tmux_oturum, pencere_adi)
                    self.oturumlar[pid] = k
                else:
                    k["pencere_adi"] = _temiz(pencere_adi, 60)
                    araclar, yeni_gorev = self.oku(k)
                    if yeni_gorev:
                        olaylar.append({"tur": "terminal_arac", "ajan": ajan, "oda": k["oda"],
                                        "oturum_adi": k["oturum_adi"], "arac": "YeniGorev", "detay": ""})
                    if araclar:
                        k["son_arac"], k["son_hedef"] = araclar[-1]
                        # tur başına oturum başına tek araç olayı: akış taşmaz
                        olaylar.append({"tur": "terminal_arac", "ajan": ajan, "oda": k["oda"],
                                        "oturum_adi": k["oturum_adi"], "arac": k["son_arac"],
                                        "detay": k["son_hedef"] or ""})
                k["durum"] = self.durum_hesapla(k, d)
                if k["yayinlanan"] != k["durum"]:
                    k["yayinlanan"] = k["durum"]
                    olaylar.append({"tur": "terminal_durum", **self.disari(k)})
            olaylar += self.token_yaz()
        for o in olaylar:
            ortak.olay_yaz(o)

    def token_yaz(self):
        """Bekleyen oturum toplamlarını dosyaya koyar; ajan başına en fazla 1 olay / TOKEN_OLAY_SN.
        İlk taramadan gelenler sayılır ama olay basılmaz."""
        simdi, olaylar = time.time(), []
        for k in self.oturumlar.values():
            if not k["token_bekleyen"] or simdi - self.token_zaman.get(k["ajan"], 0) < TOKEN_OLAY_SN:
                continue
            ilk = not k["token_ilk_yazildi"]
            ajan_gun = None
            for tarih in sorted(k["token_bekleyen"]):
                g = token_sayac.kayit_koy(tarih, "_oturumlar", k["sid"], k["ajan"], k["tekil"][tarih].toplam)
                if tarih == ortak.bugun():
                    ajan_gun = g
            k["token_bekleyen"] = set()
            k["token_ilk_yazildi"] = True
            if ilk or ajan_gun is None:
                continue
            self.token_zaman[k["ajan"]] = simdi
            olaylar.append({"tur": "token", "ajan": k["ajan"], "oda": k["oda"], "kaynak": "terminal",
                            "oturum_adi": k["oturum_adi"], "ajan_gun": ajan_gun})
        return olaylar

    def alt_ajanlar(self, k):
        """Oturumun son MASAUSTU_ACIK_SN içinde yazılmış alt-ajanları (<sid>/subagents/agent-*.jsonl), yeniden eskiye."""
        if not k["yol"]:
            return []
        klasor = os.path.join(k["yol"][:-6], "subagents")
        try:
            girdiler = [g for g in os.scandir(klasor) if g.name.startswith("agent-") and g.name.endswith(".jsonl")]
        except OSError:
            return []
        simdi, sonuc = time.time(), []
        for g in girdiler:
            try:
                mtime = g.stat().st_mtime
            except OSError:
                continue
            if simdi - mtime > MASAUSTU_ACIK_SN:
                continue
            onceki = self.alt_onbellek.get(g.path)
            ozet = onceki[1] if onceki and onceki[0] == mtime else alt_ajan_ozeti(g.path, g.path[:-6] + ".meta.json")
            self.alt_onbellek[g.path] = (mtime, ozet)
            sonuc.append({**ozet, "durum": "calisiyor" if simdi - mtime < CALISIYOR_SN else "bitti",
                          "zaman": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime))})
        return sorted(sonuc, key=lambda x: x["zaman"], reverse=True)[:ALT_MAKS]

    def liste(self):
        with self.kilit:
            kayitlar = list(self.oturumlar.values())
        sonuc = [{**self.disari(k), "alt_ajanlar": self.alt_ajanlar(k)} for k in kayitlar]
        sinir = time.time() - MASAUSTU_ACIK_SN       # kapanmış alt-ajanlar önbellekte birikmez
        self.alt_onbellek = {y: v for y, v in self.alt_onbellek.items() if v[0] >= sinir}
        return sorted(sonuc, key=lambda x: (x["ajan"], x["oturum_adi"]))

    def dongu(self):
        while True:
            try:
                self.tur()
            except Exception as e:  # köprü hatası sunucuyu düşürmez
                ortak.olay_yaz({"tur": "hata", "ajan": "ceo", "detay": f"terminal köprüsü: {type(e).__name__}"})
                time.sleep(30)
            time.sleep(ARALIK_SN)

    def baslat(self):
        threading.Thread(target=self.dongu, name="terminal-kopru", daemon=True).start()
