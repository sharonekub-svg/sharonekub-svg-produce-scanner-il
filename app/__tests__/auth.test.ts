import { beforeEach, expect, it, jest } from '@jest/globals';
import { createHash } from 'crypto';

jest.mock('expo-crypto', () => ({
  CryptoDigestAlgorithm: { SHA256: 'SHA-256' }, CryptoEncoding: { BASE64: 'base64' },
  getRandomBytes: (n: number) => new Uint8Array(require('crypto').randomBytes(n)),
  digestStringAsync: async (_a: string, data: string) => require('crypto').createHash('sha256').update(data).digest('base64'),
}));
const mockStore = new Map<string, string>();
jest.mock('expo-secure-store', () => ({
  getItemAsync: async (k: string) => mockStore.get(k) ?? null,
  setItemAsync: async (k: string, v: string) => { mockStore.set(k, v); },
  deleteItemAsync: async (k: string) => { mockStore.delete(k); },
}));
jest.mock('expo-linking', () => ({ createURL: (p: string) => `producescanner://${p}` }));
let mockAuthUrl = '';
jest.mock('expo-web-browser', () => ({
  openAuthSessionAsync: async (url: string) => { mockAuthUrl = url; return { type: 'success', url: 'producescanner://auth-callback?code=abc123' }; },
}));
jest.mock('expo-constants', () => ({ expoConfig: { extra: { feedback: { url: 'https://sb.test', anonKey: 'pk' } } } }));

const calls: { url: string; body: any }[] = [];
beforeEach(() => {
  calls.length = 0; mockStore.clear();
  (global as any).fetch = jest.fn(async (url: string, init: any) => {
    calls.push({ url, body: init?.body ? JSON.parse(init.body) : null });
    return { ok: true, json: async () => ({ access_token: 'AT', refresh_token: 'RT', expires_in: 3600, user: { user_metadata: { full_name: 'Dana' } } }) } as any;
  });
});

it('signs in with PKCE, stores only tokens + name in the keychain, and signs out', async () => {
  const auth = require('../src/auth');
  expect(await auth.signIn()).toBe(true);
  const q = new URLSearchParams(mockAuthUrl.split('?')[1]);
  expect(q.get('provider')).toBe('google');
  expect(q.get('redirect_to')).toBe('producescanner://auth-callback');
  const token = calls.find((c) => c.url.includes('grant_type=pkce'))!;
  expect(token.body.auth_code).toBe('abc123');
  const expected = createHash('sha256').update(token.body.code_verifier).digest('base64url');
  expect(q.get('code_challenge')).toBe(expected);
  const stored = JSON.parse(mockStore.get('sb_session_v1')!);
  expect(Object.keys(stored).sort()).toEqual(['access_token', 'avatar', 'expires_at', 'name', 'refresh_token']);
  expect(await auth.authHeaders()).toEqual({ apikey: 'pk', Authorization: 'Bearer AT' });
  await auth.signOut();
  expect(auth.getSession()).toBeNull();
  expect(mockStore.has('sb_session_v1')).toBe(false);
});
