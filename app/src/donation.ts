// Opt-in photo donation (docs/research/food-quality.md → data; server/supabase/migrations/003_photo_donations.sql).
// Only after the user taps "share" and confirms the consent text, for THIS photo only. The photo is
// re-encoded to <= 1024 px JPEG, which drops EXIF (GPS location, device model). No user or device id is sent.
import Constants from 'expo-constants';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

const cfg = (Constants.expoConfig?.extra ?? {}) as { feedback?: { url?: string; anonKey?: string } };
export const CONSENT_VERSION = 'v1';

export interface Donation {
  photoUri: string;
  model_id: string;
  predicted: string | null;
  correct: boolean | null;
  score?: number | null;
  quality_verdict?: 'great' | 'okay' | 'poor' | null;
}

export function donationEnabled(): boolean {
  return Boolean(cfg.feedback?.url && cfg.feedback?.anonKey);
}

function uuid4(): string {
  // Object name only (the server checks the v4 shape); not a secret and not an identifier of the user.
  const h = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16));
  h[12] = '4';
  h[16] = '89ab'[Math.floor(Math.random() * 4)];
  const s = h.join('');
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}

export async function donatePhoto(d: Donation): Promise<boolean> {
  const url = cfg.feedback?.url?.replace(/\/$/, ''), key = cfg.feedback?.anonKey;
  if (!url || !key) return false;
  const auth = { apikey: key, ...(key.startsWith('eyJ') ? { Authorization: `Bearer ${key}` } : {}) };
  try {
    const ctx = ImageManipulator.manipulate(d.photoUri).resize({ width: 1024 });
    const img = await (await ctx.renderAsync()).saveAsync({ compress: 0.85, format: SaveFormat.JPEG });
    const name = `${uuid4()}.jpg`;
    const reg = await fetch(`${url}/rest/v1/photo_donations`, {
      method: 'POST',
      headers: { ...auth, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify({ object_name: name, model_id: d.model_id, predicted: d.predicted, correct: d.correct,
                             score: d.score ?? null, quality_verdict: d.quality_verdict ?? null,
                             consent_version: CONSENT_VERSION, app_version: Constants.expoConfig?.version ?? null }),
    });
    if (!reg.ok) return false;
    const blob = await (await fetch(img.uri)).blob();
    const up = await fetch(`${url}/storage/v1/object/scan-donations/${name}`, {
      method: 'POST',
      headers: { ...auth, 'Content-Type': 'image/jpeg' },
      body: blob,
    });
    return up.ok;
  } catch {
    return false; // donation must never break the scan flow
  }
}
