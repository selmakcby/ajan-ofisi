// Eğlence odası mantığı self-check: node test_eglence.mjs → OK (python test_ofis.py bunu da koşturur)
import assert from 'node:assert/strict';
import { geceMi, saatAl, yerAta, balonMetni, MIYAV, sonrakiBalon, yatakDizilimi, bilardoAdim, bilardoDurdu, dovusYeni, dovusAdim } from './on-yuz/eglence-mantik.js';

// gece 20:00–07:59, gündüz 08:00–19:59
assert.equal(geceMi(20), true); assert.equal(geceMi(23), true); assert.equal(geceMi(0), true); assert.equal(geceMi(7), true);
assert.equal(geceMi(8), false); assert.equal(geceMi(12), false); assert.equal(geceMi(19), false);

// ?saat=23 elle saat (deneme); geçersizse gerçek saat
assert.equal(saatAl('?saat=23', new Date(2026, 10, 6, 10)), 23);
assert.equal(saatAl('?saat=7&demo=1', new Date(2026, 10, 6, 10)), 7);
assert.equal(saatAl('?saat=25', new Date(2026, 10, 6, 10)), 10);
assert.equal(saatAl('?saat=abc', new Date(2026, 10, 6, 15)), 15);
assert.equal(saatAl('', new Date(2026, 10, 6, 21)), 21);

// yer ataması: her kedi farklı yer, aynı tur → aynı sonuç, yer yetmezse -1 yok (taşma yerleri dahil)
const idler = ['a', 'b', 'c', 'd', 'e', 'f'];
const y1 = yerAta(idler, 10, 5);
assert.equal(y1.size, 6);
assert.equal(new Set(y1.values()).size, 6, 'iki kedi aynı yere düştü');
assert.ok([...y1.values()].every(i => i >= 0 && i < 10));
assert.deepEqual([...yerAta(idler, 10, 5)], [...y1], 'aynı tur aynı yerleri vermeli');
assert.notDeepEqual([...yerAta(idler, 10, 6).values()], [...y1.values()], 'tur değişince yerler değişmeli');
// bir kedi işe gidince diğerlerinin çoğu yerinde kalır (herkes zıplamasın)
const y2 = yerAta(idler.filter(i => i !== 'c'), 10, 5);
const kalan = idler.filter(i => i !== 'c' && y2.get(i) === y1.get(i)).length;
assert.ok(kalan >= 4, 'bir kedi ayrılınca ' + (5 - kalan) + ' kedi yer değiştirdi');
// yer sayısından fazla kedi: her biri yine farklı bir yere (çağıran taşma yerleri ekler)
assert.throws(() => yerAta(['a', 'b', 'c'], 2, 1), /yer/);

// balonlar: yalnız "miyav" ailesi, token yok
assert.ok(MIYAV.length >= 4 && MIYAV.every(m => /^(m|M)/.test(m)));
assert.equal(balonMetni(0), MIYAV[0]);
assert.equal(balonMetni(.9999), MIYAV[MIYAV.length - 1]);
const s = sonrakiBalon(.5);
assert.ok(s >= 5 && s <= 14, 'balon aralığı ' + s);

// her kediye ayrı yatak: dar odada iki sıra, yataklar çakışmaz
const tek = yatakDizilimi(1, 10.4);
assert.deepEqual(tek, [{ dx:0, dz:0 }]);
const dort = yatakDizilimi(4, 10.4);                 // taban oda: sırada en çok 3 yatak
assert.equal(dort.length, 4);
assert.equal(new Set(dort.map(p => p.dz)).size, 2, 'dar odada iki sıra olmalı');
const genis = yatakDizilimi(4, 15.2);
assert.equal(new Set(genis.map(p => p.dz)).size, 1, 'geniş odada tek sıra');
for (const liste of [dort, genis, yatakDizilimi(7, 15.2)]) {
  for (let i = 0; i < liste.length; i++) for (let j = i + 1; j < liste.length; j++) {
    const a = liste[i], b = liste[j];
    assert.ok(Math.abs(a.dx - b.dx) >= 1.15 || Math.abs(a.dz - b.dz) >= 1.1, 'yataklar çakıştı');
  }
}

// bilardo: sürtünme yavaşlatır, bant sektirir, toplar birbirinin içinden geçmez
const masa = { w:2.5, d:1.3, r:.06 };
let toplar = [{ x:0, z:0, vx:2, vz:0 }];
for (let i = 0; i < 10; i++) toplar = bilardoAdim(toplar, 1 / 30, masa); // banda varmadan
assert.ok(toplar[0].vx < 2 && toplar[0].vx > 0, 'sürtünme');
toplar = [{ x:1.15, z:0, vx:3, vz:0 }];
for (let i = 0; i < 10; i++) toplar = bilardoAdim(toplar, 1 / 60, masa);
assert.ok(toplar[0].vx < 0 && toplar[0].x <= masa.w / 2 - masa.r + 1e-9, 'banttan sekmedi');
toplar = [{ x:-.3, z:0, vx:2, vz:0 }, { x:.3, z:0, vx:0, vz:0 }];
for (let i = 0; i < 40; i++) toplar = bilardoAdim(toplar, 1 / 60, masa);
assert.ok(toplar[1].vx > .5, 'çarpışma hızı aktarmadı');
assert.ok(Math.hypot(toplar[0].x - toplar[1].x, toplar[0].z - toplar[1].z) >= 2 * masa.r - 1e-6, 'toplar iç içe');
for (let i = 0; i < 2000; i++) toplar = bilardoAdim(toplar, 1 / 60, masa);
assert.ok(bilardoDurdu(toplar), 'toplar sonunda durmalı');

// dövüş oyunu: canlar azalır, biri bitince K.O. ve yeni raunt
let r = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
let d = dovusYeni(r);
assert.equal(d.can[0], 100); assert.equal(d.can[1], 100);
let ko = false, yeni = false;
for (let i = 0; i < 4000 && !yeni; i++) {
  const once = d;
  d = dovusAdim(d, 1 / 12, r);
  if (d.ko) ko = true;
  if (ko && d !== once && d.raunt > once.raunt) yeni = true;
}
assert.ok(ko && yeni, 'raunt bitmedi');

console.log('OK');
