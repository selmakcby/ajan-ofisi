// Ajan Ofisi · prosedürel 3D kedi (harici model/doku yok)
// createCat({ desen, ton, yavru, aksesuar }) → { group, setDurum, update, setMeme, setKontur, dugum }
// Koordinat: kök = sandalye oturağının üstü, kedi +z'ye bakar (robotla aynı çerçeve).
import * as THREE from 'three';

export const DESENLER = {
  'tekir':     { govde:'#c98a4b', cizgi:'#6a4326', gobek:'#f2dfc4', agiz:'#f5e7d2', yanak:'#d9a571', pati:'#f0dcc2', kulak:'#b97a40', kuyruk:'#c98a4b', goz:'#9cc24a', biyik:'#fffaf0', burun:'#d98583', ic:'#f0a8a6', cizgili:1 },
  'tekir-gri': { govde:'#9b9893', cizgi:'#4a4744', gobek:'#ebe7df', agiz:'#f0ece5', yanak:'#b5b2ad', pati:'#e6e2da', kulak:'#8a8783', kuyruk:'#9b9893', goz:'#d9b23e', biyik:'#fffaf0', burun:'#c98a8c', ic:'#eaa6a8', cizgili:1 },
  'sarman':    { govde:'#e49a50', cizgi:'#bf6c2c', gobek:'#f7dfbb', agiz:'#f9e9d2', yanak:'#efb072', pati:'#f6d9b0', kulak:'#d98a42', kuyruk:'#e49a50', goz:'#a8c84a', biyik:'#fffaf0', burun:'#e08c86', ic:'#f2aaa4', cizgili:.55 },
  'siyah':     { govde:'#2b2828', gobek:'#322e2e', agiz:'#3a3434', yanak:'#302c2c', pati:'#2b2828', kulak:'#2b2828', kuyruk:'#2b2828', goz:'#dcc43a', biyik:'#f4f1ea', burun:'#b9767c', ic:'#8a5e62' },
  'smokin':    { govde:'#272424', gobek:'#f8f5ef', agiz:'#f8f5ef', yanak:'#f8f5ef', pati:'#f8f5ef', kulak:'#272424', kuyruk:'#272424', goz:'#b9cd3e', biyik:'#fffdf8', burun:'#e8999f', ic:'#e3a2a6', maske:1 },
  'gri-beyaz': { govde:'#8d9196', gobek:'#f7f5f1', agiz:'#f7f5f1', yanak:'#f7f5f1', pati:'#f7f5f1', kulak:'#8d9196', kuyruk:'#8d9196', goz:'#e3b548', biyik:'#fffdf8', burun:'#eaa0a6', ic:'#eeaab0', maske:1 },
  'siyam':     { govde:'#efe3cd', uc:'#57402f', gobek:'#f6eedf', agiz:'#5f4635', yanak:'#a88a6e', pati:'#57402f', kulak:'#57402f', kuyruk:'#57402f', goz:'#5aa2e6', biyik:'#fffaf0', burun:'#5a3f36', ic:'#b08478', siyam:1 },
};

/* ---------- paylaşılan geometriler ---------- */
const GEO = (() => {
  const kure = new THREE.SphereGeometry(1, 30, 22);
  const bacak = new THREE.CapsuleGeometry(.055, .34, 6, 14); bacak.translate(0, -.22, 0);
  const kuyruk = new THREE.CapsuleGeometry(.046, .1, 5, 12); kuyruk.translate(0, .06, 0);
  const kulak = new THREE.ConeGeometry(.1, .2, 18); kulak.translate(0, .1, 0);
  const kulakIc = new THREE.ConeGeometry(.064, .14, 14); kulakIc.translate(0, .07, 0);
  const yay = new THREE.TorusGeometry(.05, .011, 6, 16, Math.PI);
  const biyik = new THREE.BufferGeometry();
  const nok = [];
  [-1, 1].forEach(s => [[-.03, .04], [-.075, .0], [-.12, -.04]].forEach(([dy, dz]) => {
    nok.push(s * .085, -.08, .25, s * .34, -.08 + dy, .19 + dz);
  }));
  biyik.setAttribute('position', new THREE.Float32BufferAttribute(nok, 3));
  const papyon = new THREE.ConeGeometry(.06, .11, 4); papyon.rotateZ(Math.PI / 2); papyon.translate(-.055, 0, 0);
  const tasma = new THREE.TorusGeometry(.15, .022, 8, 28);
  const kalkanSekil = new THREE.Shape();
  kalkanSekil.moveTo(0, .09); kalkanSekil.lineTo(.075, .065); kalkanSekil.lineTo(.065, -.03); kalkanSekil.lineTo(0, -.09); kalkanSekil.lineTo(-.065, -.03); kalkanSekil.lineTo(-.075, .065); kalkanSekil.closePath();
  const kalkan = new THREE.ExtrudeGeometry(kalkanSekil, { depth:.02, bevelEnabled:true, bevelSize:.006, bevelThickness:.006, bevelSegments:2 });
  return { kure, bacak, kuyruk, kulak, kulakIc, yay, biyik, papyon, tasma, kalkan };
})();

/* ---------- dokular (desen başına bir kez) ---------- */
function tuval(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return { c, x:c.getContext('2d') }; }
function dokuYap(c) { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; }
function kurkGurultu(x, w, h, renk, adet = 2600) {
  x.globalAlpha = .07; x.fillStyle = renk;
  for (let i = 0; i < adet; i++) { const px = Math.random() * w, py = Math.random() * h; x.fillRect(px, py, 1 + Math.random() * 2, 3 + Math.random() * 5); }
  x.globalAlpha = 1;
}
// SphereGeometry UV: u=.25 ön (+z), u=.75 sırt; tuval üstü = kürenin tepesi
function govdeDokusu(d) {
  const W = 512, H = 256, { c, x } = tuval(W, H);
  x.fillStyle = d.govde; x.fillRect(0, 0, W, H);
  if (d.siyam) {
    const g = x.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, 'rgba(120,90,60,.10)'); g.addColorStop(.25, 'rgba(255,255,255,0)'); g.addColorStop(.75, 'rgba(110,80,55,.22)'); g.addColorStop(1, 'rgba(120,90,60,.10)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  if (d.cizgili) {
    x.strokeStyle = d.cizgi; x.lineCap = 'round'; x.globalAlpha = d.cizgili;
    for (let i = 0; i < 9; i++) {
      const y0 = 30 + i * 24; x.lineWidth = 7 + (i % 3) * 2;
      x.beginPath();
      for (let u = .42; u <= 1.08; u += .01) { const px = u * W, py = y0 + Math.sin(u * 22 + i) * 6; u === .42 ? x.moveTo(px, py) : x.lineTo(px, py); }
      x.stroke();
      x.beginPath();
      for (let u = -.08; u <= .1; u += .01) { const px = u * W + (u < 0 ? W : 0), py = y0 + Math.sin(u * 22 + i) * 6; x.lineTo(px, py); }
      x.stroke();
    }
    x.globalAlpha = 1;
  }
  if (d.gobek && !d.maske) { // ön karın açık ton
    const g = x.createRadialGradient(.25 * W, .62 * H, 10, .25 * W, .62 * H, 110);
    g.addColorStop(0, d.gobek); g.addColorStop(.6, d.gobek); g.addColorStop(1, 'rgba(0,0,0,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  kurkGurultu(x, W, H, d.siyam || d.maske || !d.cizgi ? '#ffffff' : d.cizgi);
  return dokuYap(c);
}
function basDokusu(d) {
  const W = 512, H = 256, { c, x } = tuval(W, H);
  x.fillStyle = d.govde; x.fillRect(0, 0, W, H);
  const cx = .25 * W;
  if (d.siyam) {
    const g = x.createRadialGradient(cx, .62 * H, 8, cx, .6 * H, 95);
    g.addColorStop(0, d.uc); g.addColorStop(.55, d.uc); g.addColorStop(1, 'rgba(87,64,47,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  }
  if (d.maske) { // ön yüzde beyaz ters V (smokin / gri-beyaz)
    x.fillStyle = d.agiz; x.beginPath();
    x.moveTo(cx, .38 * H); x.quadraticCurveTo(cx + 22, .55 * H, cx + 62, H); x.lineTo(cx - 62, H); x.quadraticCurveTo(cx - 22, .55 * H, cx, .38 * H); x.fill();
  }
  if (d.cizgili) { // alında M çizgileri + yanak çizgileri
    x.strokeStyle = d.cizgi; x.lineCap = 'round'; x.lineWidth = 6; x.globalAlpha = Math.min(1, d.cizgili + .2);
    [[-20, 24], [-7, 30], [7, 30], [20, 24]].forEach(([dx, uz]) => { x.beginPath(); x.moveTo(cx + dx, .14 * H); x.lineTo(cx + dx * 1.15, .14 * H + uz); x.stroke(); });
    [-1, 1].forEach(s => [0, 1].forEach(k => { x.beginPath(); x.moveTo(cx + s * (70 + k * 6), (.5 + k * .07) * H); x.lineTo(cx + s * (110 + k * 10), (.47 + k * .07) * H); x.stroke(); }));
    for (let i = 0; i < 6; i++) { x.beginPath(); x.moveTo(.45 * W + i * 40, 0); x.lineTo(.45 * W + i * 40 + 8, .4 * H); x.stroke(); }
    x.globalAlpha = 1;
  }
  kurkGurultu(x, W, H, '#ffffff', 1200);
  return dokuYap(c);
}
function halkaDokusu(d) {
  const { c, x } = tuval(64, 128);
  x.fillStyle = d.kuyruk; x.fillRect(0, 0, 64, 128);
  if (d.cizgili) { x.fillStyle = d.cizgi; x.globalAlpha = d.cizgili; [26, 80].forEach(y => x.fillRect(0, y, 64, 16)); x.globalAlpha = 1; }
  return dokuYap(c);
}

/* ---------- malzeme önbelleği ---------- */
const MAT = new Map();
function kurk(anahtar, ayar, saydam) {
  const k = anahtar + (saydam ? '|s' : '');
  if (!MAT.has(k)) {
    const m = new THREE.MeshPhysicalMaterial({ roughness:.9, metalness:0, sheen:.6, sheenRoughness:.55, sheenColor:new THREE.Color('#fff4e6'), ...ayar });
    if (saydam) { m.transparent = true; m.opacity = .58; }
    MAT.set(k, m);
  }
  return MAT.get(k);
}
const DOKU = new Map();
function doku(desen, tur, yap) { const k = desen + tur; if (!DOKU.has(k)) DOKU.set(k, yap()); return DOKU.get(k); }
function desenMalzemeleri(desen, ton, saydam) {
  const d = DESENLER[desen] || DESENLER.tekir;
  const tk = Math.round(ton * 4) / 4; // ton farkını 9 kademeye yuvarla, malzeme paylaşılsın
  const ac = new THREE.Color(1, 1, 1).multiplyScalar(1 + tk * .08);
  const renkli = (r) => new THREE.Color(r).offsetHSL(0, 0, tk * .035);
  const k = desen + '|' + tk;
  const m = {
    govde: kurk(k + 'g', { map:doku(desen, 'g', () => govdeDokusu(d)), color:ac }, saydam),
    bas: kurk(k + 'b', { map:doku(desen, 'b', () => basDokusu(d)), color:ac }, saydam),
    halka: kurk(k + 'h', { map:doku(desen, 'h', () => halkaDokusu(d)), color:ac }, saydam),
    gobek: kurk(k + 'o', { color:renkli(d.gobek) }, saydam),
    agiz: kurk(k + 'a', { color:renkli(d.agiz) }, saydam),
    yanak: kurk(k + 'y', { color:renkli(d.yanak) }, saydam),
    pati: kurk(k + 'p', { color:renkli(d.pati) }, saydam),
    kulak: kurk(k + 'k', { color:renkli(d.kulak) }, saydam),
    ic: kurk(desen + 'ic', { color:d.ic, roughness:.7, sheen:0 }, saydam),
    burun: kurk(desen + 'n', { color:d.burun, roughness:.45, sheen:0 }, saydam),
    goz: kurk(desen + 'gz', { color:d.goz, roughness:.15, sheen:0, clearcoat:1, emissive:d.goz, emissiveIntensity:.12 }, saydam),
    biyik: new THREE.LineBasicMaterial({ color:d.biyik, transparent:true, opacity:.85 }),
    bacak: d.siyam ? kurk(k + 'su', { color:renkli(d.uc) }, saydam) : kurk(k + 'h', {}, saydam),
  };
  return { d, m };
}
const ORTAK = {
  bebek: new THREE.MeshPhysicalMaterial({ color:'#0d0b0b', roughness:.1, clearcoat:1 }),
  parilti: new THREE.MeshBasicMaterial({ color:'#ffffff' }),
  cizgi: new THREE.MeshBasicMaterial({ color:'#2a2220' }),
  acikCizgi: new THREE.MeshBasicMaterial({ color:'#b9aea4' }),
  agizIc: new THREE.MeshStandardMaterial({ color:'#5a2228', roughness:.6 }),
  kirmizi: new THREE.MeshStandardMaterial({ color:'#d8433a', roughness:.55 }),
  altin: new THREE.MeshStandardMaterial({ color:'#e2b54a', roughness:.25, metalness:.85 }),
  kalkan: new THREE.MeshStandardMaterial({ color:'#4f6b5a', roughness:.4, metalness:.3 }),
  joypad:new THREE.MeshStandardMaterial({ color:'#2f3440', roughness:.5 }),
  istaka:new THREE.MeshStandardMaterial({ color:'#d9b98a', roughness:.55 }),
  istakaUc:new THREE.MeshStandardMaterial({ color:'#5b7fd6', roughness:.6 }),
  dugme:(() => { const m = new Map(); return r => m.get(r) || m.set(r, new THREE.MeshBasicMaterial({ color:r })).get(r); })(),
};
// PlayStation oynarken yüz ifadeleri: kaş çatma, şaşırma, şaşı, sırıtma, gözler kısık, bağırma
const OYUN_YUZ = [{ kas:1, agiz:.25 }, { buyuk:1, bebek:1, agiz:.55 }, { sasi:1, agiz:.15 }, { mutlu:1, acik:0 },
  { kapak:.75, kas:.7 }, { agiz:.95, buyuk:.5 }, { bakX:.8, kas:.5 }];

/* ---------- pozlar: [px,py,pz, rx,ry,rz, sx,sy,sz] ---------- */
const P = (p = [0, 0, 0], r = [0, 0, 0], s = [1, 1, 1]) => [...p, ...r, ...s];
const ayna = (a) => [-a[0], a[1], a[2], a[3], -a[4], -a[5], a[6], a[7], a[8]];
function pozTamamla(p) {
  const o = { ...p };
  ['kalca', 'ayak', 'kulak', 'on'].forEach(n => { if (o[n + 'L'] && !o[n + 'R']) o[n + 'R'] = ayna(o[n + 'L']); });
  return o;
}
const KUYRUK_OTUR = [P([0, .05, -.27], [-1.57, 0, 1.2]), P([0, .12, 0], [0, 0, .42]), P([0, .12, 0], [0, 0, .42]), P([0, .12, 0], [0, 0, .4]), P([0, .12, 0], [.35, 0, .3]), P([0, .12, 0], [.45, 0, .2])];
const KUYRUK_KIVRIL = [P([0, .07, -.29], [-1.57, 0, 1.4]), P([0, .12, 0], [0, 0, .5]), P([0, .12, 0], [0, 0, .5]), P([0, .12, 0], [0, 0, .5]), P([0, .12, 0], [0, 0, .45]), P([0, .12, 0], [0, 0, .4])];
export const POZ = {
  otur: pozTamamla({
    kok: P(), govde: P([0, .36, -.02], [.1, 0, 0], [.3, .38, .29]), gogus: P([0, .47, .17], [.15, 0, 0], [.19, .25, .13]),
    kalcaL: P([-.16, .17, -.04], [0, 0, 0], [.15, .16, .21]), ayakL: P([-.15, .04, .16], [0, 0, 0], [.075, .05, .11]),
    bas: P([0, .86, .08]), kulakL: P([-.15, .16, -.01], [-.1, 0, .32]), onL: P([-.11, .52, .17], [-1.2, 0, .04]),
    boyun: P([0, .64, .17], [.25, 0, 0]),
    ...Object.fromEntries(KUYRUK_OTUR.map((v, i) => ['k' + i, v])),
  }),
  // uyku: masanın sol boş köşesinde, laptopun yanında kıvrılmış
  kivril: pozTamamla({
    kok: P([-.62, .3, .84], [0, -.2, 0]), govde: P([0, .19, -.03], [0, 0, 0], [.34, .21, .3]), gogus: P([0, .17, .15], [0, 0, 0], [.17, .12, .1]),
    kalcaL: P([-.14, .13, -.1], [0, 0, 0], [.15, .12, .19]), ayakL: P([-.13, .05, .1], [0, 0, 0], [.06, .04, .08]),
    bas: P([.03, .25, .13], [.3, -.1, .22], [.95, .95, .95]), kulakL: P([-.15, .15, -.02], [-.35, 0, .6]), onL: P([-.09, .16, .06], [-1.5, 0, 0], [1, .5, 1]),
    boyun: P([.04, .25, .16], [.6, 0, 0], [.8, .8, .8]),
    ...Object.fromEntries(KUYRUK_KIVRIL.map((v, i) => ['k' + i, v])),
  }),
};
// temel poza kısmi değişiklik ekler (meme pozları için)
export function pozTuret(temel, degisiklik = {}) {
  const t = POZ[temel] || POZ.otur;
  const o = { ...t };
  Object.entries(degisiklik).forEach(([n, v]) => { o[n] = v; });
  return pozTamamla(o);
}

/* ---------- kedi ---------- */
const YUZ0 = { acik:1, bebek:0, bakX:0, bakY:0, kapak:0, agiz:0, kas:0, mutlu:0, buyuk:0, sasi:0 };
export function createCat({ desen = 'tekir', ton = 0, yavru = false, aksesuar = {} } = {}) {
  const { d, m } = desenMalzemeleri(desen, ton, yavru);
  const group = new THREE.Group();
  const koyu = new THREE.Color(d.govde).getHSL({}).l < .25 && !d.maske || desen === 'smokin';
  const kok = new THREE.Group(); group.add(kok);
  const dugum = { kok };
  const golgeli = [];
  const mesh = (parent, geo, mat, p = [0, 0, 0], s = [1, 1, 1], golge = true) => {
    const x = new THREE.Mesh(geo, mat); x.position.set(...p); x.scale.set(...s);
    if (golge) { x.castShadow = true; x.receiveShadow = true; golgeli.push(x); }
    parent.add(x); return x;
  };
  const grup = (ad, parent = kok) => { const g = new THREE.Group(); parent.add(g); dugum[ad] = g; return g; };

  // gövde parçaları: düğüm = grup, ölçek grubun üstünde (küre birim)
  mesh(grup('govde'), GEO.kure, m.govde);
  mesh(grup('gogus'), GEO.kure, m.gobek);
  ['L', 'R'].forEach(y => { mesh(grup('kalca' + y), GEO.kure, m.govde); mesh(grup('ayak' + y), GEO.kure, m.pati); });

  // baş
  const bas = grup('bas');
  const basOlcek = yavru ? 1.18 : 1;
  const kafa = new THREE.Group(); kafa.scale.setScalar(basOlcek); bas.add(kafa);
  mesh(kafa, GEO.kure, m.bas, [0, 0, 0], [.3, .26, .27]);
  [-1, 1].forEach(s => mesh(kafa, GEO.kure, m.yanak, [s * .12, -.08, .12], [.14, .11, .13]));
  [-1, 1].forEach(s => mesh(kafa, GEO.kure, m.agiz, [s * .044, -.088, .222], [.068, .054, .06]));
  mesh(kafa, GEO.kure, m.agiz, [0, -.135, .2], [.05, .035, .05]);
  mesh(kafa, GEO.kure, m.burun, [0, -.045, .272], [.033, .022, .02], false);
  const agiz = mesh(kafa, GEO.kure, ORTAK.agizIc, [0, -.128, .238], [.045, .001, .02], false);
  const biyik = new THREE.LineSegments(GEO.biyik, m.biyik); kafa.add(biyik);
  const gozler = [-1, 1].map(s => {
    const g = new THREE.Group(); g.position.set(s * .105, .03, .232); g.rotation.y = s * .36; kafa.add(g);
    const acikG = new THREE.Group(); g.add(acikG);
    mesh(acikG, GEO.kure, m.goz, [0, 0, 0], [.062, .07, .03], false);
    const bebek = mesh(acikG, GEO.kure, ORTAK.bebek, [0, 0, .02], [.024, .056, .016], false);
    const parilti = mesh(acikG, GEO.kure, ORTAK.parilti, [.018, .026, .034], [.014, .014, .008], false);
    const parilti2 = mesh(acikG, GEO.kure, ORTAK.parilti, [-.016, -.022, .032], [.008, .008, .006], false);
    const yay = new THREE.Mesh(GEO.yay, koyu ? ORTAK.acikCizgi : ORTAK.cizgi); yay.position.z = .02; yay.visible = false; g.add(yay);
    const kas = mesh(g, GEO.kure, ORTAK.cizgi, [-s * .005, .085, .015], [.055, .011, .01], false); kas.visible = false;
    return { g, acikG, bebek, parilti, parilti2, yay, kas, s };
  });
  ['L', 'R'].forEach((y, i) => {
    const k = grup('kulak' + y, kafa);
    mesh(k, GEO.kulak, m.kulak, [0, 0, 0], [1, 1, .55]);
    mesh(k, GEO.kulakIc, m.ic, [0, .005, .028], [1, 1, .4], false);
  });

  // ön bacaklar (omuzdan aşağı), pati ucu
  ['L', 'R'].forEach(y => {
    const o = grup('on' + y);
    mesh(o, GEO.bacak, m.bacak);
    const p = mesh(o, GEO.kure, m.pati, [0, -.44, .015], [.072, .052, .088]);
    dugum['pati' + y] = p;
  });

  // kuyruk zinciri
  let ust = kok;
  for (let i = 0; i < 6; i++) {
    const g = grup('k' + i, ust);
    const r = 1 - i * .07;
    const kuyrukMat = d.siyam && i < 2 ? m.govde : m.halka;
    mesh(g, GEO.kuyruk, kuyrukMat, [0, 0, 0], [r, 1, r]);
    ust = g;
  }

  // boyun + aksesuar
  const boyun = grup('boyun');
  if (aksesuar.papyon) {
    [-1, 1].forEach(s => { const x = mesh(boyun, GEO.papyon, ORTAK.kirmizi, [0, 0, .02]); x.scale.x = s; });
    mesh(boyun, GEO.kure, ORTAK.kirmizi, [0, 0, .03], [.03, .03, .03]);
  }
  if (aksesuar.tasma) {
    const t = mesh(boyun, GEO.tasma, ORTAK.altin, [0, 0, -.08]); t.rotation.x = Math.PI / 2;
    mesh(boyun, GEO.kure, ORTAK.altin, [0, -.04, .07], [.035, .035, .035]);
  }
  if (aksesuar.kalkan) { const k = mesh(boyun, GEO.kalkan, ORTAK.kalkan, [0, -.17, .02]); k.rotation.x = -.25; }

  // durum makinesi
  const NODLAR = Object.keys(POZ.otur);
  const taban = {};
  NODLAR.forEach(n => { taban[n] = POZ.kivril[n].slice(); });
  const yuz = { ...YUZ0, acik:0 };
  let durum = 'uyuyor', t = Math.random() * 10, bittiT = -1, kirpT = 2 + Math.random() * 3, kirp = 0;
  let meme = null, memePoz = null, uyanT = -1;

  let dis = 'uyuyor'; // dışarıdan son gelen durum; 'bitti' her karede gelse de gerinme bir kez oynar
  function setDurum(yeni) {
    if (yeni === 'uyku' || yeni === 'bekliyor') yeni = 'uyuyor';
    if (yeni === 'oynuyor') yeni = 'oyun';
    if (yeni === dis) return;
    dis = yeni;
    durum = yeni;
    if (yeni === 'bitti') bittiT = t;
  }
  function setMeme(spec, { aninda = false } = {}) {
    meme = spec || null;
    memePoz = spec ? pozTuret(spec.temel || 'otur', spec.poz) : null;
    uyanT = spec && durum === 'uyuyor' && !aninda ? t : -1; // uyuyan kedi önce gerinip uyanır
    if (aninda && spec) { // önizleme: geçişsiz doğrudan poz
      NODLAR.forEach(n => { taban[n] = memePoz[n].slice(); });
      Object.assign(yuz, YUZ0, spec.yuz);
    }
  }
  const uyaniyor = () => uyanT >= 0 && t - uyanT < 1.1;

  // eğlence odası araçları: oyun kolu ve ıstaka kökte durur (pozla birlikte gelir), yalnız ilgili durumda görünür
  // oyun kolu iki pati ucunun arasında: oyunda patiler yatay öne uzanır, uçları (±.11, .53, .61); yüzü kediye eğik
  const joypad = new THREE.Group(); joypad.position.set(0, .52, .6); joypad.rotation.x = -.4; joypad.visible = false; kok.add(joypad);
  mesh(joypad, GEO.kure, ORTAK.joypad, [0, 0, 0], [.15, .042, .08], false);
  [-1, 1].forEach(s => mesh(joypad, GEO.kure, ORTAK.joypad, [s * .12, -.02, -.035], [.06, .05, .07], false)); // tutamaklar
  [[-.06, '#ff7a59'], [.06, '#7fc8a9'], [.025, '#f2c14e'], [-.025, '#6cc3c8']].forEach(([x, r]) => mesh(joypad, GEO.kure, ORTAK.dugme(r), [x, .038, .012], [.018, .012, .018], false));
  const istaka = new THREE.Group(); istaka.position.set(.07, .6, -.4); istaka.visible = false; kok.add(istaka);
  const sopa = mesh(istaka, GEO.kure, ORTAK.istaka, [0, 0, .7], [.016, .016, .78], false);
  mesh(istaka, GEO.kure, ORTAK.istakaUc, [0, 0, 1.47], [.017, .017, .03], false);
  let vurduMu = false, sonFaz = 0;
  const VURUS_SN = 4.5, VURUS_AN = .78;
  function vurusOfset(f) { // nişan → geri çek → vur → bekle (istakanın ileri-geri konumu)
    if (f < .55) return Math.sin(t * 3) * .025;
    if (f < VURUS_AN - .03) return -.2 * (f - .55) / (VURUS_AN - .03 - .55);
    if (f < VURUS_AN) return -.2 + .34 * (f - (VURUS_AN - .03)) / .03;
    return .14 * (1 - (f - VURUS_AN) / (1 - VURUS_AN));
  }

  function hedefPoz() {
    if (meme && !uyaniyor()) return memePoz;
    if (meme || durum !== 'uyuyor') return POZ.otur;
    return POZ.kivril;
  }
  function hedefYuz() {
    if (meme && !uyaniyor()) return { ...YUZ0, ...meme.yuz };
    if (durum === 'uyuyor' && !meme) return { ...YUZ0, acik:0 };
    if (durum === 'bitti' || uyaniyor()) return { ...YUZ0, acik:0, mutlu:1 };
    if (durum === 'dusunuyor') return { ...YUZ0, bakY:.6, bakX:.3 };
    if (durum === 'oyun') return { ...YUZ0, ...OYUN_YUZ[Math.floor(t / 1.1) % OYUN_YUZ.length] }; // ekrana göre şekilden şekle
    if (durum === 'tavla') return { ...YUZ0, bakY:-.7 };
    return YUZ0;
  }

  function uygula(n, arr, ek) {
    const g = dugum[n];
    g.position.set(arr[0], arr[1], arr[2]);
    g.rotation.set(arr[3] + (ek?.rx || 0), arr[4] + (ek?.ry || 0), arr[5] + (ek?.rz || 0));
    g.scale.set(arr[6] * (ek?.s || 1), arr[7] * (ek?.sy || ek?.s || 1), arr[8] * (ek?.s || 1));
    if (ek?.py) g.position.y += ek.py;
  }

  function update(dt) {
    t += dt;
    if (durum === 'bitti' && bittiT >= 0 && t - bittiT > 1.7 && !meme) { durum = 'uyuyor'; bittiT = -1; }
    const k = 1 - Math.exp(-dt * 8);
    const hp = hedefPoz();
    NODLAR.forEach(n => { const a = taban[n], b = hp[n]; for (let i = 0; i < 9; i++) a[i] += (b[i] - a[i]) * k; });
    const hy = hedefYuz();
    if (meme?.konus && !uyaniyor()) hy.agiz = .2 + Math.abs(Math.sin(t * 9)) * .55;
    if (!meme && durum === 'sohbet' && Math.sin(t * .7) > -.2) hy.agiz = .15 + Math.abs(Math.sin(t * 8)) * .5;
    Object.keys(yuz).forEach(n => { yuz[n] += (hy[n] - yuz[n]) * Math.min(1, k * 1.6); });

    const uyur = durum === 'uyuyor' && !meme;
    const yaz = (!meme && durum === 'calisiyor') || (meme && meme.yaz && !uyaniyor());
    const oyun = !meme && durum === 'oyun'; // eğlence odası: oyun kolu — patiler hızlı ve küçük
    const ek = {};
    if (uyur) {
      const n = Math.sin(t * 1.7);
      ek.govde = { s:1 + n * .03 }; ek.bas = { py:n * .006 }; ek.gogus = { s:1 + n * .03 };
    }
    if (yaz) {
      const h = meme?.yazHiz || 11;
      ek.onL = { rx:Math.sin(t * h) * .16 }; ek.onR = { rx:Math.sin(t * h + Math.PI) * .16 };
      ek.bas = { rx:Math.sin(t * 2.3) * .03 };
    }
    if (oyun) {
      ek.onL = { rx:-.35 + Math.sin(t * 15) * .09 }; ek.onR = { rx:-.35 + Math.sin(t * 15 + 1.3) * .09 };
      ek.bas = { rx:Math.sin(t * 1.7) * .05, ry:Math.sin(t * .9) * .12 };
    } else if (!meme && durum === 'dinleniyor') {
      ek.bas = { ry:Math.sin(t * .6) * .35, rx:Math.sin(t * .8) * .05 }; // etrafa bakınır
    } else if (!meme && durum === 'sohbet') { // el sallayarak anlatır, karşısındaki başını sallar
      const anlatiyor = Math.sin(t * .7) > -.2;
      ek.onR = { rx:-1.1 + Math.sin(t * 5.5) * (anlatiyor ? .45 : .08), rz:-.3 + Math.sin(t * 2.9) * (anlatiyor ? .35 : .05) };
      ek.onL = { rx:-.4 + Math.sin(t * 4.1 + 1) * (anlatiyor ? .25 : .05) };
      ek.bas = { rx:Math.sin(t * (anlatiyor ? 3.2 : 1.6)) * .08, rz:Math.sin(t * .9) * .1 };
    } else if (!meme && durum === 'tavla') { // arada zar atar
      const z = (t % 3.2) / 3.2, e = z > .82 ? Math.sin((z - .82) / .18 * Math.PI) : 0;
      ek.onR = { rx:-.5 - 1.1 * e, rz:-.2 * e }; ek.bas = { rx:.12 };
    } else if (!meme && durum === 'bilardo') { // nişan al, geri çek, vur
      const f = (t % VURUS_SN) / VURUS_SN, o = vurusOfset(f);
      if (sonFaz < VURUS_AN && f >= VURUS_AN) vurduMu = true;
      sonFaz = f;
      istaka.position.z = -.4 + o;
      ek.onR = { rx:-1.25 + o * 2.2 }; ek.onL = { rx:-1.35 + o * .6 };
      ek.govde = { rx:.18 }; ek.bas = { rx:.15, ry:-.05 };
    }
    joypad.visible = oyun;
    istaka.visible = !meme && durum === 'bilardo';
    if (!uyur) { ek.k4 = { rz:Math.sin(t * 3.1) * .3 }; ek.k5 = { rz:Math.sin(t * 3.1 - .6) * .45 }; }
    const bitiyor = durum === 'bitti' && bittiT >= 0 && !meme;
    if (bitiyor || uyaniyor()) {
      const tb = bitiyor ? t - bittiT : t - uyanT, sure = bitiyor ? 1.6 : 1.1;
      const e = Math.sin(Math.min(1, tb / sure) * Math.PI);
      ek.onL = { rx:-1.4 * e, rz:.5 * e }; ek.onR = { rx:-1.4 * e, rz:-.5 * e };
      ek.kok = { py:bitiyor ? Math.abs(Math.sin(tb * 6)) * .1 * (1 - tb / sure) : 0 };
      ek.govde = { sy:1 + .12 * e }; ek.bas = { rx:-.25 * e };
    }
    if (meme?.anim && !uyaniyor()) meme.anim(t, ek);
    NODLAR.forEach(n => uygula(n, taban[n], ek[n]));

    // göz kırpma
    if (!uyur && yuz.acik > .8) {
      kirpT -= dt;
      if (kirpT < 0) { kirp = .14; kirpT = 2 + Math.random() * 4; }
    }
    kirp = Math.max(0, kirp - dt);
    const acik = yuz.acik * (kirp > 0 ? .08 : 1);
    gozler.forEach(o => {
      o.acikG.visible = acik > .22;
      o.acikG.scale.set(1, Math.max(.05, acik * (1 - .48 * yuz.kapak)), 1);
      o.acikG.position.y = -.022 * yuz.kapak;
      o.yay.visible = acik <= .22;
      o.yay.rotation.z = yuz.mutlu > .5 ? 0 : Math.PI;
      o.yay.position.y = yuz.mutlu > .5 ? -.02 : .01;
      const b = yuz.bebek;
      o.bebek.scale.set(.024 + b * .03, .056 + b * .006, .016);
      o.bebek.position.x = yuz.bakX * .022 - o.s * yuz.sasi * .02;
      o.g.scale.setScalar(1 + yuz.buyuk * .38);
      o.parilti2.visible = b > .5;
      o.bebek.position.y = yuz.bakY * .02;
      o.parilti.scale.setScalar(.014 + b * .01);
      o.kas.visible = yuz.kas > .1;
      o.kas.rotation.z = -o.s * .45 * yuz.kas;
    });
    agiz.scale.set(.045, .001 + yuz.agiz * .045, .02);
    agiz.visible = yuz.agiz > .02;
  }

  // kontur: arka yüzlü şişirilmiş kopya (meme parıltısı)
  let kontur = null;
  function setKontur(renk) {
    if (!kontur && renk) {
      kontur = new THREE.MeshBasicMaterial({ color:renk, side:THREE.BackSide, transparent:true, opacity:.9, depthWrite:false });
      golgeli.slice().forEach(x => {
        const c = new THREE.Mesh(x.geometry, kontur);
        c.position.copy(x.position); c.scale.copy(x.scale).multiplyScalar(1.09); c.rotation.copy(x.rotation);
        c.userData.kontur = true; x.parent.add(c);
      });
    }
    if (kontur) { kontur.visible = !!renk; if (renk) kontur.color.set(renk); }
  }

  update(0);
  // bilardo: vuruş anı bir kez bildirilir (top o an yola çıkar)
  const vurdu = () => { const v = vurduMu; vurduMu = false; return v; };
  return { group, dugum, setDurum, setMeme, setKontur, update, vurdu, get durum() { return durum; }, desen };
}

/* ---------- takım → desen eşlemesi ---------- */
const ODA_DESEN = {
  'ceo':'smokin', 'tasarim':'sarman', 'yazi':'tekir', 'kod':'siyam', 'atolye':'siyah',
  'posta':'gri-beyaz', 'sosyal':'tekir-gri', 'veri':'siyah', 'arastirma':'siyam', 'gun-sonu':'gri-beyaz',
};
const AJAN_DESEN = { 'bekci':'smokin', 'temizlikci':'sarman' };
export function ajanDeseni(ajanId, odaId) { return AJAN_DESEN[ajanId] || ODA_DESEN[odaId] || 'tekir'; }
export function ajanAksesuari(ajanId, odaId) {
  if (ajanId === 'ceo') return { papyon:true };
  if (ajanId === 'bekci') return { kalkan:true };
  if (odaId === 'atolye') return { tasma:true };
  return {};
}
