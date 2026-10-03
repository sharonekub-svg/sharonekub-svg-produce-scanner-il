// Labelling mode for the owner (and other labeler accounts): photograph produce, tap good / small problem / rotten,
// and the photo is stored with that label for evaluating and training the model on types no licensed dataset
// covers. Only accounts in private.labelers see it (rpc am_i_labeler); the server stamps the row from the token.
import { authHeaders, onAuthChange, SB_URL } from './auth';
import { donatePhoto } from './donation';

export type LabelCondition = 'good' | 'early' | 'rotten';

let cached: boolean | null = null;
onAuthChange(() => { cached = null; });

/** True when the signed-in account is a labeler. Cached per session; false when signed out or offline. */
export async function amILabeler(): Promise<boolean> {
  if (cached != null) return cached;
  const h = await authHeaders();
  if (!h || !SB_URL) return false;
  try {
    const r = await fetch(`${SB_URL}/rest/v1/rpc/am_i_labeler`, {
      method: 'POST', headers: { ...h, 'Content-Type': 'application/json' }, body: '{}',
    });
    cached = r.ok ? (await r.json()) === true : false;
  } catch {
    return false; // offline: ask again next time
  }
  return cached;
}

let today = { day: '', n: 0 };
export const labelledToday = () => (today.day === new Date().toDateString() ? today.n : 0);

export async function sendLabel(photoUri: string, model_id: string, predicted: string | null, produce: string,
                                condition: LabelCondition): Promise<boolean> {
  const h = await authHeaders();
  if (!h) return false;
  const ok = await donatePhoto({ photoUri, model_id, predicted, correct: predicted == null ? null : predicted === produce,
                                 label: { produce, condition }, headers: h });
  if (ok) {
    const d = new Date().toDateString();
    today = { day: d, n: (today.day === d ? today.n : 0) + 1 };
  }
  return ok;
}
