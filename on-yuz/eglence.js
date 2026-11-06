// Ajan Ofisi · eğlence odası ve kedi yatakları (prosedürel, harici dosya yok, model çağrısı yok)
// eglenceKur: PlayStation'lı TV, kanepe, armut koltuk, bilardo, iki tavla, çay-kahve köşesi, koltuklar.
// Döndürdüğü "yer"ler kedilerin gündüz oturduğu noktalardır (oda grubuna göre yerel).
import * as THREE from 'three';

const PI = Math.PI;
const yon = (x, z, hx, hz) => Math.atan2(hx - x, hz - z); // kedi +z'ye bakar; (hx,hz)'ye dönmesi için ry

function tvDoku(tuvalDoku) {
  const { ctx, t } = tuvalDoku(256, 144);
  const g = ctx.createLinearGradient(0, 0, 0, 144);
  g.addColorStop(0, '#5b7fd6'); g.addColorStop(1, '#9fd8b0');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 256, 144);
  ctx.fillStyle = '#7a5c3a'; ctx.fillRect(0, 108, 256, 36);                // yol
  ctx.fillStyle = '#ff7a59'; ctx.fillRect(60, 84, 34, 22);                  // araba 1
  ctx.fillStyle = '#f2c14e'; ctx.fillRect(150, 90, 34, 18);                 // araba 2
  ctx.fillStyle = '#fff'; ctx.font = '600 18px Inter'; ctx.fillText('P1  03:12  P2', 70, 26);
  t.needsUpdate = true; return t;
}
function tavlaDoku(tuvalDoku) {
  const { ctx, t } = tuvalDoku(256, 192);
  ctx.fillStyle = '#7a4e2d'; ctx.fillRect(0, 0, 256, 192);
  ctx.fillStyle = '#e9cfa3'; ctx.fillRect(10, 10, 113, 172); ctx.fillRect(133, 10, 113, 172);
  for (let yarim = 0; yarim < 2; yarim++) for (let i = 0; i < 6; i++) {
    const x0 = 10 + yarim * 123 + i * 18.8;
    [[10, 1], [182, -1]].forEach(([y, s], k) => {
      ctx.fillStyle = (i + k) % 2 ? '#a3402c' : '#3b342c';
      ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + 18.8, y); ctx.lineTo(x0 + 9.4, y + s * 72); ctx.fill();
    });
  }
  t.needsUpdate = true; return t;
}

export function eglenceKur(g, oda, { kutu, mat, aoLeke, tuvalDoku }) {
  const yerler = [];
  const yer = (x, z, y, ry, durum, aktivite) => yerler.push({ x, z, y, ry, durum, aktivite });
  const silindir = (r1, r2, h, renk, x, y, z, seg = 18) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, seg), typeof renk === 'string' ? mat(renk) : renk);
    m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; g.add(m); return m;
  };
  const kure = (r, renk, x, y, z, sx = 1, sy = 1, sz = 1) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 12), typeof renk === 'string' ? mat(renk) : renk);
    m.position.set(x, y, z); m.scale.set(sx, sy, sz); m.castShadow = true; m.receiveShadow = true; g.add(m); return m;
  };

  // halı (oturma alanı)
  const hali = kutu(g, 6.2, .03, 4.2, '#e9b48f', -3.3, .125, -1.6, .015, false); hali.receiveShadow = true;
  kutu(g, 5.8, .032, 3.8, '#f6dcc4', -3.3, .127, -1.6, .015, false);

  // TV + PlayStation (arka duvar, sol)
  kutu(g, 3.0, .5, .55, '#8d8276', -3.4, .37, -4.42, .05);                          // TV ünitesi
  kutu(g, 2.5, 1.45, .1, '#2b2724', -3.4, 1.62, -4.66, .03);                       // TV kasası
  const tv = new THREE.Mesh(new THREE.PlaneGeometry(2.3, 1.3), new THREE.MeshBasicMaterial({ map:tvDoku(tuvalDoku), toneMapped:false }));
  tv.position.set(-3.4, 1.62, -4.6); g.add(tv);
  kutu(g, .12, .48, .4, '#f4f2ee', -2.25, .86, -4.42, .03);                        // PlayStation (dik)
  kutu(g, .13, .06, .41, '#2b2724', -2.25, .86, -4.42, .01, false);                // siyah orta şerit
  [-3.9, -3.5].forEach(x => kutu(g, .24, .06, .14, '#3a3f4a', x, .65, -4.3, .03));    // oyun kolları
  aoLeke(g, 3.4, 1.2, -3.4, -4.3, .118, .7);

  // kanepe (TV'ye bakar) + armut koltuk
  kutu(g, 3.6, .42, 1.05, '#6f86b8', -3.4, .35, -1.35, .12);                       // oturak
  kutu(g, 3.6, .75, .28, '#5f76a8', -3.4, .7, -.86, .1);                           // sırt (TV'nin tersinde)
  [-5.1, -1.7].forEach(x => kutu(g, .28, .6, 1.05, '#5f76a8', x, .55, -1.35, .1));  // kolçaklar
  [-4.45, -3.4, -2.35].forEach(x => {
    kutu(g, .95, .12, .85, '#8aa0cc', x, .62, -1.4, .06);                           // minderler
    yer(x, -1.45, .68, PI, 'oynuyor', 'oyun');
  });
  kure(.62, '#f2876b', -6.0, .45, -2.3, 1.05, .62, 1.05);                          // armut koltuk
  yer(-6.0, -2.3, .72, yon(-6.0, -2.3, -3.4, -4.6), 'oynuyor', 'oyun');
  aoLeke(g, 4.6, 1.8, -3.4, -1.3, .118, .8);

  // bilardo masası (sağ arka)
  const BX = 3.4, BZ = -2.7;
  [[-1.2, -.62], [1.2, -.62], [-1.2, .62], [1.2, .62]].forEach(([dx, dz]) => kutu(g, .18, .78, .18, '#5a3d2a', BX + dx, .5, BZ + dz, .04));
  kutu(g, 2.9, .24, 1.62, '#6b4a33', BX, .96, BZ, .06);
  kutu(g, 2.56, .04, 1.3, '#2f7d55', BX, 1.09, BZ, .015, false);
  [['#f4f2ee', -.7, .1], ['#f2c14e', .5, -.2], ['#c95c45', .62, .05], ['#3f7fb5', .74, -.08], ['#2b2724', .86, .14], ['#7a5cc4', .5, .25]]
    .forEach(([r, dx, dz]) => kure(.06, r, BX + dx, 1.17, BZ + dz));
  const istaka = kutu(g, 1.9, .035, .035, '#d9b98a', BX - .9, 1.18, BZ + .2, .015);
  istaka.rotation.y = .12;
  [6.55, 6.7].forEach((x, i) => { const s = kutu(g, .035, 1.7, .035, '#d9b98a', x, .95, -4.55 + i * .12, .015); s.rotation.z = -.12; });
  kutu(g, 1.3, .06, .5, '#fff1cf', BX, 2.45, BZ, .03, false);                      // masa lambası
  kutu(g, .02, .5, .02, '#8d8276', BX, 2.72, BZ, .01, false);
  aoLeke(g, 3.6, 2.4, BX, BZ, .118, .8);
  yer(BX - 1.75, BZ, .12, PI / 2, 'oynuyor', 'bilardo');
  yer(BX + 1.75, BZ, .12, -PI / 2, 'dinleniyor', 'bilardo');
  yer(BX, BZ + 1.3, .12, PI, 'dinleniyor', 'bilardo');

  // iki tavla masası (ön sol), karşılıklı minderler
  const tavla = tavlaDoku(tuvalDoku);
  [-4.6, -1.8].forEach(TX => {
    const TZ = 1.55;
    kutu(g, 1.05, .08, .82, '#e9e1d4', TX, .5, TZ, .03);
    [[-.4, -.3], [.4, -.3], [-.4, .3], [.4, .3]].forEach(([dx, dz]) => kutu(g, .07, .4, .07, '#c9bfb1', TX + dx, .28, TZ + dz, .02));
    const tahta = new THREE.Mesh(new THREE.PlaneGeometry(.86, .64), new THREE.MeshStandardMaterial({ map:tavla, roughness:.8 }));
    tahta.rotation.x = -PI / 2; tahta.rotation.z = PI / 2; tahta.position.set(TX, .545, TZ); g.add(tahta);
    [[-.18, .1, '#f4f2ee'], [-.1, -.15, '#2b2724'], [.15, .12, '#f4f2ee'], [.2, -.05, '#2b2724']]
      .forEach(([dx, dz, r]) => silindir(.045, .045, .025, r, TX + dx, .56, TZ + dz, 14));
    [[-.95, PI / 2], [.95, -PI / 2]].forEach(([dx, ry]) => {
      kutu(g, .62, .18, .62, '#f5a463', TX + dx, .2, TZ, .08);
      yer(TX + dx, TZ, .3, ry, 'oynuyor', 'tavla');
    });
    aoLeke(g, 2.8, 1.4, TX, TZ, .118, .7);
  });

  // çay-kahve köşesi (sağ duvar)
  kutu(g, .9, .9, 2.8, '#e9d8c4', 6.2, .55, 1.7, .05);
  kutu(g, .95, .06, 2.85, '#f6efe4', 6.2, 1.03, 1.7, .02);
  kutu(g, .5, .62, .42, '#3b3a3a', 6.25, 1.37, .75, .05);                           // kahve makinesi
  kutu(g, .2, .05, .16, '#8d8276', 6.0, 1.2, .75, .01);
  silindir(.07, .06, .1, '#fff5e8', 6.0, 1.11, .75);                                // fincan
  silindir(.2, .24, .34, mat('#c9ccd1', { metalness:.6, roughness:.3 }), 6.25, 1.23, 2.0); // çaydanlık (alt)
  silindir(.13, .16, .24, mat('#d8dbe0', { metalness:.6, roughness:.3 }), 6.25, 1.52, 2.0); // demlik (üst)
  [2.55, 2.7, 2.85].forEach(z => silindir(.045, .035, .12, mat('#c95c45', { transparent:true, opacity:.85 }), 6.0, 1.12, z, 12)); // ince belli
  aoLeke(g, 1.6, 3.2, 6.2, 1.7, .118, .7);
  yer(5.15, .95, .12, PI / 2, 'dinleniyor', 'kahve');
  yer(5.15, 2.35, .12, PI / 2, 'dinleniyor', 'kahve');

  // sohbet köşesi: iki koltuk + sehpa
  [[1.25, PI / 2 + .5], [3.25, -PI / 2 - .5]].forEach(([x, ry]) => {
    const k = new THREE.Group(); k.position.set(x, 0, 2.35); k.rotation.y = ry; g.add(k);
    kutu(k, .95, .4, .9, '#7fc8a9', 0, .33, 0, .1); kutu(k, .95, .6, .22, '#6cb497', 0, .65, -.36, .08);
    yer(x, 2.35, .53, ry, 'dinleniyor', 'sohbet');
  });
  silindir(.38, .32, .06, '#e9e1d4', 2.25, .5, 2.35); silindir(.05, .05, .4, '#c9bfb1', 2.25, .28, 2.35);
  [2.15, 2.35].forEach(x => silindir(.045, .035, .11, mat('#c95c45', { transparent:true, opacity:.85 }), x, .58, 2.35, 12));

  // köşe bitkileri
  [[-6.3, -4.3], [6.3, 4.1], [-6.3, 4.1]].forEach(([x, z]) => {
    kutu(g, .55, .55, .55, '#d9c3a5', x, .4, z, .1);
    const y = mat('#9db58a', { flatShading:true, roughness:.9 });
    [[0, 1.0, 0, .45], [.15, 1.3, .05, .32]].forEach(([dx, yy, dz, r]) => {
      const m = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 0), y); m.position.set(x + dx, yy, z + dz); m.castShadow = true; g.add(m);
    });
  });
  return yerler;
}

// Fazla kedi için ortadaki boş şeritte yere oturma noktaları
export function tasmaYerleri(n) {
  const yerler = [];
  for (let i = 0; yerler.length < n; i++) {
    const sira = Math.floor(i / 12), j = i % 12;
    yerler.push({ x:-5.4 + j * .8, z:.25 + (sira % 2) * .75 - Math.floor(sira / 2) * .3, y:.12, ry:(j % 2 ? .4 : -.4), durum:'dinleniyor', aktivite:'yer' });
  }
  return yerler;
}

// Kedi yatağı: n kedi yan yana kıvrılır. Döndürülen noktalar kıvrılmış kedinin merkezi (oda grubuna göre yerel).
export function yatakKur(g, x, z, n, renk, { kutu }) {
  const W = Math.max(1.3, .5 + .72 * n), D = 1.05;
  kutu(g, W, .14, D, '#f3e3cf', x, .19, z, .06);                                    // minder
  kutu(g, W + .16, .16, .14, renk, x, .25, z - D / 2, .06);                          // kenarlar
  kutu(g, W + .16, .12, .14, renk, x, .23, z + D / 2, .06);
  [-1, 1].forEach(s => kutu(g, .14, .16, D, renk, x + s * W / 2, .25, z, .06));
  kutu(g, .5, .1, .3, '#fff8ee', x - W / 2 + .4, .31, z - .25, .05);                // yastık
  return Array.from({ length:n }, (_, i) => ({ x:x - W / 2 + .5 + i * .72 + .1, z:z + .05, y:.27 }));
}

// "Miyaw" balonu: her söz için bir kez çizilen doku
const BALON = new Map();
export function balonDoku(metin, tuvalDoku) {
  if (BALON.has(metin)) return BALON.get(metin);
  const { ctx, t } = tuvalDoku(256, 128);
  ctx.fillStyle = 'rgba(255,255,255,.96)'; ctx.strokeStyle = 'rgba(59,52,44,.18)'; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.roundRect(8, 8, 240, 82, 30); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(110, 88); ctx.lineTo(128, 118); ctx.lineTo(146, 88); ctx.fill();
  ctx.fillStyle = '#3b342c'; ctx.font = '600 38px "Space Grotesk", Inter, sans-serif'; ctx.textAlign = 'center';
  ctx.fillText(metin, 128, 62);
  t.needsUpdate = true; BALON.set(metin, t); return t;
}
