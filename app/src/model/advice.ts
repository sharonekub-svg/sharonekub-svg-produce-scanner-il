// General produce-care guidance per type (ux-principles.md #7), from produce_care.json — evidence and
// sources in docs/research/food-quality.md. Generic advice, NOT a claim about the photographed item.
import CARE from './produce_care.json';

type Care = { fridge: string; chill_below_c: number | null; ethylene: { producer: boolean; sensitive: boolean }; tip_he: string; touch_he: string;
              stage_use_he?: Record<string, string> };
const PRODUCE_CARE = CARE.produce as Record<string, Care>;
export const CARE_GENERAL_HE = CARE.general_he;

/** Storage tip + the ethylene rule that applies to this type (one short paragraph). */
export const STORAGE_TIP_HE: Record<string, string> = Object.fromEntries(
  Object.entries(PRODUCE_CARE).map(([k, c]) => {
    const eth = c.ethylene.producer ? CARE.general_he.ethylene_producer : c.ethylene.sensitive ? CARE.general_he.ethylene_sensitive : '';
    return [k, eth ? `${c.tip_he} ${eth}` : c.tip_he];
  }),
);

/** General hand check per type ("texture": a photo can't measure it). Same text as the server's touch_tip_he. */
export const TOUCH_HE: Record<string, string> = Object.fromEntries(Object.entries(PRODUCE_CARE).map(([k, c]) => [k, c.touch_he]));

/** What to do with the fruit at its ripeness stage (e.g. green mango -> salad, very ripe banana -> baking). */
export function stageUseHe(produce: string | null, stage: string | null | undefined): string | null {
  if (!produce || !stage) return null;
  return PRODUCE_CARE[produce]?.stage_use_he?.[stage] ?? null;
}

type HeadLike = { label: string | null; available: boolean } | null | undefined;
/** Skin appearance in words, derived only from the freshness/spoilage heads (same rules as server/app.py surface_he). */
export function surfaceHe(freshness: HeadLike, spoilage: HeadLike): string | null {
  const sp = spoilage?.available ? spoilage.label : null;
  const fr = freshness?.available ? freshness.label : null;
  if (sp == null && fr == null) return null;
  if (sp === 'severe' || fr === 'spoiled') return 'סימני ריקבון נראים בקליפה';
  if (sp === 'defects') return 'פגמים נראים בקליפה';
  if (sp === 'mild' || fr === 'declining' || fr === 'not_fresh') return 'כתמים קלים או סימני התייבשות';
  if ((sp == null || sp === 'none') && (fr == null || fr === 'fresh')) return 'קליפה נקייה, בלי פגמים נראים';
  return null;
}

/** Score in one word + tone (same bands as the web app). */
export function verdictHe(score: number): string {
  return score >= 9 ? 'מצוין' : score >= 7 ? 'טוב' : score >= 5 ? 'סביר' : score >= 3 ? 'חלש' : 'לא מומלץ';
}

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

/** Quality heads below this confidence -> suggest a second photo from another side (both photos are combined). */
export const ANGLE_CONFIDENCE = 0.75;
type ConfHead = { label: string | null; available: boolean; confidence?: number | null } | null | undefined;
type AngleResult = { status: string; ripeness?: ConfHead; freshness?: ConfHead; visual_spoilage?: ConfHead };
/** True when the fruit is identified but its condition is uncertain and one more angle could settle it. */
export function needsAnotherAngle(r: AngleResult, angles: number): boolean {
  if (r.status !== 'ok' || angles >= 2) return false;
  const confs = [r.ripeness, r.freshness, r.visual_spoilage]
    .filter((h) => h?.available && h.confidence != null).map((h) => h!.confidence as number);
  return confs.length > 0 && Math.min(...confs) < ANGLE_CONFIDENCE;
}
/** Where to point the camera next: under the punnet for berries, the other side for everything else. */
export function angleHintHe(produce: string | null): string {
  return produce && ['strawberry', 'grape'].includes(produce) ? 'הפכו את הקופסה וצלמו מלמטה – שם מסתתרים פירות פגועים'
    : 'סובבו וצלמו את הצד השני, או מלמטה';
}
