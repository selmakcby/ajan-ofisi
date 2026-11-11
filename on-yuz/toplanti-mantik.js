// Toplantı odası saf mantığı (three.js'siz; node test_toplanti.mjs ile test edilir).
export const ARALIK = 1.1;   // iki sandalye arası (masa boyunca)
export const MASA_EN = 1.6;  // masanın derinliği (z)

// n: CEO dahil kişi sayısı → masa uzunluğu (x)
export const masaUzunlugu = n => Math.max(3, Math.ceil((n - 1) / 2) * ARALIK + 1.2);

// ilk id CEO: masanın kısa başında. Diğerleri sırayla sağ ön, sol ön, sağda bir arkası…
// Dönüş oda-yerel: { id, x, z, ry }; ry = rotation.y (ileri yön (sin ry, cos ry)), herkes masaya bakar.
export function oturmaDuzeni(ajanIdleri) {
  const L = masaUzunlugu(ajanIdleri.length);
  return ajanIdleri.map((id, i) => {
    if (i === 0) return { id, x: -L / 2 - .9, z: 0, ry: Math.PI / 2 };
    const k = i - 1, yan = k % 2 ? -1 : 1, sira = Math.floor(k / 2);
    return { id, x: -L / 2 + .9 + sira * ARALIK, z: yan * (MASA_EN / 2 + .55), ry: yan > 0 ? Math.PI : 0 };
  });
}

export function toplantidaMi(aktif, simdiMs) {
  if (!aktif) return false;
  const bitis = Date.parse(aktif.bitis);
  return Number.isFinite(bitis) && simdiMs < bitis;
}

// sıradaki toplantı saati: bugün şimdiden sonraki ilk saat, yoksa yarının sabahı
function siradaki(saatler, simdi) {
  const s = { sabah: '09:00', aksam: '17:00', ...(saatler || {}) };
  const dk = simdi.getHours() * 60 + simdi.getMinutes();
  const dakika = t => { const [h, m] = String(t).split(':').map(Number); return h * 60 + m; };
  return [s.sabah, s.aksam].find(t => dakika(t) > dk) || s.sabah;
}

// TV ekranı: toplantıdaysa konu + projeler + özet (en çok 8 satır), değilse durum.
export function tvSatirlari(aktif, projeler, saatler, simdi) {
  if (aktif) {
    return [aktif.konu || 'Toplantı', ...projeler.map(p => `• ${p.baslik} %${p.ilerleme ?? 0}`),
      ...String(aktif.ozet || '').split('\n').map(x => x.trim()).filter(Boolean)].slice(0, 8);
  }
  if (!projeler.length) return ['Toplantı yok', 'Açık proje yok — toplantı yapılmaz'];
  return ['Toplantı yok', `${projeler.length} açık proje`, `Sıradaki: ${siradaki(saatler, simdi)}`];
}
