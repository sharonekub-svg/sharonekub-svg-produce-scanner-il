// Opt-in user feedback ("was this right?"). Sends NO photo and no identifiers — only the model's
// answer and the user's yes/no. Disabled unless app.json extra.feedback.{url,anonKey} is set
// (Supabase table: server/supabase/migrations/001_feedback.sql, insert-only RLS).
import Constants from 'expo-constants';

const cfg = (Constants.expoConfig?.extra ?? {}) as { feedback?: { url?: string; anonKey?: string } };

export interface Feedback {
  model_id: string;
  status: string;
  produce: string | null;
  confidence: number | null;
  correct: boolean;
}

export async function sendFeedback(f: Feedback): Promise<boolean> {
  const url = cfg.feedback?.url, key = cfg.feedback?.anonKey;
  if (!url || !key) return false;
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/rest/v1/scan_feedback`, {
      method: 'POST',
      // Publishable keys (sb_publishable_…) go in `apikey` only; legacy JWT anon keys also as Bearer.
      headers: {
        apikey: key,
        ...(key.startsWith('eyJ') ? { Authorization: `Bearer ${key}` } : {}),
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({ ...f, app_version: Constants.expoConfig?.version ?? null }),
    });
    return res.ok;
  } catch {
    return false; // feedback must never break the scan flow
  }
}

export type Rating = 'great' | 'okay' | 'poor';

/** "How was the analysis?" (great / okay / poor) with the type and the score shown. No photo, no identifiers
 *  (Supabase table quality_feedback, server/supabase/migrations/006_quality_feedback.sql, insert-only). */
export async function sendRating(r: { model_id: string; produce: string | null; score: number | null; verdict: Rating }): Promise<boolean> {
  const url = cfg.feedback?.url, key = cfg.feedback?.anonKey;
  if (!url || !key) return false;
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/rest/v1/quality_feedback`, {
      method: 'POST',
      headers: {
        apikey: key,
        ...(key.startsWith('eyJ') ? { Authorization: `Bearer ${key}` } : {}),
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({ ...r, app_version: Constants.expoConfig?.version ?? null }),
    });
    return res.ok;
  } catch {
    return false; // feedback must never break the scan flow
  }
}
