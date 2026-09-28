// REST calls for the signed-in user's scan history (public.scan_history, owner-only RLS;
// server/supabase/migrations/004_scan_history.sql). Same rows as the web app, so history is shared.
import { SB_URL, authHeaders } from './auth';

export interface CloudRow { t: number; result: any; thumb: string | null }

async function call(method: string, query = '', body?: unknown): Promise<any | null> {
  const h = await authHeaders();
  if (!h) return null;
  try {
    const r = await fetch(`${SB_URL}/rest/v1/scan_history${query}`, {
      method, headers: { ...h, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return r.ok ? (method === 'GET' ? r.json() : true) : null;
  } catch { return null; }
}

export const cloudList = (): Promise<CloudRow[] | null> => call('GET', '?select=t,result,thumb&order=t.desc&limit=100');
// Inserts are rate-limited to 10 rows/min per client: callers send at most 8 at once.
export const cloudAdd = (rows: CloudRow[]) => call('POST', '', rows);
export const cloudRemove = (t: number) => call('DELETE', `?t=eq.${t}`);
export const cloudClear = () => call('DELETE', '?t=gte.0');
