import { expect, test } from '@jest/globals';
import bundle from '../assets/model/bundle.json';
import { STORAGE_TIP_HE, combineProbs, confidenceWord } from '../src/model/advice';

test('every target produce in the shipped bundle has a storage tip', () => {
  const meta = (bundle as any).produce_meta as Record<string, { is_negative_class?: boolean }>;
  const targets = Object.keys(meta).filter((k) => !meta[k].is_negative_class);
  expect(targets.filter((t) => !STORAGE_TIP_HE[t])).toEqual([]);
});

test('storage tips never make safety claims', () => {
  for (const tip of Object.values(STORAGE_TIP_HE)) expect(tip).not.toMatch(/בטוח/);
});

test('confidence words', () => {
  expect(confidenceWord(0.93)).toBe('ביטחון גבוה');
  expect(confidenceWord(0.75)).toBe('ביטחון בינוני');
  expect(confidenceWord(0.4)).toBe('ביטחון נמוך');
  expect(confidenceWord(null)).toBe('');
});

test('combining two angles: agreement sharpens, disagreement stays uncertain', () => {
  const a = [0.6, 0.3, 0.1];
  const agree = combineProbs(a, [0.7, 0.2, 0.1]);
  expect(agree.reduce((x, y) => x + y, 0)).toBeCloseTo(1, 12);
  expect(agree[0]).toBeGreaterThan(0.6);
  const disagree = combineProbs(a, [0.1, 0.8, 0.1]);
  expect(Math.max(...disagree)).toBeLessThan(0.7);
});
