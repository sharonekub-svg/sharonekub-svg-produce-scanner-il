// "My scans" history (same idea as the web app's history).
// Stored in the app's document directory: history/index.json + one small JPEG thumbnail per scan.
// Only successful scans ("ok") are kept; newest first; at most HMAX entries.
// When signed in with Google (auth.ts), entries also sync with the account (cloud.ts) — shared with the web app.
import { Directory, File, Paths } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

import { getSession } from './auth';
import { type CloudRow, cloudAdd, cloudClear, cloudList, cloudRemove } from './cloud';
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
  const entry = { id, t: id, thumb, output };
  const h = [entry, ...loadHistory()];
  h.slice(HMAX).forEach(deleteThumb);
  save(h.slice(0, HMAX));
  if (getSession()) toCloud(entry).then((row) => cloudAdd([row]));
}

export function removeFromHistory(id: number) {
  const h = loadHistory();
  h.filter((e) => e.id === id).forEach(deleteThumb);
  save(h.filter((e) => e.id !== id));
  if (getSession()) cloudRemove(id);
}

export function clearHistory() {
  loadHistory().forEach(deleteThumb);
  save([]);
  if (getSession()) cloudClear();
}

// ---------- account sync ----------
const THUMB_MAX = 60000; // server check: data URL length <= 60000

async function toCloud(e: HistoryEntry): Promise<CloudRow> {
  let thumb: string | null = null;
  try {
    if (e.thumb) {
      const url = `data:image/jpeg;base64,${await new File(e.thumb).base64()}`;
      thumb = url.length <= THUMB_MAX ? url : null;
    }
  } catch { thumb = null; }
  // The web app keeps top3 inside the result object; keep the same shape so both can read every row.
  return { t: e.id, result: { ...e.output.result, top3: e.output.top3 }, thumb };
}

function fromCloud(row: CloudRow): HistoryEntry {
  let thumb: string | null = null;
  const m = /^data:image\/jpeg;base64,(.+)$/.exec(row.thumb ?? '');
  if (m) {
    try {
      const d = dir();
      if (d) { const f = new File(d, `${row.t}.jpg`); f.write(m[1], { encoding: 'base64' }); thumb = f.uri; }
      else thumb = row.thumb; // no device file system: a data URL still displays
    } catch { thumb = null; }
  }
  const { top3, ...result } = row.result ?? {};
  return { id: row.t, t: row.t, thumb, output: { result, top3: Array.isArray(top3) ? top3 : [], angles: 1 } as ScanOutput };
}

let syncing: Promise<void> | null = null;
/** Merge the account's scans into this device and upload this device's scans (at most 8 per sync). */
export function syncHistory(): Promise<void> {
  if (!getSession()) return Promise.resolve();
  syncing ??= (async () => {
    try {
      const rows = await cloudList();
      if (!rows) return;
      const local = loadHistory();
      const have = new Set(local.map((e) => e.id));
      const inCloud = new Set(rows.map((r) => r.t));
      const up = local.filter((e) => !inCloud.has(e.id)).slice(0, 8);
      if (up.length) await cloudAdd(await Promise.all(up.map(toCloud)));
      const added = rows.filter((r) => !have.has(r.t)).map(fromCloud);
      if (!added.length) return;
      const merged = [...local, ...added].sort((a, b) => b.t - a.t);
      merged.slice(HMAX).forEach(deleteThumb);
      save(merged.slice(0, HMAX));
    } finally {
      syncing = null;
    }
  })();
  return syncing;
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
