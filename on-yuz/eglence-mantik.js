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

// ---------- yataklar: her kediye ayrı yatak; oda dar gelirse arka arkaya sıralar ----------
export const YATAK_ARA = 1.2, YATAK_SIRA = 1.15;
export function yatakDizilimi(n, odaW) {
  const sirada = Math.max(1, Math.floor((odaW - 6.8 + .2) / YATAK_ARA)); // yan duvardaki eşyalara değmesin
  const siralar = Math.ceil(n / sirada), sonuc = [];
  for (let s = 0, kalan = n; s < siralar; s++) {
    const m = Math.ceil(kalan / (siralar - s)); kalan -= m;
    for (let j = 0; j < m; j++) sonuc.push({ dx:(j - (m - 1) / 2) * YATAK_ARA, dz:s ? -s * YATAK_SIRA : 0 });
  }
  return sonuc;
}

// ---------- bilardo: masa merkezine göre (x,z); sürtünme, bant, eşit kütleli çarpışma ----------
const SURTUNME = .9, DUR = .02, BANT = .9, CARPMA = .95;
export function bilardoAdim(toplar, dt, { w, d, r }) {
  const t = toplar.map(b => ({ ...b }));
  const hiz = Math.max(0, ...t.map(b => Math.hypot(b.vx, b.vz)));
  const n = Math.max(1, Math.ceil(hiz * dt / (r * .5)));   // hızlı topta küçük adımlar: içinden geçmesin
  const h = dt / n, xs = w / 2 - r, zs = d / 2 - r;
  for (let k = 0; k < n; k++) {
    t.forEach(b => {
      b.x += b.vx * h; b.z += b.vz * h;
      if (b.x > xs) { b.x = 2 * xs - b.x; b.vx = -Math.abs(b.vx) * BANT; }
      if (b.x < -xs) { b.x = -2 * xs - b.x; b.vx = Math.abs(b.vx) * BANT; }
      if (b.z > zs) { b.z = 2 * zs - b.z; b.vz = -Math.abs(b.vz) * BANT; }
      if (b.z < -zs) { b.z = -2 * zs - b.z; b.vz = Math.abs(b.vz) * BANT; }
    });
    for (let i = 0; i < t.length; i++) for (let j = i + 1; j < t.length; j++) {
      const a = t[i], b = t[j], dx = b.x - a.x, dz = b.z - a.z, m = Math.hypot(dx, dz);
      if (m >= 2 * r || m === 0) continue;
      const nx = dx / m, nz = dz / m, ort = (2 * r - m) / 2;
      a.x -= nx * ort; a.z -= nz * ort; b.x += nx * ort; b.z += nz * ort;
      const yak = (a.vx - b.vx) * nx + (a.vz - b.vz) * nz;
      if (yak > 0) { const p = yak * (1 + CARPMA) / 2; a.vx -= p * nx; a.vz -= p * nz; b.vx += p * nx; b.vz += p * nz; }
    }
  }
  const s = Math.exp(-dt * SURTUNME);
  t.forEach(b => { b.vx *= s; b.vz *= s; if (Math.hypot(b.vx, b.vz) < DUR) { b.vx = 0; b.vz = 0; } });
  return t;
}
export const bilardoDurdu = toplar => toplar.every(b => !b.vx && !b.vz);

// ---------- TV'deki dövüş oyunu: rastgele raunt, can barları, K.O. ----------
const AKSIYON = ['bekle', 'yumruk', 'tekme', 'zipla', 'blok', 'yumruk'];
export function dovusYeni(r = Math.random, raunt = 1) {
  return { raunt, can:[100, 100], ko:false, koT:0, kazanan:-1, sahne:Math.floor(r() * 4), renk:[Math.floor(r() * 6), Math.floor(r() * 6)],
    aksiyon:['bekle', 'bekle'], aksiyonT:.4, x:[.32, .68], vurus:-1 };
}
export function dovusAdim(d, dt, r = Math.random) {
  if (d.ko) {
    const koT = d.koT + dt;
    return koT > 1.6 ? dovusYeni(r, d.raunt + 1) : { ...d, koT };
  }
  let { aksiyonT } = d; aksiyonT -= dt;
  if (aksiyonT > 0) return { ...d, aksiyonT, vurus:-1 };
  const aksiyon = [0, 1].map(() => AKSIYON[Math.floor(r() * AKSIYON.length)]);
  const can = [...d.can]; let vurus = -1;
  [0, 1].forEach(i => {
    const a = aksiyon[i], o = 1 - i;
    if ((a === 'yumruk' || a === 'tekme') && aksiyon[o] !== 'blok' && r() < .7) {
      can[o] = Math.max(0, can[o] - (a === 'tekme' ? 12 : 8) - Math.floor(r() * 8)); vurus = o;
    }
  });
  const x = [Math.min(.45, d.x[0] + (r() - .4) * .05), Math.max(.55, d.x[1] - (r() - .4) * .05)];
  const kaybeden = can.findIndex(c => c <= 0);
  return { ...d, aksiyon, aksiyonT:.35 + r() * .3, can, x, vurus, ko:kaybeden >= 0, kazanan:kaybeden >= 0 ? 1 - kaybeden : -1 };
}
