// Ajan Ofisi · panel avatarları: her ajanın kendi 3D kedisi, meme pozunda, kafa-omuz portre (256×256)
// Açılışta bir kez ayrı küçük bir renderer'da üretilir; Map<ajanId, dataURL> döner.
import * as THREE from 'three';
import { createCat } from './kedi.js?v=3';
import { memeBul } from './meme.js?v=3';

const BOYUT = 256;

export function portreleriUret(ajanlar, { desen, aksesuar, renk }) {
  const sonuc = new Map();
  let r;
  try {
    r = new THREE.WebGLRenderer({ antialias:true, preserveDrawingBuffer:true });
  } catch { return sonuc; } // WebGL yoksa baş harf rozetleri kalır
  r.setPixelRatio(1); r.setSize(BOYUT, BOYUT, false);
  r.toneMapping = THREE.ACESFilmicToneMapping; r.outputColorSpace = THREE.SRGBColorSpace;
  const sahne = new THREE.Scene();
  sahne.add(new THREE.HemisphereLight('#fff6ea', '#cdb99d', 1.5));
  const gunes = new THREE.DirectionalLight('#ffe2bf', 2.4); gunes.position.set(-2, 3, 4); sahne.add(gunes);
  const kamera = new THREE.PerspectiveCamera(28, 1, .05, 20);
  const bas = new THREE.Vector3(), ileri = new THREE.Vector3(), q = new THREE.Quaternion();

  ajanlar.forEach(a => {
    const kedi = createCat({ desen:desen(a), aksesuar:aksesuar(a) });
    sahne.add(kedi.group);
    const m = memeBul(a.id, a.oda);
    if (m) {
      // takılan aksesuarlar (kapüşon, ahize) kediye bağlanır; dekor grubu sahneye eklenmez
      m.sahne?.(new THREE.Group(), {}, kedi);
      kedi.setMeme(m.kedi, { aninda:true });
      if (m.kedi.kontur) kedi.setKontur(m.kedi.kontur);
    } else kedi.setDurum('calisiyor');
    kedi.update(1 / 60);
    kedi.group.updateMatrixWorld(true);
    kedi.dugum.bas.getWorldPosition(bas);
    kedi.dugum.bas.getWorldQuaternion(q);
    ileri.set(0, 0, 1).applyQuaternion(q).setY(0).normalize();
    if (ileri.lengthSq() < .01) ileri.set(0, 0, 1);
    kamera.position.copy(bas).addScaledVector(ileri, 1.65).add(new THREE.Vector3(0, .1, 0));
    kamera.lookAt(bas.x, bas.y - .2, bas.z);
    sahne.background = new THREE.Color(renk(a));
    r.render(sahne, kamera);
    sonuc.set(a.id, r.domElement.toDataURL('image/jpeg', .9));
    sahne.remove(kedi.group);
  });
  r.dispose(); r.forceContextLoss();
  return sonuc;
}
