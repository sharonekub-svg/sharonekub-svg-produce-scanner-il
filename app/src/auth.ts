// Optional Google sign-in (Supabase Auth, PKCE) — same accounts as the web app.
// The OAuth page opens in the system's secure browser sheet and returns to producescanner://auth-callback.
// Only tokens + display name are kept, in the device keychain (SecureStore). Scans sync via cloudHistory.ts.
import * as Crypto from 'expo-crypto';
import Constants from 'expo-constants';
import * as Linking from 'expo-linking';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';

const cfg = (Constants.expoConfig?.extra ?? {}) as { feedback?: { url?: string; anonKey?: string } };
export const SB_URL = cfg.feedback?.url?.replace(/\/$/, '') ?? '';
export const SB_KEY = cfg.feedback?.anonKey ?? '';
const KEY = 'sb_session_v1';

export interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number; // unix seconds
  name: string;
  avatar: string | null;
}

let session: Session | null = null;
let loaded = false;
const listeners = new Set<() => void>();
export const onAuthChange = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };
export const getSession = () => session;

const b64url = (b64: string) => b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
function bytesToB64(bytes: Uint8Array): string {
  let s = '';
  bytes.forEach((x) => { s += String.fromCharCode(x); });
  return btoa(s);
}

async function setSession(j: any | null) {
  session = j ? {
    access_token: j.access_token,
    refresh_token: j.refresh_token,
    expires_at: Date.now() / 1000 + (j.expires_in ?? 3600),
    name: j.user?.user_metadata?.full_name ?? j.user?.email ?? '',
    avatar: j.user?.user_metadata?.avatar_url ?? null,
  } : null;
  try {
    if (session) await SecureStore.setItemAsync(KEY, JSON.stringify(session));
    else await SecureStore.deleteItemAsync(KEY);
  } catch { /* keychain unavailable (e.g. web preview): session stays in memory */ }
  listeners.forEach((f) => f());
}

export async function loadSession(): Promise<Session | null> {
  if (loaded) return session;
  loaded = true;
  try { const s = await SecureStore.getItemAsync(KEY); session = s ? JSON.parse(s) : null; } catch { session = null; }
  listeners.forEach((f) => f());
  return session;
}

/** True when Google sign-in is switched on in Supabase (the button is hidden otherwise). */
export async function googleEnabled(): Promise<boolean> {
  if (!SB_URL || !SB_KEY) return false;
  try {
    const r = await fetch(`${SB_URL}/auth/v1/settings`, { headers: { apikey: SB_KEY } });
    return Boolean((await r.json())?.external?.google);
  } catch { return false; }
}

async function tokenCall(grant: string, body: object) {
  const r = await fetch(`${SB_URL}/auth/v1/token?grant_type=${grant}`, {
    method: 'POST', headers: { apikey: SB_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

/** Opens Google sign-in. Resolves true when signed in, false when cancelled or failed. */
export async function signIn(): Promise<boolean> {
  const verifier = b64url(bytesToB64(Crypto.getRandomBytes(32)));
  const challenge = b64url(await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier,
                                                          { encoding: Crypto.CryptoEncoding.BASE64 }));
  const redirect = Linking.createURL('auth-callback');
  const url = `${SB_URL}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirect)}`
    + `&code_challenge=${challenge}&code_challenge_method=s256`;
  try {
    const res = await WebBrowser.openAuthSessionAsync(url, redirect);
    if (res.type !== 'success') return false;
    const code = /[?&#]code=([^&#]+)/.exec(res.url)?.[1];
    if (!code) return false;
    await setSession(await tokenCall('pkce', { auth_code: decodeURIComponent(code), code_verifier: verifier }));
    return true;
  } catch {
    return false;
  }
}

/** Headers for the signed-in user (refreshes the token when needed); null when signed out. */
export async function authHeaders(): Promise<Record<string, string> | null> {
  await loadSession();
  if (!session) return null;
  if (session.expires_at - 60 < Date.now() / 1000) {
    try { await setSession(await tokenCall('refresh_token', { refresh_token: session.refresh_token })); }
    catch { await setSession(null); return null; }
  }
  return { apikey: SB_KEY, Authorization: `Bearer ${session!.access_token}` };
}

export async function signOut() {
  const h = await authHeaders();
  await setSession(null);
  if (h) fetch(`${SB_URL}/auth/v1/logout`, { method: 'POST', headers: h }).catch(() => {});
}

/** Deletes the account and every scan stored in it (rpc delete_my_account, cascades). */
export async function deleteAccount(): Promise<boolean> {
  const h = await authHeaders();
  if (!h) return false;
  try {
    const r = await fetch(`${SB_URL}/rest/v1/rpc/delete_my_account`, {
      method: 'POST', headers: { ...h, 'Content-Type': 'application/json' }, body: '{}',
    });
    if (!r.ok) return false;
    await setSession(null);
    return true;
  } catch { return false; }
}
