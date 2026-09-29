import { expect, test } from '@jest/globals';
import bundle from '../assets/model/bundle.json';
import { decide } from '../src/model/decision';

const b = bundle as any;
const flat = (n: number) => Array(n).fill(1 / n);

test('unsure result, then the user picks the fruit: assessed as that fruit and marked as chosen', () => {
  const probs: Record<string, number[]> = {
    produce: flat(b.outputs.produce.length),
    ripeness: flat(b.outputs.ripeness.length),
    freshness: b.outputs.freshness.map((l: string) => (l === 'fresh' ? 0.97 : 0.03 / (b.outputs.freshness.length - 1))),
    visual_spoilage: b.outputs.visual_spoilage.map((l: string) => (l === 'none' ? 0.97 : 0.03 / (b.outputs.visual_spoilage.length - 1))),
  };
  expect(decide(b, probs).status).toBe('unsure');
  const r = decide(b, probs, null, null, undefined, 'apple');
  expect(r.status).toBe('ok');
  expect(r.produce).toBe('apple');
  expect(r.chosen_by_user).toBe(true);
  expect(r.score).not.toBeNull();
});

test('a type without a verified head gets a general fresh-vs-spoiled score, marked as general', () => {
  const sup = { ...b.supported_heads, mango: ['freshness~general'] };
  const bb = { ...b, supported_heads: sup, thresholds: { ...b.thresholds, produce_min_prob: 0.5 } };
  const n = b.outputs.produce.length;
  const produce = Array(n).fill(0.001); produce[b.outputs.produce.indexOf('mango')] = 1 - 0.001 * (n - 1);
  const base = { produce, ripeness: flat(b.outputs.ripeness.length), freshness: flat(3), visual_spoilage: flat(3) };
  const bad = decide(bb, { ...base, freshness_general: Array(n).fill(0.9) } as any);
  expect(bad.status).toBe('ok');
  expect(bad.general_score).toBe(true);
  expect(bad.freshness?.label).toBe('not_fresh');
  expect(bad.score).toBe(4);
  const good = decide(bb, { ...base, freshness_general: Array(n).fill(0.05) } as any);
  expect(good.score).toBe(10);
  expect(good.general_score).toBe(true);
  expect(decide(bb, base as any).score).toBeNull(); // old server without the general head: no score, as before
});
