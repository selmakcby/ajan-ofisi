// Eğlence odası: saf mantık (three.js'siz; node test_eglence.mjs ile denenir). Model çağrısı yok, 0 token.

export const GECE_BASLA = 20, GECE_BIT = 8;          // 20:00–07:59 gece: boştaki kedi odasının yatağında uyur
export const TUR_MS = 3 * 60 * 1000;                 // gündüz yerler 3 dakikada bir değişir
export const MIYAV = ['Miyaw', 'Miyav!', 'Mrr…', 'Miyaaav ☕', 'Mrrrow?', 'Miyav miyav', 'Mır mır'];

export const geceMi = saat => saat >= GECE_BASLA || saat < GECE_BIT;

// ?saat=23 ile saat elle seçilir (deneme için); geçersizse bilgisayarın saati
export function saatAl(arama, simdi = new Date()) {
  const s = new URLSearchParams(arama).get('saat');
  const n = s !== null && /^\d{1,2}$/.test(s) ? Number(s) : NaN;
  return n >= 0 && n <= 23 ? n : simdi.getHours();
}

function ozet(s) { let h = 2166136261; for (const ch of s) h = Math.imul(h ^ ch.codePointAt(0), 16777619); return h >>> 0; }

// Her kediye ayrı bir yer: sıra ve başlangıç yeri (kimlik, tur) özetinden; doluysa sonraki boş yer.
// Bir kedi ayrılınca/gelince yalnız onunla çakışanlar yer değiştirir; herkes zıplamaz.
export function yerAta(idler, yerSayisi, tur) {
  if (idler.length > yerSayisi) throw new Error(`yer yetmiyor: ${idler.length} kedi, ${yerSayisi} yer`);
  const sirali = [...idler].sort((a, b) => ozet(a + '|' + tur) - ozet(b + '|' + tur) || (a < b ? -1 : 1));
  const dolu = new Set(), sonuc = new Map();
  sirali.forEach(id => {
    let i = ozet(id + '#' + tur) % yerSayisi;
    while (dolu.has(i)) i = (i + 1) % yerSayisi;
    dolu.add(i); sonuc.set(id, i);
  });
  return new Map(idler.map(id => [id, sonuc.get(id)]));   // çağıranın sırasıyla
}

export const balonMetni = r => MIYAV[Math.min(MIYAV.length - 1, Math.floor(r * MIYAV.length))];
export const sonrakiBalon = r => 5 + r * 9;          // sn: bir sonraki "miyav"a kadar
