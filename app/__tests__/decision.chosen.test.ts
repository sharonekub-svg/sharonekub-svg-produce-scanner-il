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
