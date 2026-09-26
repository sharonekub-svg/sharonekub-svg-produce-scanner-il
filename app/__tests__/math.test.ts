import { expect, test } from '@jest/globals';
import { argmax, energy, softmax } from '../src/model/math';

test('softmax sums to one and respects temperature', () => {
  const p = softmax([1, 2, 3]);
  expect(p.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12);
  expect(softmax([1, 2, 3], 10)[2]).toBeLessThan(p[2]);
});

test('energy equals logsumexp and is shift-stable', () => {
  expect(energy([0, 0])).toBeCloseTo(Math.log(2), 12);
  expect(energy([1000, 1000])).toBeCloseTo(1000 + Math.log(2), 9);
});

test('argmax', () => expect(argmax([0.1, 0.7, 0.2])).toBe(1));
