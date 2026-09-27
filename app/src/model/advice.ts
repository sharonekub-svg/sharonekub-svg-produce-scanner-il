// General produce-care guidance per type (ux-principles.md #7), from produce_care.json — evidence and
// sources in docs/research/food-quality.md. Generic advice, NOT a claim about the photographed item.
import CARE from './produce_care.json';

type Care = { fridge: string; chill_below_c: number | null; ethylene: { producer: boolean; sensitive: boolean }; tip_he: string };
const PRODUCE_CARE = CARE.produce as Record<string, Care>;
export const CARE_GENERAL_HE = CARE.general_he;

/** Storage tip + the ethylene rule that applies to this type (one short paragraph). */
export const STORAGE_TIP_HE: Record<string, string> = Object.fromEntries(
  Object.entries(PRODUCE_CARE).map(([k, c]) => {
    const eth = c.ethylene.producer ? CARE.general_he.ethylene_producer : c.ethylene.sensitive ? CARE.general_he.ethylene_sensitive : '';
    return [k, eth ? `${c.tip_he} ${eth}` : c.tip_he];
  }),
);

/** Confidence in words first, calibrated number second (ux-principles.md #5). */
export function confidenceWord(p: number | null | undefined): string {
  if (p == null) return '';
  if (p >= 0.85) return 'ביטחון גבוה';
  if (p >= 0.7) return 'ביטחון בינוני';
  return 'ביטחון נמוך';
}

/** Combine two photos of the same fruit: normalised geometric mean of the per-head
 *  probabilities (product of experts). Used only for the optional "another angle" retry. */
export function combineProbs(a: number[], b: number[]): number[] {
  const g = a.map((v, i) => Math.sqrt(Math.max(v, 1e-12) * Math.max(b[i], 1e-12)));
  const s = g.reduce((x, y) => x + y, 0);
  return g.map((v) => v / s);
}
