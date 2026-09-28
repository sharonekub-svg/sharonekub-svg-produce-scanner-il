// "My scans" history, on this device only (same idea as the web app's history).
// Stored in the app's document directory: history/index.json + one small JPEG thumbnail per scan.
// Only successful scans ("ok") are kept; newest first; at most HMAX entries.
import { Directory, File, Paths } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

import type { ScanOutput } from './model/engine';

export const HMAX = 30;

export interface HistoryEntry {
  id: number;          // timestamp (ms), also the thumbnail file name
  t: number;
  thumb: string | null; // file URI of the thumbnail
  output: ScanOutput;
}

let cache: HistoryEntry[] | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((f) => f());
export const onHistoryChange = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };

function dir(): Directory | null {
  try {
    const d = new Directory(Paths.document, 'history');
    if (!d.exists) d.create({ idempotent: true, intermediates: true });
    return d;
  } catch {
    return null; // e.g. web preview: keep history in memory only
  }
}

function indexFile(): File | null {
  const d = dir();
  return d ? new File(d, 'index.json') : null;
}

export function loadHistory(): HistoryEntry[] {
  if (cache) return cache;
  try {
    const f = indexFile();
    cache = f && f.exists ? (JSON.parse(f.textSync()) as HistoryEntry[]) : [];
  } catch {
    cache = [];
  }
  return cache;
}

function save(h: HistoryEntry[]) {
  cache = h;
  try { indexFile()?.write(JSON.stringify(h)); } catch { /* history must never break scanning */ }
  notify();
}

function deleteThumb(e: HistoryEntry) {
  try { if (e.thumb) { const f = new File(e.thumb); if (f.exists) f.delete(); } } catch { /* ignore */ }
}

/** Add a finished scan (only status "ok"). Never throws. */
export async function addToHistory(photoUri: string, output: ScanOutput): Promise<void> {
  if (output.result.status !== 'ok') return;
  const id = Date.now();
  let thumb: string | null = null;
  try {
    const d = dir();
    if (d) {
      const img = await (await ImageManipulator.manipulate(photoUri).resize({ width: 360 }).renderAsync())
        .saveAsync({ compress: 0.72, format: SaveFormat.JPEG });
      const dest = new File(d, `${id}.jpg`);
      await new File(img.uri).copy(dest);
      thumb = dest.uri;
    }
  } catch { thumb = null; }
  const h = [{ id, t: id, thumb, output }, ...loadHistory()];
  h.slice(HMAX).forEach(deleteThumb);
  save(h.slice(0, HMAX));
}

export function removeFromHistory(id: number) {
  const h = loadHistory();
  h.filter((e) => e.id === id).forEach(deleteThumb);
  save(h.filter((e) => e.id !== id));
}

export function clearHistory() {
  loadHistory().forEach(deleteThumb);
  save([]);
}

/** Summary for the header pills: total, good (score ≥ 7), not recommended (score ≤ 3). */
export function summarize(h: HistoryEntry[]) {
  const scored = h.filter((e) => e.output.result.score != null);
  return {
    total: h.length,
    scored: scored.length,
    good: scored.filter((e) => (e.output.result.score ?? 0) >= 7).length,
    bad: scored.filter((e) => (e.output.result.score ?? 99) <= 3).length,
  };
}
