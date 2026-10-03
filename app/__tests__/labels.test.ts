import { beforeEach, expect, it, jest } from '@jest/globals';

// Labelling mode: the label goes with the labeler's own token (so the server can stamp it), and only a labeler sees it.
jest.mock('expo-constants', () => ({ expoConfig: { version: '1.5.1', extra: { feedback: { url: 'https://sb.test', anonKey: 'pk' } } } }));
jest.mock('expo-image-manipulator', () => ({
  SaveFormat: { JPEG: 'jpeg' },
  ImageManipulator: { manipulate: () => ({ resize: () => ({ renderAsync: async () => ({ saveAsync: async () => ({ uri: 'file://x.jpg' }) }) }) }) },
}));
let mockHeaders: Record<string, string> | null = { apikey: 'pk', Authorization: 'Bearer USER' };
jest.mock('../src/auth', () => ({
  SB_URL: 'https://sb.test', authHeaders: async () => mockHeaders, onAuthChange: () => () => {},
}));

const calls: { url: string; headers: any; body: any }[] = [];
let rpcAnswer = true;
beforeEach(() => {
  calls.length = 0;
  (global as any).fetch = jest.fn(async (url: string, init: any) => {
    calls.push({ url, headers: init?.headers, body: typeof init?.body === 'string' && init.body.startsWith('{') ? JSON.parse(init.body) : init?.body ?? null });
    if (url.endsWith('/rpc/am_i_labeler')) return { ok: true, json: async () => rpcAnswer } as any;
    return { ok: true, blob: async () => 'BLOB', json: async () => ({}) } as any;
  });
});

it('sends the label with the user token, plus the model guess', async () => {
  const { sendLabel, labelledToday } = require('../src/labels');
  expect(await sendLabel('file://p.jpg', 'm1', 'apple', 'pear', 'early')).toBe(true);
  const reg = calls.find((c) => c.url.endsWith('/rest/v1/photo_donations'))!;
  expect(reg.headers.Authorization).toBe('Bearer USER');
  expect(reg.body).toMatchObject({ label_produce: 'pear', label_condition: 'early', predicted: 'apple', correct: false });
  expect(calls.some((c) => c.url.includes('/storage/v1/object/scan-donations/'))).toBe(true);
  expect(labelledToday()).toBe(1);
});

it('is hidden when signed out', async () => {
  mockHeaders = null;
  const { amILabeler } = require('../src/labels');
  expect(await amILabeler()).toBe(false);
  mockHeaders = { apikey: 'pk', Authorization: 'Bearer USER' };
});
