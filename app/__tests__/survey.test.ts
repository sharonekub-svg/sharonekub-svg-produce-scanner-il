import { beforeEach, expect, it, jest } from '@jest/globals';

jest.mock('expo-constants', () => ({ expoConfig: { version: '1.3.0', extra: { feedback: { url: 'https://sb.test', anonKey: 'pk' } } } }));
const mockPrefs: Record<string, unknown> = {};
jest.mock('../src/prefs', () => ({
  getPref: (k: string) => mockPrefs[k],
  setPref: (k: string, v: unknown) => { mockPrefs[k] = v; },
}));

import { finishSurvey, scansBucket, sendSurveyAnswer, shouldAskSurvey, snoozeSurvey } from '../src/survey';

const DAY = 24 * 3600 * 1000;
const NOW = 1_800_000_000_000;
const spread = (n: number, days: number) => Array.from({ length: n }, (_, i) => NOW - (days * DAY * i) / Math.max(n - 1, 1));

beforeEach(() => { for (const k of Object.keys(mockPrefs)) delete mockPrefs[k]; });

it('asks only after 5 scans spread over 3 days', () => {
  expect(shouldAskSurvey(spread(4, 5), NOW)).toBe(false);
  expect(shouldAskSurvey(spread(10, 1), NOW)).toBe(false);
  expect(shouldAskSurvey(spread(5, 3), NOW)).toBe(true);
});

it('never again after finishing; not during snooze', () => {
  snoozeSurvey(NOW);
  expect(shouldAskSurvey(spread(6, 4), NOW + DAY)).toBe(false);
  expect(shouldAskSurvey(spread(6, 4), NOW + 8 * DAY)).toBe(true);
  finishSurvey();
  expect(shouldAskSurvey(spread(6, 4), NOW + 30 * DAY)).toBe(false);
});

it('buckets scan counts', () => {
  expect([5, 9, 10, 29, 30, 200].map(scansBucket)).toEqual(['5-9', '5-9', '10-29', '10-29', '30+', '30+']);
});

it('sends only question, answer, bucket and app version', async () => {
  const calls: { url: string; body: any }[] = [];
  (global as any).fetch = jest.fn(async (url: string, init: any) => { calls.push({ url, body: JSON.parse(init.body) }); return { ok: true } as any; });
  expect(await sendSurveyAnswer('less_waste', 'a_little', 12)).toBe(true);
  expect(calls[0].url).toBe('https://sb.test/rest/v1/user_survey');
  expect(calls[0].body).toEqual({ question: 'less_waste', answer: 'a_little', scans_bucket: '10-29', app_version: '1.3.0' });
});
