// Chip colour per label (docs/product-spec.md). Colour is never the only carrier: text is always shown.
export const CHIP: Record<string, { dot: string; bg: string }> = {
  unripe: { dot: '🟡', bg: '#FFF4CC' },
  partially_ripe: { dot: '🟡', bg: '#FFF4CC' },
  ripe: { dot: '🟢', bg: '#DFF3E4' },
  overripe: { dot: '🟠', bg: '#FFE6CC' },
  fresh: { dot: '🟢', bg: '#DFF3E4' },
  declining: { dot: '🟠', bg: '#FFE6CC' },
  spoiled: { dot: '🔴', bg: '#FADBD8' },
  none: { dot: '🟢', bg: '#DFF3E4' },
  mild: { dot: '🟠', bg: '#FFE6CC' },
  severe: { dot: '🔴', bg: '#FADBD8' },
  not_fresh: { dot: '🔴', bg: '#FADBD8' },
  defects: { dot: '🔴', bg: '#FADBD8' },
  good: { dot: '🟢', bg: '#DFF3E4' },
  bad: { dot: '🔴', bg: '#FADBD8' },
  early: { dot: '🟠', bg: '#FFE6CC' },
  rotten: { dot: '🔴', bg: '#FADBD8' },
  unknown: { dot: '⚪', bg: '#EEEEEE' },
};

/** Calibrated probability rounded to 5% (spec: no false precision). */
export const pct = (p: number | null | undefined) => (p == null ? '' : `${Math.round((p * 100) / 5) * 5}%`);

/** 0-100 score shown in steps of 5 (same rule: the model is not that precise). */
export const step5 = (x: number) => Math.round(x / 5) * 5;

/** The score every screen shows, 0-100: the condition-based overall, else the 1-10 score x 10 (general model). */
export const score100 = (r: { overall?: number | null; score?: number | null }) =>
  (r.overall != null ? step5(r.overall) : r.score != null ? r.score * 10 : null);
