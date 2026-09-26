// Numerics mirrored from ml/evaluation/calibration.py and ml/evaluation/ood.py.

export function softmax(logits: number[], temperature = 1): number[] {
  const z = logits.map((v) => v / temperature);
  const m = Math.max(...z);
  const e = z.map((v) => Math.exp(v - m));
  const s = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / s);
}

/** Negative free energy: T * logsumexp(logits / T). Higher = more in-distribution. */
export function energy(logits: number[], temperature = 1): number {
  const z = logits.map((v) => v / temperature);
  const m = Math.max(...z);
  return temperature * (m + Math.log(z.reduce((a, v) => a + Math.exp(v - m), 0)));
}

export function argmax(v: number[]): number {
  let best = 0;
  for (let i = 1; i < v.length; i++) if (v[i] > v[best]) best = i;
  return best;
}
