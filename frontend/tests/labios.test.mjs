// Pruebas de la sincronía de labios por sílaba: node --test frontend/tests/labios.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const Labios = require('../public/js/labios.js');

const shapes = steps => steps.map(step => step.m);

test('cada sílaba toma la forma de su vocal', () => {
  assert.deepEqual(Labios.syllables('dolor').map(s => s.shape), ['O', 'O']);
  assert.deepEqual(Labios.syllables('barriga').map(s => s.shape), ['A', 'E', 'A']);
  // Vocales seguidas forman una sola sílaba: manda la A, luego la O/U, luego la E y la I.
  assert.deepEqual(Labios.syllables('buenos').map(s => s.shape), ['O', 'O']);
  assert.deepEqual(Labios.syllables('días').map(s => s.shape), ['A']);
});

test('M, B y P cierran la boca un instante antes de su vocal; F la deja pequeña', () => {
  const { steps } = Labios.plan('mapa');
  assert.deepEqual(shapes(steps), [null, 'A', null, 'A', null]);
  assert.deepEqual(shapes(Labios.plan('fe').steps), ['pequena', 'E', null]);
  // La vocal llega poco después del inicio de la sílaba.
  assert.ok(steps[1].u > 0 && steps[1].u < 0.5);
});

test('la puntuación cierra la boca y separa frases', () => {
  const result = Labios.plan('Hola, doctor.');
  assert.deepEqual(result.boundaries, [0, 2, 4]);
  assert.equal(result.total, 4);
  // Sin pausas (voz medida) el silencio real cierra la boca; con pausas lo hace la propia línea.
  const paused = Labios.plan('Hola, doctor.', { pauses: true });
  assert.equal(paused.steps.find(step => step.u === 2).m, null);
  assert.equal(paused.steps.find(step => step.u > 2).m, 'O');
});

test('con pausas, la puntuación ocupa tiempo; sin ellas no', () => {
  assert.equal(Labios.plan('Hola, doctor').total, 4);
  assert.ok(Labios.plan('Hola, doctor', { pauses: true }).total > 5);
});

test('los números también mueven la boca', () => {
  const { steps, total } = Labios.plan('Tiene 38 grados');
  assert.ok(total > 4);
  assert.ok(steps.some(step => step.m && step.u >= 2 && step.u < total - 2));
});

test('no repite formas seguidas', () => {
  const { steps } = Labios.plan('ojo loco');
  for (let i = 1; i < steps.length; i++) assert.notEqual(steps[i].m, steps[i - 1].m);
});

test('cada palabra guarda su posición en el texto para seguir a la voz del navegador', () => {
  const { words } = Labios.plan('Buenos días, doctor');
  assert.deepEqual(words.map(word => word.char), [0, 7, 13]);
  assert.deepEqual(words.map(word => word.u), [0, 2, 3]);
});

function recorder() {
  const seen = [];
  const lips = Labios.createLipSync({ setMouth: m => seen.push(m), msPerSyllable: 100 });
  return { lips, seen };
}

test('con voz medida, la boca avanza solo mientras suena y se cierra en el silencio', () => {
  const { lips, seen } = recorder();
  lips.start('mapa');
  lips.step(50, true);
  assert.equal(seen.at(-1), 'A');
  lips.step(200, false);
  assert.equal(seen.at(-1), null);
  assert.ok(Math.abs(lips.position() - 0.5) < 1e-9, 'el silencio no gasta sílabas');
});

test('una pausa larga vuelve a alinear la boca con el inicio de la frase siguiente', () => {
  const { lips } = recorder();
  lips.start('Hola que tal, buenos dias');
  // La voz real va más lenta que la estimación: al llegar a la coma, el reloj aún va por la sílaba 2,4.
  lips.step(240, true);
  lips.step(300, false);
  lips.step(16, true);
  assert.ok(lips.position() >= 4 && lips.position() < 4.3, `posición ${lips.position()}`);
});

test('una pausa corta (una consonante oclusiva) no realinea', () => {
  const { lips } = recorder();
  lips.start('Hola que tal, buenos dias');
  lips.step(240, true);
  lips.step(60, false);
  lips.step(16, true);
  assert.ok(lips.position() < 2.6);
});

test('sin medir la voz, el reloj avanza solo y sigue los avisos de palabra', () => {
  const { lips, seen } = recorder();
  lips.start('Hola, tal', { pauses: true });
  lips.step(50, null);
  assert.equal(seen.at(-1), 'O');
  lips.seekChar(6);
  lips.step(1, null);
  assert.equal(seen.at(-1), 'A');
});

test('al detenerse cierra la boca', () => {
  const { lips, seen } = recorder();
  lips.start('hola');
  lips.step(20, true);
  lips.stop();
  assert.equal(seen.at(-1), null);
  lips.step(20, true);
  assert.equal(seen.at(-1), null);
});
