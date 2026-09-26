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
  unknown: { dot: '⚪', bg: '#EEEEEE' },
};

/** Calibrated probability rounded to 5% (spec: no false precision). */
export const pct = (p: number | null | undefined) => (p == null ? '' : `${Math.round((p * 100) / 5) * 5}%`);
