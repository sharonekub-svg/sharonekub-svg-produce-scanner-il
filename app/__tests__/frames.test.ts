// "Short video" frames: combining several analysed photos into one result (engine.combineFrames).
import { expect, it, jest } from '@jest/globals';

jest.mock('expo-image-manipulator', () => ({ ImageManipulator: {}, SaveFormat: {} }));
jest.mock('expo-constants', () => ({ expoConfig: { extra: {} } }));

import bundleJson from '../assets/model/bundle.json';
import { combineFrames } from '../src/model/engine';

const b = bundleJson as any;
const OK: any = { ok: true, reason: null, mean_luma: 120, laplacian_var: 500, clipped_frac: 0 };
const BLUR = { ...OK, ok: false, reason: 'blurry' };
const banana = b.outputs.produce.indexOf('banana');
const frame = (q = OK, strength = 12) => ({
  quality: q,
  logits: Object.fromEntries(Object.entries(b.outputs).map(([h, labels]: [string, any]) =>
    [h, labels.map((_: string, i: number) => (h === 'produce' && i === banana ? strength : 0))])),
} as any);

it('combines every usable frame', () => {
  const r = combineFrames([frame(), frame(), frame(), frame()]);
  expect(r.angles).toBe(4);
  expect(r.result.produce).toBe('banana');
  expect(r.result.status).not.toBe('retake');
});

it('a blurry frame never replaces a usable result', () => {
  const r = combineFrames([frame(), frame(BLUR), frame()]);
  expect(r.result.status).not.toBe('retake');
  expect(r.result.produce).toBe('banana');
});

it('a blurry first frame is skipped', () => {
  const r = combineFrames([frame(BLUR), frame()]);
  expect(r.result.status).not.toBe('retake');
  expect(r.angles).toBe(1);
});

it('asks for a retake only when every frame is unusable', () => {
  expect(combineFrames([frame(BLUR), frame(BLUR)]).result.status).toBe('retake');
});
