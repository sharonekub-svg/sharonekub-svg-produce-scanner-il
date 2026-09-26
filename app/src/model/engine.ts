// Inference engine selection. The UI only calls `scan(uri)`; swapping the model or the
// inference location never touches UI code.
//   native : on-device Core ML via modules/produce-model (preferred)
//   remote : OUR self-hosted server (server/app.py) — fallback, never a third-party AI API
import Constants from 'expo-constants';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { requireOptionalNativeModule } from 'expo';

import bundledBundle from '../../assets/model/bundle.json';
import { combineProbs } from './advice';
import { decide } from './decision';
import { energy, softmax } from './math';
import type { Bundle, Logits, QualityStats, ScanResult } from './types';
import { HEADS } from './types';

interface NativeProduceModel {
  isAvailable(): boolean;
  analyze(uri: string, size: number, resizeRatio: number, mean: number[], std: number[]): Promise<{ logits: Logits; quality: QualityStats }>;
}

type Mode = 'native' | 'remote';
const extra = (Constants.expoConfig?.extra ?? {}) as { inference?: { mode?: Mode; serverUrl?: string } };
const native = requireOptionalNativeModule<NativeProduceModel>('ProduceModel');

let bundle: Bundle = bundledBundle as unknown as Bundle;
export const getBundle = () => bundle;

export function inferenceMode(): Mode | null {
  const wanted = extra.inference?.mode ?? 'native';
  if (wanted === 'native' && native?.isAvailable()) return 'native';
  if (extra.inference?.serverUrl) return 'remote';
  return native?.isAvailable() ? 'native' : null;
}

async function remoteAnalyze(uri: string): Promise<{ logits: Logits; quality: QualityStats }> {
  const base = extra.inference!.serverUrl!.replace(/\/$/, '');
  // Downscale before upload: less data, same model input (server centre-crops to 224).
  const ctx = ImageManipulator.manipulate(uri).resize({ width: 768 });
  const img = await (await ctx.renderAsync()).saveAsync({ compress: 0.85, format: SaveFormat.JPEG });
  const form = new FormData();
  form.append('image', { uri: img.uri, name: 'scan.jpg', type: 'image/jpeg' } as unknown as Blob);
  const res = await fetch(`${base}/v1/analyze`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`server ${res.status}`);
  const body = await res.json();
  if (body.model_id !== bundle.model_id) {
    // Server was upgraded: fetch its bundle so class lists / thresholds stay consistent.
    bundle = await (await fetch(`${base}/v1/bundle`)).json();
  }
  return body;
}

export interface ScanOutput {
  result: ScanResult;
  top3: { produce: string; he: string; prob: number }[];
  mode: Mode;
  probs: Record<string, number[]>;
  energy: number;
  angles: number;
}

/** Scan a photo. With `previous` (the "another angle" retry after an unsure result), the two
 *  photos' probabilities are combined; a bad second photo falls back to asking for a retake. */
export async function scan(uri: string, previous?: ScanOutput): Promise<ScanOutput> {
  const mode = inferenceMode();
  if (!mode) throw new Error('no inference engine configured');
  const { logits, quality } = mode === 'native'
    ? await native!.analyze(uri, bundle.input.size, bundle.input.resize_ratio, bundle.input.mean, bundle.input.std)
    : await remoteAnalyze(uri);
  let probs: Record<string, number[]> = Object.fromEntries(HEADS.map((h) => [h, softmax(logits[h], bundle.temperatures[h] ?? 1)]));
  let e = energy(logits.produce);
  if (previous && !quality.reason) {
    probs = Object.fromEntries(HEADS.map((h) => [h, combineProbs(previous.probs[h], probs[h])]));
    e = Math.max(e, previous.energy);
  }
  const result = decide(bundle, probs, quality.reason, e);
  const top3 = probs.produce
    .map((p, i) => ({ produce: bundle.outputs.produce[i], he: bundle.produce_meta[bundle.outputs.produce[i]].he, prob: p }))
    .sort((a, b) => b.prob - a.prob)
    .slice(0, 3);
  return { result, top3, mode, probs, energy: e, angles: previous ? previous.angles + 1 : 1 };
}
