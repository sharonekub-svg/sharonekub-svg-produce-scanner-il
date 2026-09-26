# Phases 8–9: beta and production runbook

Everything here is implemented as code or config in the repo. Anything that needs an Apple developer account, a Supabase project, real users or a lawyer is listed as a **human action**.

## Phase 8 — Beta (TestFlight, ~50 Israeli users)

**Entry criteria.** All of these must hold:
- Phase 5 gates pass on the real-world set.
- Phase 6 on-device gates pass.
- A lawyer has signed off every dataset listed in `bundle.training_datasets` (`scripts/verify_licenses.py --manifest … --purpose commercial_training` exits 0).
- The privacy policy is published.

| Item | Where | Status |
|---|---|---|
| iOS build profile | `app/eas.json` (`development`, `preview` = TestFlight, `production`) | ✅ in repo |
| Feedback ("was this right?") | `app/src/feedback.ts` → `scan_feedback` table; migration `server/supabase/migrations/001_feedback.sql` (insert-only RLS, no photos, no identifiers) | ✅ code. **Human:** create the Supabase project, apply the migration, put URL and anon key in `app.json → extra.feedback` |
| Beta dashboard | `feedback_daily` view (accuracy by model × produce per day), readable with the service role only | ✅ SQL |
| Photo donation for the real-world set | Not in the app. Collected only through the contributor process in `data-collection-protocol.md` | by design |
| **Human actions** | Apple developer account; `eas build --profile preview`; recruit testers; publish privacy policy (Hebrew) | — |

**Beta exit criteria:**
- ≥ 1,000 scans with feedback.
- User-reported accuracy for produce ID ≥ 90% overall and ≥ 85% for every P1 produce with n ≥ 30.
- Abstention (`unsure`/`retake`) ≤ 25% of scans.
- No safety-wording complaints.
- Crash-free sessions ≥ 99.5%.

## Phase 9 — Production

### Release checklist (per model version)

1. `python -m ml.export.export --ckpt … --out exports/vN --coreml --fp16`.
2. `python -m ml.export.verify_onnx …`: fp32 top-1 agreement with PyTorch must be 100%.
3. Evaluate on:
   - the standard test set
   - the cross-dataset set
   - the **real-world set**
   - the unseen-produce OOD set
   - the stress-proxy sets

   All gates in `evaluation.md` must pass. Store the JSONs next to the export.
4. `python scripts/verify_licenses.py --manifest <training manifest> --purpose commercial_training` must exit 0.
5. `scripts/sync_model_to_app.sh exports/vN`. This also regenerates the data-credits screen (`scripts/gen_credits.py`).
6. On-device parity plus performance check (`mobile.md` steps 3–5).
7. `app.json` version bump → `eas build --profile production` → App Store review.

### Model updates

- The model ships inside the binary. The bundle's `model_id` is shown on the result screen and sent with feedback, so every feedback row maps to an exact model.
- **Over-the-air JS updates (`eas update`) must not change `decision.ts` without a matching Python change and regenerated parity fixtures.** CI (`.github/workflows/ci.yml`) enforces this through the parity tests.
- Remote mode: the server exposes `model_id` via `/healthz` and `/v1/bundle`. The app refetches the bundle when the server's `model_id` changes.

### Monitoring

| Signal | Source | Alert |
|---|---|---|
| Accuracy by model × produce | `feedback_daily` | 7-day accuracy for any P1 produce < 85% with n ≥ 30 |
| Abstention rate | client analytics (to add; no photos) | > 30% over 7 days → retune thresholds on the real-world set |
| Server latency / errors (remote mode) | platform metrics on `/v1/analyze` | p95 > 1.5 s or 5xx > 1% |
| Data drift | monthly: evaluate the newest donated real-world batch | macro-F1 drop > 3 points vs. release |

### Retraining cadence

Retrain quarterly, or when an alert fires:
1. Add the newly collected own-data (stream A to train; stream B stays test-only).
2. Rebuild the manifest (dedup across old and new data).
3. Rerun the Phase 4 winner config plus the release checklist.
4. A new model must beat the current one on the real-world set's worst P1 class, not just on average.
