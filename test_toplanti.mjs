// Toplantı odası mantığı self-check: node test_toplanti.mjs → OK (python test_ofis.py bunu da koşturur)
import assert from 'node:assert/strict';
import { oturmaDuzeni, masaUzunlugu, toplantidaMi, tvSatirlari, MASA_EN } from './on-yuz/toplanti-mantik.js';

// CEO başta, diğerleri masanın iki yanında; n=1…12 için çakışma yok
for (let n = 1; n <= 12; n++) {
  const ids = ['ceo', ...Array.from({ length: n - 1 }, (_, i) => 'a' + i)], d = oturmaDuzeni(ids), L = masaUzunlugu(n);
  assert.equal(d.length, n); assert.equal(d[0].id, 'ceo'); assert.ok(d[0].x < -L / 2, 'CEO başta');
  const anah = new Set(d.map(y => y.x.toFixed(2) + ',' + y.z.toFixed(2))); assert.equal(anah.size, n, 'çakışma n=' + n);
  d.slice(1).forEach(y => { assert.ok(Math.abs(y.z) > MASA_EN / 2 && y.x > -L / 2 && y.x < L / 2, 'masanın yanında'); });
}
// hiyerarşi: 1. sağ ön, 2. sol ön, 3. sağda bir arkası
const d = oturmaDuzeni(['ceo', 'a', 'b', 'c']);
assert.ok(d[1].z > 0 && d[2].z < 0 && d[1].x === d[2].x && d[3].x > d[1].x, 'sağ, sol, sonra bir arka');
// herkes masaya bakar: CEO +x yönüne, yandakiler masanın ortasına (z=0) doğru
const bak = y => [Math.sin(y.ry), Math.cos(y.ry)];
assert.ok(bak(d[0])[0] > .9, 'CEO masaya bakar');
assert.ok(bak(d[1])[1] < -.9 && bak(d[2])[1] > .9, 'yandakiler masaya bakar');

const aktif = { bitis: '2026-11-06T09:05:00+03:00', konu: 'Bugün ne yapacağız?', ozet: 'a\nb' };
assert.equal(toplantidaMi(aktif, Date.parse('2026-11-06T09:04:00+03:00')), true);
assert.equal(toplantidaMi(aktif, Date.parse('2026-11-06T09:06:00+03:00')), false);
assert.equal(toplantidaMi(null, 0), false);
assert.equal(toplantidaMi({ bitis: 'bozuk' }, 0), false);

const saat = { sabah: '09:00', aksam: '17:00' };
assert.deepEqual(tvSatirlari(aktif, [{ baslik: 'Site', ilerleme: 40 }], saat, new Date(2026, 10, 6, 9, 2)), ['Bugün ne yapacağız?', '• Site %40', 'a', 'b']);
assert.deepEqual(tvSatirlari(null, [], saat, new Date(2026, 10, 6, 10)), ['Toplantı yok', 'Açık proje yok — toplantı yapılmaz']);
assert.deepEqual(tvSatirlari(null, [{}, {}], saat, new Date(2026, 10, 6, 10)), ['Toplantı yok', '2 açık proje', 'Sıradaki: 17:00']);
assert.deepEqual(tvSatirlari(null, [{}], saat, new Date(2026, 10, 6, 18)), ['Toplantı yok', '1 açık proje', 'Sıradaki: 09:00']);
assert.deepEqual(tvSatirlari(null, [{}], null, new Date(2026, 10, 6, 8)), ['Toplantı yok', '1 açık proje', 'Sıradaki: 09:00']);
const uzun = tvSatirlari({ ...aktif, ozet: Array.from({ length: 20 }, (_, i) => 's' + i).join('\n') }, [], saat, new Date());
assert.equal(uzun.length, 8);
console.log('OK');
