import { describe, expect, it } from '@jest/globals';
// Parity: the TypeScript port of decide() must reproduce ml/inference/decision.py exactly.
// Regenerate fixtures with `python scripts/gen_decision_fixtures.py` after changing either side.
import fixtures from './fixtures/decision_cases.json';
import { decide } from '../src/model/decision';
import type { Bundle, Probs } from '../src/model/types';

const bundle = fixtures.bundle as unknown as Bundle;

describe('decide() parity with Python', () => {
  it('has enough cases covering every status', () => {
    const statuses = new Set(fixtures.cases.map((c) => c.expected.status));
    expect(fixtures.cases.length).toBeGreaterThanOrEqual(500);
    expect([...statuses].sort()).toEqual(['not_produce', 'ok', 'retake', 'unsure']);
  });

  it.each(fixtures.cases.map((c, i) => [i, c] as const))('case %i', (_i: number, c: (typeof fixtures.cases)[number]) => {
    const got = decide(bundle, c.probs as Probs, c.quality_reason, c.energy);
    expect(got).toEqual(c.expected);
  });
});
