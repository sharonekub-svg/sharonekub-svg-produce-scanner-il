// Contract with exports/<version>/bundle.json (ml/export/export.py). The app depends on nothing else.

export type Head = 'produce' | 'ripeness' | 'freshness' | 'visual_spoilage';
export const HEADS: Head[] = ['produce', 'ripeness', 'freshness', 'visual_spoilage'];

export interface ProduceMeta {
  category: string;
  he: string;
  emoji: string;
  priority: string;
  is_negative_class?: boolean;
  ripeness_visual?: string;
  ripeness_note_he?: string;
}

export interface Thresholds {
  produce_min_prob: number;
  produce_min_margin: number;
  ood_min_energy: number | null;
  head_min_prob: number;
  spoiled_alert_prob: number;
  /** Per type: condition confidence below which the score is capped and a better photo requested (fitted on val). */
  condition_abstain?: Record<string, number>;
  /** Highest P(good condition) the score may use: measured reliability on photo sources the model never saw. */
  condition_max_p?: number;
  /** Same ceiling for the graded (good / early / rotten) condition types. */
  condition_max_p_graded?: number;
  /** Per-type override (types whose P(good) comes from the binary head but whose "how bad" is transferred). */
  condition_max_p_type?: Record<string, number>;
}

export interface Bundle {
  bundle_version: number;
  model_id: string;
  input: { size: number; mean: number[]; std: number[]; resize: string; resize_ratio: number };
  outputs: Record<Head, string[]>;
  temperatures: Partial<Record<Head | 'condition', number>>;
  thresholds: Thresholds;
  supported_heads: Record<string, string[]>;
  produce_meta: Record<string, ProduceMeta>;
  label_he: Record<Exclude<Head, 'produce'>, Record<string, string>>;
  training_datasets?: string[];
}

export type Logits = Record<Head, number[]>;
/** freshness_general / condition: one probability per produce output (P(spoiled) / P(good condition)). */
export type Probs = Partial<Record<Head, number[]>> & { freshness_general?: number[]; condition?: number[]; condition_rot?: number[] };

export interface QualityStats {
  ok: boolean;
  reason: 'too_dark' | 'too_bright' | 'overexposed' | 'blurry' | null;
  mean_luma?: number;
  laplacian_var?: number;
  clipped_frac?: number;
}

export interface HeadResult {
  label: string | null;
  label_he: string | null;
  confidence: number | null;
  available: boolean;
}

// Mirrors ml.inference.decision.ScanResult.to_dict() field-for-field (snake_case on purpose:
// parity tests compare against JSON produced by Python).
export interface ScanResult {
  status: 'ok' | 'retake' | 'unsure' | 'not_produce';
  message_he: string | null;
  produce: string | null;
  produce_he: string | null;
  emoji: string | null;
  produce_confidence: number | null;
  ripeness: HeadResult | null;
  freshness: HeadResult | null;
  visual_spoilage: HeadResult | null;
  recommendation: string | null;
  recommendation_he: string | null;
  explanation_he: string[];
  score: number | null;
  score_reason_he: string | null;
  /** True when the user picked the fruit after an unsure result (identification not from the model). */
  chosen_by_user?: boolean;
  /** Score from the general fresh-vs-spoiled model (this type has no verified per-fruit head). */
  general_score?: boolean;
  disclaimer_he: string;
  /** Condition head v2 (docs/quality-scoring.md): calibrated good-vs-bad condition, only for types that have it. */
  condition?: HeadResult | null;
  /** 0-100: min(condition, ripeness), capped at 60 when the condition is unclear. */
  overall?: number | null;
  condition_score?: number | null;
  ripeness_score?: number | null;
  condition_confidence?: number | null;
  /** Below the type's abstain confidence: conservative score + ask for a better photo. */
  low_confidence?: boolean;
  /** Only what a verified head reported (no invented "small brown spot"). */
  issues_he?: string[];
}
