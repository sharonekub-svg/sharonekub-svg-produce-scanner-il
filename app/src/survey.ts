// In-app user survey (server/supabase/migrations/005_user_survey.sql). Asked once, only after real use:
// >= 5 scans spread over >= 3 days. Anonymous: question + answer + scan-count bucket + app version.
// The answers are the only basis for any claim like "X% of users who answered say ...".
import Constants from 'expo-constants';
import { getPref, setPref } from './prefs';

const cfg = (Constants.expoConfig?.extra ?? {}) as { feedback?: { url?: string; anonKey?: string } };

export type SurveyQuestion = 'better_fruit' | 'less_waste';
export type SurveyAnswer = 'a_lot' | 'a_little' | 'no_change' | 'not_sure';
export const QUESTIONS: SurveyQuestion[] = ['better_fruit', 'less_waste'];
export const ANSWERS: SurveyAnswer[] = ['a_lot', 'a_little', 'no_change', 'not_sure'];

export const MIN_SCANS = 5;
export const MIN_DAYS = 3;
const DAY = 24 * 3600 * 1000;
const SNOOZE_DAYS = 7;

export function scansBucket(n: number): '5-9' | '10-29' | '30+' {
  return n >= 30 ? '30+' : n >= 10 ? '10-29' : '5-9';
}

/** Whether to ask now. `scanTimes`: timestamps (ms) of the user's scans; `now` for tests. */
export function shouldAskSurvey(scanTimes: number[], now = Date.now()): boolean {
  if (!cfg.feedback?.url || !cfg.feedback?.anonKey) return false;
  if (getPref('surveyDone')) return false;
  const snooze = getPref('surveySnoozeUntil');
  if (snooze && now < snooze) return false;
  if (scanTimes.length < MIN_SCANS) return false;
  return now - Math.min(...scanTimes) >= MIN_DAYS * DAY;
}

export const snoozeSurvey = (now = Date.now()) => setPref('surveySnoozeUntil', now + SNOOZE_DAYS * DAY);
export const finishSurvey = () => setPref('surveyDone', true);

export async function sendSurveyAnswer(question: SurveyQuestion, answer: SurveyAnswer, scans: number): Promise<boolean> {
  const url = cfg.feedback?.url, key = cfg.feedback?.anonKey;
  if (!url || !key) return false;
  try {
    const res = await fetch(`${url.replace(/\/$/, '')}/rest/v1/user_survey`, {
      method: 'POST',
      headers: {
        apikey: key,
        ...(key.startsWith('eyJ') ? { Authorization: `Bearer ${key}` } : {}),
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({ question, answer, scans_bucket: scansBucket(scans), app_version: Constants.expoConfig?.version ?? null }),
    });
    return res.ok;
  } catch {
    return false; // the survey must never break the app
  }
}
