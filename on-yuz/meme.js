// Ajan Ofisi · kedi meme'leri: tıklanan kedi kendi meme pozuna geçer (fotoğraf yok, hepsi prosedürel 3D)
import * as THREE from 'three';
import { pozTuret } from './kedi.js?v=3';

const P = (p = [0, 0, 0], r = [0, 0, 0], s = [1, 1, 1]) => [...p, ...r, ...s];
const mat = (renk, ek = {}) => new THREE.MeshStandardMaterial({ color:renk, roughness:.7, ...ek });
const isik = (renk) => new THREE.MeshBasicMaterial({ color:renk, toneMapped:false });

function kutu(g, w, h, d, m, x, y, z) {
  const k = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); k.position.set(x, y, z);
  k.castShadow = true; k.receiveShadow = true; g.add(k); return k;
}
function tuval(w, h) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return { c, x:c.getContext('2d'), t };
}

/* ---------- canlı dokular ---------- */
function matrixDoku(w = 256, h = 256) {
  const d = tuval(w, h); const kolon = Array.from({ length:Math.floor(w / 10) }, () => Math.random() * h);
  d.x.fillStyle = '#020a04'; d.x.fillRect(0, 0, w, h);
  d.ciz = () => {
    d.x.fillStyle = 'rgba(2,10,4,.16)'; d.x.fillRect(0, 0, w, h);
    d.x.font = '700 11px monospace';
    kolon.forEach((y, i) => {
      d.x.fillStyle = Math.random() > .9 ? '#d9ffe0' : '#35e06a';
      d.x.fillText(Math.random() > .5 ? '1' : '0', i * 10, y);
      kolon[i] = y > h + Math.random() * 60 ? 0 : y + 11;
    });
    d.t.needsUpdate = true;
  };
  for (let i = 0; i < 40; i++) d.ciz();
  return d;
}
function haritaDoku() {
  const d = tuval(1024, 512), x = d.x;
  const g = x.createLinearGradient(0, 0, 1024, 512); g.addColorStop(0, '#071a4a'); g.addColorStop(.6, '#0d3b9c'); g.addColorStop(1, '#0a2466');
  x.fillStyle = g; x.fillRect(0, 0, 1024, 512);
  const kitalar = [[200, 170, 120, 80], [270, 340, 60, 100], [520, 150, 90, 60], [540, 290, 70, 110], [720, 180, 170, 90], [820, 370, 70, 45]];
  for (let px = 8; px < 1024; px += 13) for (let py = 8; py < 512; py += 13) {
    if (kitalar.some(([cx, cy, rx, ry]) => ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 < 1)) { x.fillStyle = 'rgba(140,200,255,.75)'; x.fillRect(px, py, 4, 4); }
  }
  x.strokeStyle = 'rgba(160,220,255,.5)'; x.lineWidth = 1.5;
  const n = [[210, 160], [540, 150], [760, 190], [560, 300], [290, 330], [830, 370]];
  n.forEach((a, i) => n.slice(i + 1).forEach(b => { if (Math.random() > .4) { x.beginPath(); x.moveTo(...a); x.lineTo(...b); x.stroke(); } }));
  n.forEach(([a, b]) => { x.fillStyle = '#e8f6ff'; x.beginPath(); x.arc(a, b, 5, 0, 7); x.fill(); });
  d.t.needsUpdate = true; return d;
}
function girdapDoku() {
  const d = tuval(256, 256), x = d.x;
  x.fillStyle = '#0a1240'; x.fillRect(0, 0, 256, 256);
  for (let k = 0; k < 4; k++) {
    x.strokeStyle = ['#3a5bff', '#8fb0ff', '#ffffff', '#2236b8'][k]; x.lineWidth = 7 - k;
    x.beginPath();
    for (let a = 0; a < 18; a += .05) { const r = a * 7; x.lineTo(128 + Math.cos(a + k * 1.6) * r, 128 + Math.sin(a + k * 1.6) * r); }
    x.stroke();
  }
  d.t.center.set(.5, .5); d.t.needsUpdate = true; return d;
}

/* ---------- prosedürel aksesuarlar (kedi çerçevesi: masa üstü y=.30, masa z .45–1.35) ---------- */
const BEJ = mat('#e4dccb'), BEJ_KOYU = mat('#cfc5b0'), SIYAH = mat('#1c1c1f', { roughness:.4 }), METAL = mat('#9aa0a6', { metalness:.7, roughness:.35 });
function crt(g, x, z, ry, ekranMat, olcek = 1) {
  const c = new THREE.Group(); c.position.set(x, .3, z); c.rotation.y = ry; c.scale.setScalar(olcek); g.add(c);
  kutu(c, .56, .48, .42, BEJ, 0, .3, 0);
  kutu(c, .4, .34, .26, BEJ_KOYU, 0, .3, -.3);
  kutu(c, .3, .05, .26, BEJ_KOYU, 0, .03, 0);
  const cer = kutu(c, .5, .42, .02, mat('#2a2a28'), 0, .31, .21);
  cer.castShadow = false;
  const e = new THREE.Mesh(new THREE.PlaneGeometry(.42, .34), ekranMat); e.position.set(0, .31, .225); c.add(e);
  return c;
}
function pcKasa(g, x, z, ry, acik = ['+x'], y = .3) {
  const c = new THREE.Group(); c.position.set(x, y, z); c.rotation.y = ry; g.add(c);
  const W = .42, H = .66, D = .62, t = .02, m = mat('#3a3d42', { metalness:.4, roughness:.45 });
  const yuzler = { '-x':[t, H, D, -W / 2, H / 2, 0], '+x':[t, H, D, W / 2, H / 2, 0], '+y':[W, t, D, 0, H, 0], '-y':[W, t, D, 0, 0, 0], '-z':[W, H, t, 0, H / 2, -D / 2], '+z':[W, H, t, 0, H / 2, D / 2] };
  Object.entries(yuzler).forEach(([k, v]) => { if (!acik.includes(k)) kutu(c, ...v.slice(0, 3), m, ...v.slice(3)); });
  kutu(c, .02, .4, .44, mat('#2f7a46'), -W / 2 + .03, .36, 0);
  const fan = new THREE.Mesh(new THREE.TorusGeometry(.07, .015, 8, 20), METAL); fan.position.set(-.1, .52, -D / 2 + .04); c.add(fan);
  kutu(c, .14, .08, .1, METAL, -.06, .16, .12);
  return c;
}
function kablolar(g, adet, merkez, boyut) {
  const renk = ['#d23a3a', '#2f6fd8', '#e0b02a', '#3aa35a', '#e8e8e8', '#7a4fc0', '#1b1b1b', '#e07a2a'];
  for (let i = 0; i < adet; i++) {
    const nok = Array.from({ length:5 }, () => new THREE.Vector3(
      merkez[0] + (Math.random() - .5) * boyut[0], merkez[1] + (Math.random() - .5) * boyut[1], merkez[2] + (Math.random() - .5) * boyut[2]));
    const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(nok), 40, .006 + Math.random() * .006, 6), mat(renk[i % renk.length], { roughness:.5 }));
    m.castShadow = true; g.add(m);
  }
}
function kapuson(kedi, g, renk, kenar) {
  const m = mat(renk, { side:THREE.DoubleSide, roughness:.85 });
  const h = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 18, .78 * Math.PI, 1.44 * Math.PI, 0, .7 * Math.PI), m);
  h.scale.set(.36, .33, .34); h.position.set(0, .03, -.02); kedi.dugum.bas.add(h);
  const pelerin = new THREE.Mesh(new THREE.CylinderGeometry(.22, .42, .62, 26, 1, true), m);
  pelerin.position.set(0, .4, -.04); kedi.dugum.kok.add(pelerin);
  const parcalar = [h, pelerin];
  if (kenar) {
    const k = new THREE.Mesh(new THREE.TorusGeometry(.25, .03, 10, 28), mat(kenar, { roughness:.95 }));
    k.position.set(0, .01, .17); k.scale.set(1.08, 1, 1); kedi.dugum.bas.add(k); parcalar.push(k);
  }
  return parcalar; // kapatınca sökülür
}
function laptop(g, x, z, ry, ekranMat) {
  const c = new THREE.Group(); c.position.set(x, .3, z); c.rotation.y = ry; g.add(c);
  kutu(c, .5, .025, .34, mat('#2b2d31', { metalness:.5, roughness:.4 }), 0, .012, 0);
  const kapak = new THREE.Group(); kapak.position.set(0, .02, -.16); kapak.rotation.x = -.25; c.add(kapak);
  kutu(kapak, .5, .32, .018, mat('#2b2d31', { metalness:.5, roughness:.4 }), 0, .16, 0);
  const e = new THREE.Mesh(new THREE.PlaneGeometry(.46, .28), ekranMat); e.position.set(0, .16, .011); kapak.add(e);
  return c;
}
function ahize(kedi, g) {
  const el = new THREE.Group(); el.position.set(-.02, -.36, .06); kedi.dugum.onR.add(el);
  const m = mat('#c83c32', { roughness:.3 });
  const sap = new THREE.Mesh(new THREE.CapsuleGeometry(.03, .26, 6, 12), m); el.add(sap);
  [-1, 1].forEach(s => { const u = new THREE.Mesh(new THREE.SphereGeometry(.055, 14, 10), m); u.scale.set(1, .65, 1); u.position.set(-.03, s * .16, 0); el.add(u); });
  const taban = new THREE.Group(); taban.position.set(.55, .3, .8); g.add(taban);
  kutu(taban, .3, .1, .24, m, 0, .05, 0);  // kırmızı retro telefon
  kutu(taban, .2, .03, .14, mat('#d8cfc0'), 0, .11, .02);
  const kordon = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(.45, .36, .78), new THREE.Vector3(.35, .32, .6), new THREE.Vector3(.3, .45, .4), new THREE.Vector3(.25, .7, .25)]), 30, .008, 5), m);
  g.add(kordon);
  return [el];
}
function kagitlar(g, x, z) {
  const m = mat('#fbf8f1', { roughness:.95 }), m2 = mat('#f1ead8', { roughness:.95 });
  for (let i = 0; i < 9; i++) {
    const k = kutu(g, .34, .012, .44, i % 2 ? m : m2, x + (Math.random() - .5) * .12, .305 + i * .012, z + (Math.random() - .5) * .1);
    k.rotation.y = (Math.random() - .5) * .7;
  }
  for (let i = 0; i < 4; i++) { const k = kutu(g, .3, .006, .4, m, x + .35 + Math.random() * .4, .305, z + (Math.random() - .5) * .4); k.rotation.y = Math.random() * 3; }
}
function arka(g, doku, w, h, z, y = 1) {
  const p = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map:doku.t, toneMapped:false }));
  p.position.set(0, y, z); g.add(p); return p;
}

/* ---------- meme tanımları ---------- */
const OTUR_ON = P([-.11, .52, .17], [-1.2, 0, .04]);
const MEMELER = {
  tasarimci: {
    yazi:'BİR REVİZE DAHA MI?',
    kedi:{ poz:{ bas:P([0, .86, .1], [-.14, 0, .16]), onR:P([.11, .52, .17], [-.25, 0, -.05]) }, yuz:{ bebek:1, buyuk:1, bakY:.25 } },
    kam:[.25, 1.0, 2.4], hedef:[0, .82, .1],
  },
  temizlikci: {
    yazi:'YER AÇIYORUM',
    // masanın solunda, yerde duran açık kasanın içine kafa üstü girmiş; arkası ve kuyruğu dışarıda
    kedi:{ temel:'kivril', poz:{ kok:P([-.98, -.56, 1.75], [0, -Math.PI / 2, 0]), bas:P([0, .24, .22], [.15, 0, 0]),
      k0:P([0, .1, -.3], [-1.2, 0, 0]), k1:P([0, .12, 0], [.35, 0, 0]), k2:P([0, .12, 0], [.3, 0, 0]), k3:P([0, .12, 0], [.25, 0, .2]), k4:P([0, .12, 0], [.2, 0, .3]), k5:P([0, .12, 0], [.1, 0, .3]) }, yuz:{ bebek:.6 } },
    sahne(g) { pcKasa(g, -1.32, 1.75, 0, ['+x', '+z'], -.56); },
    kam:[-.45, .45, 4.4], hedef:[-1.05, -.3, 1.75],
  },
  'blog-yazari': 'girdap', editor: 'girdap',
  girdap: {
    yazi:'OKURLAR SENİ SEVİYOR',
    kedi:{ poz:{ bas:P([0, .84, .1], [-.18, 0, -.22]), kulakL:P([-.15, .14, -.03], [-.45, 0, .75]), onR:P([.11, .52, .17], [-.25, 0, -.05]) }, yuz:{ acik:0, mutlu:1 } },
    sahne(g, d) {
      const gd = girdapDoku(); d.girdap = gd;
      crt(g, .72, .85, -.85, new THREE.MeshBasicMaterial({ map:gd.t, toneMapped:false }), 1.1);
      const kol = new THREE.Group(); kol.position.set(.62, .62, .78); g.add(kol);
      kol.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(.02, 1.18, .12).sub(kol.position).normalize());
      const ten = mat('#f0c8a8', { roughness:.6 });
      const boy = new THREE.Vector3(.02, 1.2, .12).distanceTo(kol.position);
      const k = new THREE.Mesh(new THREE.CapsuleGeometry(.055, boy - .2, 6, 14), ten); k.rotation.x = Math.PI / 2; k.position.z = (boy - .1) / 2; kol.add(k);
      const el = new THREE.Mesh(new THREE.SphereGeometry(.09, 18, 14), ten); el.scale.set(1.1, .55, 1.25); el.position.z = boy - .06; kol.add(el);
      const yen = new THREE.Mesh(new THREE.CylinderGeometry(.075, .075, .1, 16), mat('#e8e2d6')); yen.rotation.x = Math.PI / 2; yen.position.z = .06; kol.add(yen);
      d.el = el; d.elZ = boy - .06;
    },
    anim(t, d) { if (d.girdap) d.girdap.t.rotation = -t * 1.6; if (d.el) d.el.position.z = d.elZ + Math.sin(t * 5) * .05; },
    kam:[.55, 1.1, 2.5], hedef:[.2, .82, .3],
  },
  'sosyal-yazar': {
    yazi:'GÜNDEMDE NE VAR',
    kedi:{ poz:{ bas:P([0, .86, .1], [0, -.6, .05]) }, yuz:{ bakX:1, kapak:.45, bebek:.6, buyuk:.3 }, yaz:true },
    kam:[.6, 1.0, 2.1], hedef:[0, .84, .1],
  },
  posta: {
    yazi:'GELEN KUTUSU: 999+',
    kedi:{ poz:{ govde:P([0, .38, -.02], [-.04, 0, 0], [.28, .4, .28]), bas:P([0, .9, .08], [.12, 0, 0]) }, yuz:{ bebek:.3 }, yaz:true, yazHiz:17 },
    sahne(g) { crt(g, 0, 1.0, Math.PI, new THREE.MeshBasicMaterial({ color:'#9fc4ff', toneMapped:false }), 1); },
    kam:[2.3, 1.55, 2.6], hedef:[0, .72, .35],
  },
  ceo: {
    yazi:'EVET PATRON, HALLEDİYORUM',
    kedi:{ poz:{ onR:P([.11, .55, .12], [-2.55, 0, .5]), bas:P([0, .86, .08], [-.05, 0, -.14]) }, yuz:{ kapak:.35, bakX:-.4 }, konus:true },
    sahne(g, d, kedi) { d.sok = ahize(kedi, g); },
    kam:[.15, 1.05, 2.6], hedef:[0, .82, .1],
  },
  'kod-inceleyici': 'burun', 'test-yazari': 'burun',
  burun: {
    yazi:'BU SATIRDA BUG VAR',
    kedi:{ poz:{ govde:P([0, .36, .04], [.42, 0, 0], [.3, .38, .29]), gogus:P([0, .45, .26], [.45, 0, 0], [.19, .25, .13]), bas:P([0, .64, .46], [.1, 0, 0]), onL:P([-.11, .5, .3], [-1.0, 0, .04]) }, yuz:{ sasi:1, bebek:.7, buyuk:.2 } },
    sahne(g) { crt(g, 0, 1.0, Math.PI, new THREE.MeshBasicMaterial({ color:'#cfe3ff', toneMapped:false })); },
    kam:[2.1, 1.0, 1.2], hedef:[0, .62, .65],
  },
  arastirma: {
    yazi:'KAYNAK ARIYORUM',
    kedi:{ poz:{ govde:P([0, .36, .06], [.5, 0, 0], [.3, .38, .29]), gogus:P([0, .44, .28], [.5, 0, 0], [.19, .25, .13]), bas:P([0, .58, .6], [.15, 0, 0]), onL:P([-.13, .5, .3], [-1.1, 0, .2]) }, yuz:{} },
    sahne(g) { pcKasa(g, 0, .95, 0, ['-z']); },
    kam:[1.9, 1.05, 1.5], hedef:[0, .55, .6],
  },
  'gun-sonu': {
    yazi:'BUGÜN NE YAPTIK',
    kedi:{ poz:{ kok:P([-.55, .4, .86], [0, .15, 0]), onL:P([-.11, .52, .17], [-.2, 0, .04]) }, yuz:{ kapak:.2, bakY:-.3 } },
    sahne(g) { kagitlar(g, -.55, .86); },
    kam:[0, 1.75, 4.0], hedef:[-.45, .85, .8],
  },
  gelistirici: {
    yazi:'DEPLOY ETTİM BİLE',
    kedi:{ poz:{ bas:P([0, .86, .1], [.04, .25, 0]) }, yuz:{ kas:1, kapak:.42, bakX:-.6 } },
    sahne(g, d, kedi) {
      d.harita = haritaDoku(); arka(g, d.harita, 4.2, 2.2, -.45, 1.0);
      d.ekran = matrixDoku(); laptop(g, .48, .72, -.6, new THREE.MeshBasicMaterial({ map:d.ekran.t, toneMapped:false }));
      d.sok = kapuson(kedi, g, '#2a2d34');
    },
    anim(t, d) { if (t - (d.son || 0) > .07) { d.son = t; d.ekran.ciz(); } },
    kam:[.35, 1.0, 2.5], hedef:[.1, .8, .2],
  },
  veri: {
    yazi:'ANLAMADIM',
    kedi:{ poz:{ bas:P([0, .84, .1], [0, .2, .28]), onR:P([.11, .52, .17], [-.3, 0, -.05]) }, yuz:{ bebek:.9, buyuk:.25, agiz:.35, bakX:-.3 } },
    sahne(g, d, kedi) {
      crt(g, -.5, .85, .5, new THREE.MeshBasicMaterial({ color:'#7fa6a0', toneMapped:false }), .9);
      kablolar(g, 40, [0, 1.4, -.75], [3.2, 2.0, .4]);
      kablolar(g, 8, [.75, .45, .6], [.5, .3, .6]);
      d.sok = kapuson(kedi, g, '#b8322b', '#f5f1ea');
    },
    kam:[.2, 1.25, 3.0], hedef:[0, .8, .1],
  },
  bekci: {
    yazi:'BU DOSYA İÇERİ GİREMEZ',
    kedi:{ poz:{ onL:P([-.11, .5, .18], [-1.5, 0, .95]), onR:P([.11, .56, .2], [-1.5, 0, -.95]), bas:P([0, .87, .07], [-.1, 0, .06]) }, yuz:{ kapak:.6, bakX:.2 }, kontur:'#4dff7a' },
    sahne(g, d) { d.ekran = matrixDoku(256, 256); arka(g, d.ekran, 3.6, 2.4, -.42, 1.0); },
    anim(t, d) { if (t - (d.son || 0) > .06) { d.son = t; d.ekran.ciz(); } },
    kam:[.1, 1.35, 2.7], hedef:[0, .7, .15],
  },
};
// kendi ajan id'lerin için: ajan id'sinde meme yoksa odasının meme'si oynar
const ODA_MEME = { yazi:'girdap', kod:'burun', tasarim:'tasarimci', sosyal:'sosyal-yazar', arastirma:'arastirma', 'gun-sonu':'gun-sonu',
  atolye:'gelistirici', bakim:'bekci', posta:'posta', veri:'veri', ceo:'ceo' };
export function memeBul(id, oda) { let m = MEMELER[id] ?? ODA_MEME[oda]; while (typeof m === 'string') m = MEMELER[m]; return m || null; }

/* ---------- altyazı ---------- */
function yaziKur() {
  if (!document.getElementById('memeFont')) {
    const l = document.createElement('link'); l.id = 'memeFont'; l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?family=Anton&display=swap'; document.head.append(l);
    const s = document.createElement('style');
    s.textContent = `#memeYazi{position:fixed;left:50%;bottom:9vh;transform:translate(-50%,20px) scale(.92);z-index:60;pointer-events:none;
      font:400 clamp(34px,5.6vw,86px)/1.02 Anton,Impact,'Arial Black',sans-serif;color:#fff;text-transform:uppercase;letter-spacing:.01em;
      -webkit-text-stroke:.07em #000;paint-order:stroke fill;text-shadow:0 .05em .12em rgba(0,0,0,.45);text-align:center;max-width:92vw;
      opacity:0;transition:opacity .25s ease,transform .35s cubic-bezier(.2,1.4,.4,1)}
      body.meme-acik #etiketler{opacity:0;transition:opacity .2s}
      #memeYazi.acik{opacity:1;transform:translate(-50%,0) scale(1)}`;
    document.head.append(s);
  }
  let d = document.getElementById('memeYazi');
  if (!d) { d = document.createElement('div'); d.id = 'memeYazi'; document.body.append(d); }
  return d;
}

/* ---------- oynatıcı ---------- */
export function memeKur({ kameraGit, controls, iptal }) {
  let aktif = null, sinirZaman = 0;
  // yakın plan için OrbitControls sınırlarını geçici gevşet (minDistance 14 kamerayı geri iter)
  const sinir = controls ? { min:controls.minDistance, pol:controls.maxPolarAngle } : null;
  const gevset = () => { if (!sinir) return; clearTimeout(sinirZaman); controls.minDistance = 1.5; controls.maxPolarAngle = 1.5; };
  const geriAl = () => { if (!sinir) return; clearTimeout(sinirZaman); sinirZaman = setTimeout(() => { controls.minDistance = sinir.min; controls.maxPolarAngle = sinir.pol; }, 1400); };
  const yazi = yaziKur();
  function kapat() {
    if (!aktif) return null;
    const a = aktif; aktif = null;
    a.zamanlar.forEach(clearTimeout);
    cancelAnimationFrame(a.raf);
    a.kedi.setMeme(null); a.kedi.setKontur(null);
    a.sok.forEach(x => x.parent?.remove(x));
    a.props.parent?.remove(a.props);
    a.ajan.memeAktif = false;
    yazi.classList.remove('acik');
    document.body.classList.remove('meme-acik');
    geriAl();
    return a.ajan;
  }
  function oynat(ajan, { bitince, tut = false, aninda = false } = {}) {
    kapat();
    const kedi = ajan.kedi; const m = memeBul(ajan.id, ajan.oda);
    if (!kedi || !m) { bitince?.(); return false; }
    const props = new THREE.Group(); kedi.group.add(props);
    const veri = {};
    m.sahne?.(props, veri, kedi);
    const uyuyordu = kedi.durum === 'uyuyor';
    kedi.setMeme(m.kedi, { aninda });
    if (m.kedi.kontur) kedi.setKontur(m.kedi.kontur);
    kedi.group.updateMatrixWorld(true);
    const poz = kedi.group.localToWorld(new THREE.Vector3(...m.kam));
    const hedef = kedi.group.localToWorld(new THREE.Vector3(...m.hedef));
    gevset();
    kameraGit(poz, hedef, 1.0, aninda);
    ajan.memeAktif = true;
    document.body.classList.add('meme-acik');
    const a = { ajan, kedi, props, sok:veri.sok || [], zamanlar:[], raf:0 };
    aktif = a;
    const t0 = performance.now();
    const dongu = () => { if (aktif !== a) return; m.anim?.((performance.now() - t0) / 1000, veri); a.raf = requestAnimationFrame(dongu); };
    dongu();
    const yaziGecikme = (uyuyordu ? 1100 : 0) + 650;
    a.zamanlar.push(setTimeout(() => { yazi.textContent = m.yazi; yazi.classList.add('acik'); }, yaziGecikme));
    if (!tut) a.zamanlar.push(setTimeout(() => { kapat(); bitince?.(); }, yaziGecikme + 3000));
    return true;
  }
  addEventListener('keydown', e => { if (e.key === 'Escape' && aktif) { const a = kapat(); iptal?.(a); } });
  return { oynat, kapat, aktif:() => !!aktif };
}
