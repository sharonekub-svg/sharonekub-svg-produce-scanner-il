// Inference engine selection. The UI only calls `scan(uri)`; swapping the model or the
// inference location never touches UI code.
//   native : on-device Core ML via modules/produce-model (preferred)
//   remote : OUR self-hosted server (server/app.py) — fallback, never a third-party AI API
//            (also the web preview of the app, served by that same server: same origin)
import Constants from 'expo-constants';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

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
  if (Platform.OS === 'web') return 'remote'; // web preview: the page is served by the inference server
  const wanted = extra.inference?.mode ?? 'native';
  if (wanted === 'native' && native?.isAvailable()) return 'native';
  if (extra.inference?.serverUrl) return 'remote';
  return native?.isAvailable() ? 'native' : null;
}

type Analysis = { logits: Logits; quality: QualityStats };
const serverBase = () => (Platform.OS === 'web' ? '' : extra.inference!.serverUrl!.replace(/\/$/, ''));

// Downscale before upload: less data, same model input (server centre-crops to 224).
async function uploadPart(form: FormData, field: string, uri: string) {
  const ctx = ImageManipulator.manipulate(uri).resize({ width: 768 });
  const img = await (await ctx.renderAsync()).saveAsync({ compress: 0.85, format: SaveFormat.JPEG });
  if (Platform.OS === 'web') form.append(field, await (await fetch(img.uri)).blob(), 'scan.jpg');
  else form.append(field, { uri: img.uri, name: 'scan.jpg', type: 'image/jpeg' } as unknown as Blob);
}

async function syncBundle(modelId: string) {
  // Server was upgraded: fetch its bundle so class lists / thresholds stay consistent.
  if (modelId !== bundle.model_id) bundle = await (await fetch(`${serverBase()}/v1/bundle`)).json();
}

async function remoteAnalyze(uri: string): Promise<Analysis> {
  const form = new FormData();
  await uploadPart(form, 'image', uri);
  const res = await fetch(`${serverBase()}/v1/analyze`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`server ${res.status}`);
  const body = await res.json();
  await syncBundle(body.model_id);
  return body;
}

/** Several frames in one request (one encoder pass on the server); one-by-one if the server is older. */
async function remoteAnalyzeMany(uris: string[]): Promise<Analysis[]> {
  const form = new FormData();
  for (const u of uris) await uploadPart(form, 'images', u);
  const res = await fetch(`${serverBase()}/v1/analyze_many`, { method: 'POST', body: form });
  if (res.status === 404) { const out: Analysis[] = []; for (const u of uris) out.push(await remoteAnalyze(u)); return out; }
  if (!res.ok) throw new Error(`server ${res.status}`);
  const body = await res.json();
  await syncBundle(body.model_id);
  return body.items;
}

const analyzeOne = (uri: string): Promise<Analysis> => (inferenceMode() === 'native'
  ? native!.analyze(uri, bundle.input.size, bundle.input.resize_ratio, bundle.input.mean, bundle.input.std)
  : remoteAnalyze(uri));

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
  if (!inferenceMode()) throw new Error('no inference engine configured');
  return fromAnalysis(await analyzeOne(uri), previous);
}

/** Probabilities, combination with an earlier photo, and the decision for one analysed photo. */
export function fromAnalysis({ logits, quality }: Analysis, previous?: ScanOutput): ScanOutput {
  const mode = inferenceMode()!;
  let probs: Record<string, number[]> = Object.fromEntries(HEADS.map((h) => [h, softmax(logits[h], bundle.temperatures[h] ?? 1)]));
  const general = (logits as Record<string, number[] | undefined>).freshness_general; // P(spoiled) per produce type (v0.8+)
  let e = energy(logits.produce);
  if (previous && !quality.reason) {
    probs = Object.fromEntries(HEADS.map((h) => [h, combineProbs(previous.probs[h], probs[h])]));
    e = Math.max(e, previous.energy);
  }
  if (general) {
    let pg = general.map((l) => 1 / (1 + Math.exp(-l)));
    const prevG = (previous?.probs as Record<string, number[] | undefined> | undefined)?.freshness_general;
    if (prevG && !quality.reason) pg = pg.map((p, i) => combineProbs([1 - prevG[i], prevG[i]], [1 - p, p])[1]); // both angles count
    probs.freshness_general = pg;
  }
  const result = decide(bundle, probs, quality.reason, e);
  const top3 = probs.produce
    .map((p, i) => ({ produce: bundle.outputs.produce[i], he: bundle.produce_meta[bundle.outputs.produce[i]].he, prob: p }))
    .sort((a, b) => b.prob - a.prob)
    .slice(0, 3);
  return { result, top3, mode, probs, energy: e, angles: previous ? previous.angles + 1 : 1 };
}

/** "Several sides" scan: photos taken while the user turns the fruit, combined like "another angle".
 *  A blurry/dark frame never replaces a usable result and is left out of the combination. */
export async function scanMany(uris: string[]): Promise<ScanOutput> {
  if (!uris.length) throw new Error('no photos');
  const mode = inferenceMode();
  if (!mode) throw new Error('no inference engine configured');
  const analyses: Analysis[] = [];
  if (mode === 'remote') analyses.push(...(await remoteAnalyzeMany(uris)));
  else for (const u of uris) analyses.push(await analyzeOne(u));
  return combineFrames(analyses);
}

/** Folds frames into one result: a blurry/dark frame never replaces a usable result and is left out of the combination. */
export function combineFrames(analyses: Analysis[]): ScanOutput {
  let out: ScanOutput | undefined;
  for (const a of analyses) {
    const o = fromAnalysis(a, out && out.result.status !== 'retake' ? out : undefined);
    if (!out || o.result.status !== 'retake' || out.result.status === 'retake') out = o;
  }
  return out!;
}
