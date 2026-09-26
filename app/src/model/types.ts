// Contract with exports/<version>/bundle.json (ml/export/export.py). The app depends on nothing else.

export type Head = 'produce' | 'ripeness' | 'freshness' | 'visual_spoilage';
export const HEADS: Head[] = ['produce', 'ripeness', 'freshness', 'visual_spoilage'];

export interface ProduceMeta {
  category: string;
  he: string;
  emoji: string;
  priority: string;
  is_negative_class?: boolean;
}

export interface Thresholds {
  produce_min_prob: number;
  produce_min_margin: number;
  ood_min_energy: number | null;
  head_min_prob: number;
  spoiled_alert_prob: number;
}

export interface Bundle {
  bundle_version: number;
  model_id: string;
  input: { size: number; mean: number[]; std: number[]; resize: string; resize_ratio: number };
  outputs: Record<Head, string[]>;
  temperatures: Partial<Record<Head, number>>;
  thresholds: Thresholds;
  supported_heads: Record<string, string[]>;
  produce_meta: Record<string, ProduceMeta>;
  label_he: Record<Exclude<Head, 'produce'>, Record<string, string>>;
  training_datasets?: string[];
}

export type Logits = Record<Head, number[]>;
export type Probs = Partial<Record<Head, number[]>>;

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
  disclaimer_he: string;
}
