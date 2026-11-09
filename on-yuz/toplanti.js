// Ajan Ofisi · toplantı odası (prosedürel, model çağrısı yok): uzun masa, kişi sayısı kadar sandalye,
// başta CEO koltuğu, duvarda toplantı TV'si. Yerler oda grubuna göre yereldir.
import * as THREE from 'three';
import { oturmaDuzeni, masaUzunlugu, MASA_EN } from './toplanti-mantik.js?v=3';

const MASA_Z = .5;     // masa odanın biraz önünde; arka duvarda TV
const OTURAK_Y = .56;  // kedinin oturduğu yükseklik

function tvCiz(ctx, satirlar) {
  const W = 512, H = 288;
  const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1f2b3a'); g.addColorStop(1, '#2e3f55');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#ff7a59'; ctx.fillRect(0, 0, W, 8);
  ctx.textBaseline = 'top';
  satirlar.forEach((s, i) => {
    const baslik = i === 0;
    ctx.font = baslik ? '700 34px "Space Grotesk", sans-serif' : '500 23px Inter, sans-serif';
    ctx.fillStyle = baslik ? '#fff4e8' : s.startsWith('•') ? '#f6c35c' : '#cfd8e3';
    let metin = String(s);
    while (metin.length > 1 && ctx.measureText(metin).width > W - 48) metin = metin.slice(0, -2) + '…';
    ctx.fillText(metin, 24, baslik ? 26 : 52 + i * 29);
  });
}

export function toplantiKur(g, oda, ajanIdleri, { kutu, aoLeke, tuvalDoku }) {
  const n = Math.max(1, ajanIdleri.length), L = masaUzunlugu(n);
  // halı + masa
  kutu(g, L + 3.4, .03, MASA_EN + 2.6, '#c9b8a6', 0, .125, MASA_Z, .015, false).receiveShadow = true;
  kutu(g, L + 3.0, .032, MASA_EN + 2.2, '#efe3d4', 0, .127, MASA_Z, .015, false);
  kutu(g, L + .5, .08, MASA_EN, '#8a6a4e', 0, .8, MASA_Z, .03);
  [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz]) => kutu(g, .12, .68, .12, '#6b4f39', sx * (L / 2 - .05), .44, MASA_Z + sz * (MASA_EN / 2 - .2), .02));
  aoLeke(g, L + 2.4, MASA_EN + 1.6, 0, MASA_Z, .118, .7);

  // sandalyeler: hiyerarşi sırası (ilk id CEO)
  const yerler = new Map();
  oturmaDuzeni(ajanIdleri).forEach((y, i) => {
    const z = MASA_Z + y.z, ceo = i === 0;
    const geri = ceo ? [-.32, 0] : [0, Math.sign(y.z) * .3];   // sırt masanın tersinde
    const renk = ceo ? '#c9566e' : '#6f86b8', sirt = ceo ? '#a8445a' : '#5f76a8';
    kutu(g, ceo ? .72 : .52, .1, ceo ? .72 : .52, renk, y.x, .46, z, .05);
    kutu(g, ceo ? .12 : .52, ceo ? 1.1 : .7, ceo ? .72 : .1, sirt, y.x + geri[0], ceo ? .98 : .8, z + geri[1], .04);
    kutu(g, .08, .42, .08, '#4a4038', y.x, .22, z, .02);
    yerler.set(y.id, { x: y.x, y: OTURAK_Y, z, ry: y.ry });
  });

  // duvarda toplantı TV'si (arka duvar)
  const tz = -oda.d / 2 + .32;
  kutu(g, 3.3, 1.95, .1, '#2b2724', 0, 2.05, tz, .03);
  const { ctx, t } = tuvalDoku(512, 288);
  tvCiz(ctx, ['Toplantı yok']); t.needsUpdate = true;
  const ekran = new THREE.Mesh(new THREE.PlaneGeometry(3.1, 1.75), new THREE.MeshBasicMaterial({ map: t, toneMapped: false }));
  ekran.position.set(0, 2.05, tz + .06); g.add(ekran);
  kutu(g, 2.2, .1, .3, '#8d8276', 0, .95, tz + .05, .03);               // TV altı raf
  kutu(g, .5, .32, .3, '#e9e2d8', .7, 1.16, tz + .05, .03);             // konferans hoparlörü
  kutu(g, .55, 1.6, .55, '#d8c9b1', oda.w / 2 - .9, .9, tz + .6, .2); // dolap
  let son = '';
  return {
    yerler,
    tv: { ciz(satirlar) { const k = satirlar.join('\n'); if (k === son) return; son = k; tvCiz(ctx, satirlar); t.needsUpdate = true; } },
  };
}
