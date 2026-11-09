// Ajan Ofisi · modele bağlı olmayan iki ofis kedisi:
// Bekçi: iki arka ayağı üstünde dikilir, ön patileri arkada birleşik şekilde odaların dışında devriye gezer.
// Temizlikçi: elinde kova ve süpürgeyle oda oda dolaşır; yerleri süpürür, masaları siler, duvardaki çerçeveleri siler.
// İkisi de hiçbir ajana/model çağrısına bağlı değildir; tıklanınca miyavlarlar.
import * as THREE from 'three';
import { createCat } from './kedi.js';

const MAT = new Map();
const mat = (renk, ek = {}) => {
  const k = renk + JSON.stringify(ek);
  if (!MAT.has(k)) MAT.set(k, new THREE.MeshStandardMaterial({ color:renk, roughness:.7, ...ek }));
  return MAT.get(k);
};
function parca(parent, geo, m, p = [0, 0, 0], s = [1, 1, 1]) {
  const x = new THREE.Mesh(geo, m); x.position.set(...p); x.scale.set(...s);
  x.castShadow = true; parent.add(x); return x;
}
const aciFark = (a, b) => Math.atan2(Math.sin(b - a), Math.cos(b - a));

const MAVI = '#2f6fb0', MAVI_KOYU = '#1f4d80', MAVI_ACIK = '#4f96d6';

/* ---------- aksesuarlar ---------- */
function sapka(bas) { // mavi güvenlik kasketi: baş düğümüne eklenir, kafayla birlikte hareket eder
  const g = new THREE.Group(); g.position.set(0, .1, .02); bas.add(g);
  parca(g, new THREE.SphereGeometry(.3, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2), mat(MAVI), [0, 0, 0], [1, .62, 1]);
  parca(g, new THREE.CylinderGeometry(.305, .305, .05, 24), mat(MAVI_KOYU), [0, .005, 0]);   // bant
  parca(g, new THREE.BoxGeometry(.36, .035, .2), mat(MAVI_KOYU), [0, -.005, .2]);            // siperlik
  parca(g, new THREE.SphereGeometry(.038, 10, 8), mat('#e2b54a', { metalness:.7, roughness:.3 }), [0, .13, .12]); // arma
  return g;
}
function yelek(govde) { // bekçi üniforması: önü açık mavi yelek + kemer + rozet
  const g = new THREE.Group(); govde.add(g);
  const kumas = mat(MAVI, { roughness:.85, side:THREE.DoubleSide });
  parca(g, new THREE.SphereGeometry(1.05, 30, 22, Math.PI / 2 + .62, Math.PI * 2 - 1.24, .55, 1.85), kumas, [0, 0, 0]);
  [-1, 1].forEach(s => parca(g, new THREE.TorusGeometry(.55, .055, 8, 20, Math.PI * .62), mat(MAVI_KOYU), [0, .35, 0]).rotation.set(.35, 0, s * .35));
  parca(g, new THREE.CylinderGeometry(1.02, 1.02, .14, 28, 1, true), mat(MAVI_KOYU, { roughness:.8, side:THREE.DoubleSide }), [0, -.42, 0]);
  parca(g, new THREE.BoxGeometry(.22, .16, .06), mat('#e2b54a', { metalness:.7, roughness:.3 }), [0, -.42, .98]);
  parca(g, new THREE.BoxGeometry(.2, .24, .05), mat('#e2b54a', { metalness:.7, roughness:.3 }), [-.34, .28, .92]);
  parca(g, new THREE.BoxGeometry(.11, .14, .035), mat('#c99a2e', { metalness:.7, roughness:.3 }), [-.34, .28, .95]);
  return g;
}
function onluk(govde) { // temizlikçi önlüğü: ön panel + boyun askısı + cep
  const g = new THREE.Group(); govde.add(g);
  const kumas = mat('#f6efe0', { roughness:.9, side:THREE.DoubleSide });
  parca(g, new THREE.SphereGeometry(1.04, 30, 22, Math.PI / 2 - .72, 1.44, .5, 1.9), kumas, [0, 0, 0]);
  parca(g, new THREE.TorusGeometry(.42, .035, 8, 20, Math.PI * .9), mat('#e6d9c2'), [0, .62, .35]).rotation.x = 1.15;
  parca(g, new THREE.BoxGeometry(.42, .34, .05), mat('#efe4cf'), [0, -.32, .9]);
  parca(g, new THREE.BoxGeometry(.42, .03, .06), mat('#d9cbb2'), [0, -.16, .92]);
  return g;
}
function fener() { // patide küçük el feneri
  const g = new THREE.Group();
  parca(g, new THREE.CylinderGeometry(.028, .034, .12, 12), mat('#3d4450', { metalness:.4, roughness:.4 }), [0, 0, 0]);
  const isik = new THREE.Mesh(new THREE.CircleGeometry(.032, 14), new THREE.MeshBasicMaterial({ color:'#fff2b0' }));
  isik.position.set(0, 0, .061); isik.rotation.x = -Math.PI / 2; g.add(isik);
  g.userData.isik = isik;
  return g;
}
function kova() { // yanında taşıdığı temizlik kovası
  const g = new THREE.Group();
  parca(g, new THREE.CylinderGeometry(.15, .11, .22, 20, 1, true), mat('#5fa8c9', { roughness:.5, side:THREE.DoubleSide }), [0, .11, 0]);
  parca(g, new THREE.CylinderGeometry(.12, .12, .015, 20), mat('#3f7f9c', { roughness:.5 }), [0, .02, 0]);
  parca(g, new THREE.TorusGeometry(.14, .012, 6, 20, Math.PI), mat('#c9d3d8', { metalness:.5, roughness:.35 }), [0, .21, 0]).rotation.z = Math.PI;
  parca(g, new THREE.SphereGeometry(.05, 10, 8), mat('#9fe0ff', { transparent:true, opacity:.6, roughness:.1 }), [.04, .19, 0], [1, .5, 1]);
  return g;
}
function supurge() { // ön patilerin önünde süpürge (sap + fırça)
  const g = new THREE.Group(); g.position.set(.15, .5, .22); g.rotation.x = -.18;
  parca(g, new THREE.CylinderGeometry(.012, .012, .52, 8), mat('#c9a06a', { roughness:.8 }), [0, -.26, 0]);
  parca(g, new THREE.BoxGeometry(.18, .05, .1), mat('#d9b98a', { roughness:.95 }), [0, -.53, .03]);
  parca(g, new THREE.BoxGeometry(.19, .06, .03), mat('#b07b43', { roughness:.95 }), [0, -.55, .09]);
  return g;
}
function bez() { // ön patilerde silme bezi
  const g = new THREE.Group(); g.position.set(0, .58, .34);
  parca(g, new THREE.BoxGeometry(.2, .02, .16), mat('#bfe6ff', { roughness:.95 }), [0, 0, 0]);
  parca(g, new THREE.BoxGeometry(.2, .05, .04), mat('#9fd4f0', { roughness:.95 }), [0, .02, -.06]);
  return g;
}
function tozBulutu() { // süpürme sırasında yükselen toz zerreleri
  const g = new THREE.Group();
  const m = new THREE.MeshBasicMaterial({ color:'#e9dcc8', transparent:true, opacity:0, depthWrite:false });
  const z = [];
  for (let i = 0; i < 6; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(.03, 6, 5), m.clone()); g.add(s); z.push(s); }
  g.userData.zerre = z;
  return g;
}

/* ---------- kurulum ---------- */
export function ofisKedileriKur({ scene, odalar, kutu, secilebilir }) {
  const liste = [], kayit = {};

  function ekle(tur, desen, ton, aksesuar, rota, y, hiz, hop) {
    const kedi = createCat({ desen, ton, aksesuar });
    const grup = kedi.group;
    grup.position.set(rota[0].x, y, rota[0].z);
    scene.add(grup);

    const bilesen = { tur, kedi, grup, rota, y, hiz, hop, idx:1, durum:'bekle',
      bekle:rota[0].bekle || 0, aksiyon:rota[0].aksiyon || null,
      bas:new THREE.Vector3(), son:new THREE.Vector3(), ry0:0, ry1:0, t0:0, sure:1, adimSay:2, tepkiT:0 };

    const hit = new THREE.Mesh(new THREE.BoxGeometry(.85, 1.25, .85), new THREE.MeshBasicMaterial());
    hit.visible = false; hit.position.y = .55; hit.userData.miyav = tur; grup.add(hit); secilebilir.push(hit);

    if (tur === 'bekci') {
      sapka(kedi.dugum.bas);
      yelek(kedi.dugum.govde);
      kedi.setPoz('ayakta'); // iki ayağı üstünde dik yürüyüş
      bilesen.fener = fener(); bilesen.fener.position.set(.17, .5, .42); grup.add(bilesen.fener);
    } else {
      onluk(kedi.dugum.govde);
      bilesen.supurge = supurge(); grup.add(bilesen.supurge);
      bilesen.kova = kova(); bilesen.kova.position.set(-.27, 0, .02); grup.add(bilesen.kova);
      bilesen.bez = bez(); bilesen.bez.visible = false; grup.add(bilesen.bez);
      bilesen.toz = tozBulutu(); grup.add(bilesen.toz);
    }
    liste.push(bilesen); kayit[tur] = bilesen;
    return bilesen;
  }

  // Bekçi: kaidenin dışında, odaların çevresinde tur atar (köşelerde etrafı kolaçan eder)
  const m = 2.0;
  const devriye = kutu ? [
    { x:kutu.x0 - m, z:kutu.z0 - m, bekle:2.6 },
    { x:kutu.x1 + m, z:kutu.z0 - m, bekle:2.6 },
    { x:kutu.x1 + m, z:kutu.z1 + m, bekle:2.6 },
    { x:kutu.x0 - m, z:kutu.z1 + m, bekle:2.6 },
  ] : [{ x:0, z:0, bekle:2 }];
  ekle('bekci', 'gri-beyaz', 0, { kalkan:true }, devriye, 0, 2.6, .04);

  // Temizlikçi: her odada sırayla yer süpürür, masayı ve duvar çerçevelerini siler
  const lzOf = o => o.cam ? -.6 : -o.d / 2 + 2.15;   // masanın oda içindeki z'si
  const temizRota = [];
  (odalar || []).filter(o => !o.toplanti && !o.eglence).forEach(o => {
    const onZ = o.cz + o.d / 2 - 1.3;                 // odanın önü (yer süpürme)
    const dx = Math.min(1.6, o.w * .18);
    temizRota.push({ x:o.cx - dx, z:onZ, bekle:1.6, ry:Math.PI, aksiyon:'yer' });
    temizRota.push({ x:o.cx + dx, z:onZ, bekle:3.2, ry:Math.PI, aksiyon:'yer' });
    // masa silme: masanın önünde durup yüzü masaya dönük (desk -z yönünde)
    temizRota.push({ x:o.cx + .9, z:o.cz + lzOf(o) + 1.25, bekle:3.4, ry:Math.PI, aksiyon:'masa' });
    // çerçeve silme: sol duvardaki çerçevenin önünde durup duvara dönük (cam odada duvar yok)
    if (!o.cam) temizRota.push({ x:o.cx - o.w / 2 + 1.15, z:o.cz - .2, bekle:3.4, ry:-Math.PI / 2, aksiyon:'cerceve' });
  });
  ekle('temizlikci', 'sarman', .5, {}, temizRota.length ? temizRota : [{ x:0, z:0, bekle:2 }], .13, 2.1, .12);

  function yolBasla(c, hedef, t) {
    c.bas.copy(c.grup.position);
    c.son.set(hedef.x, 0, hedef.z);
    c.ry0 = c.grup.rotation.y;
    c.ry1 = hedef.ry != null ? hedef.ry : Math.atan2(c.son.x - c.bas.x, c.son.z - c.bas.z);
    const mes = Math.hypot(c.son.x - c.bas.x, c.son.z - c.bas.z);
    c.sure = Math.max(1.6, mes / c.hiz) + .4;             // sabit yürüme hızı, uzun yolda acele yok
    c.adimSay = Math.max(2, Math.round(mes / 1.1));        // küçük adımlar: havada süzülmez
    c.t0 = t; c.durum = 'yol';
  }

  function bekciAnim(c, t) { // dikiliş + yürüyüş: arka ayaklar adım atar, gövde hafif salınır
    const d = c.kedi.dugum;
    const yuruyor = c.durum === 'yol';
    if (yuruyor) {
      const adim = Math.sin(t * (c.hiz * 2.4));
      d.ayakL.position.z += adim * .16;
      d.ayakR.position.z += -adim * .16;
      d.ayakL.position.y += Math.max(0, adim) * .05;
      d.ayakR.position.y += Math.max(0, -adim) * .05;
      d.govde.position.y += Math.abs(adim) * .02;
      d.bas.position.y += Math.abs(adim) * .02;
      d.bas.rotation.z += adim * .04;
    } else { // nöbette: hafif salınım, etrafı kolaçan
      d.govde.rotation.z += Math.sin(t * 1.4) * .02;
      d.bas.rotation.y += Math.sin(t * .7) * .08;
    }
  }

  function temizlikAnim(c, t) { // yer süpürme / masa silme / çerçeve silme
    const d = c.kedi.dugum;
    const beklemede = c.durum === 'bekle';
    const aks = c.aksiyon;
    const aktif = beklemede && aks;
    // süpürge yalnız yer süpürürken/beklerken görünür
    c.supurge.visible = aks !== 'masa' && aks !== 'cerceve';
    c.bez.visible = beklemede && (aks === 'masa' || aks === 'cerceve');
    if (aktif && aks === 'yer') {
      c.supurge.rotation.z = Math.sin(t * 8) * .38;
      c.supurge.rotation.x = -.18 + Math.sin(t * 8) * .08;
      d.onR.rotation.x += Math.sin(t * 8) * .18;
      d.onL.rotation.x += Math.sin(t * 8 + 1) * .12;
      // toz zerreleri yükselir
      const z = c.toz.userData.zerre;
      z.forEach((s, i) => {
        const p = (t * .6 + i / z.length) % 1;
        s.position.set(-.2 + Math.sin(i * 2.1) * .25, .12 + p * .5, .35 + p * .2);
        s.material.opacity = Math.sin(p * Math.PI) * .5;
        s.scale.setScalar(.6 + p * 1.2);
      });
    } else if (aktif && aks === 'masa') { // öne eğilip masa yüzeyini daire çizerek siler
      const a = t * 5;
      d.onR.position.x += Math.sin(a) * .07;
      d.onR.position.z += .18 + Math.cos(a) * .06;
      d.onR.rotation.x += -.9;
      d.onL.position.x -= Math.sin(a) * .04;
      d.onL.rotation.x += -.75;
      d.govde.rotation.x += .12;
      d.bas.rotation.x += .18;
    } else if (aktif && aks === 'cerceve') { // yukarı uzanıp çerçeveyi siler
      const a = t * 6;
      d.onR.position.y += .3;
      d.onR.position.z += .16;
      d.onR.rotation.x += -1.7 + Math.sin(a) * .22;
      d.onL.position.y += .22;
      d.onL.rotation.x += -1.5 - Math.sin(a) * .18;
      d.bas.rotation.x += -.3;
      d.govde.rotation.x += -.05;
    }
    if (c.kova) c.kova.rotation.z = Math.sin(t * 2.3) * .04;
  }

  function guncelle(dt, t) {
    for (const c of liste) {
      if (c.durum === 'yol') {
        const p = Math.min(1, (t - c.t0) / c.sure);
        const e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        c.grup.position.x = c.bas.x + (c.son.x - c.bas.x) * e;
        c.grup.position.z = c.bas.z + (c.son.z - c.bas.z) * e;
        c.grup.position.y = c.y + Math.abs(Math.sin(p * Math.PI * c.adimSay)) * c.hop;
        c.grup.rotation.y = c.ry0 + aciFark(c.ry0, c.ry1) * Math.min(1, p * 3);
        if (p >= 1) {
          c.durum = 'bekle';
          const st = c.rota[c.idx];
          c.bekle = st.bekle || 0;
          c.aksiyon = st.aksiyon || null;
          c.grup.rotation.y = st.ry != null ? st.ry : c.grup.rotation.y;
        }
      } else {
        c.bekle -= dt;
        c.grup.position.y = c.y;
        if (c.bekle <= 0) {
          c.idx = (c.idx + 1) % c.rota.length;
          c.aksiyon = null;
          yolBasla(c, c.rota[c.idx], t);
        }
      }

      // gövde durumu: yolda uyanık; temizlikçi iş yaparken çalışıyor, bekçi nöbette
      const kd = c.durum === 'yol' ? 'dinleniyor' : c.tur === 'temizlikci' ? 'calisiyor' : 'dinleniyor';
      c.kedi.setDurum(kd);
      c.kedi.update(dt);

      // poz uygulandıktan sonra kareye özel animasyonlar (bir sonraki update üzerine yazar)
      if (c.tur === 'bekci') bekciAnim(c, t);
      else temizlikAnim(c, t);

      if (c.fener) c.fener.userData.isik.material.color.setHSL(.13, 1, .6 + Math.sin(t * 5) * .08);

      // tıklama tepkisi: kısa zıplayış
      if (c.tepkiT) {
        const p = (t - c.tepkiT) / .5;
        if (p < 1) c.grup.position.y += Math.sin(p * Math.PI) * .3;
        else c.tepkiT = 0;
      }
    }
  }

  return {
    guncelle,
    tepki(tur, t) { const c = kayit[tur]; if (c) c.tepkiT = t; },
  };
}
