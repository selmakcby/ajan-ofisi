// Eğlence odası mantığı self-check: node test_eglence.mjs → OK (python test_ofis.py bunu da koşturur)
import assert from 'node:assert/strict';
import { geceMi, saatAl, yerAta, balonMetni, MIYAV, sonrakiBalon } from './on-yuz/eglence-mantik.js';

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

console.log('OK');
