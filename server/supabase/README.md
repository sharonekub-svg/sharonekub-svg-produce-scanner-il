# Supabase — scan feedback backend

| | |
|---|---|
| Project | `produce-scanner-il` (ref `ucaahtdudyicliqwpvcu`), org `shakana1`, region eu-central-1 (Frankfurt), free plan |
| API URL | https://ucaahtdudyicliqwpvcu.supabase.co |
| App key | publishable key in `app/app.json → extra.feedback.anonKey` (safe to ship; it can only INSERT feedback) |
| Schema | `migrations/001_feedback.sql` — table `scan_feedback`, view `feedback_daily` |

**What the app can do with its key:** insert one feedback row. It cannot read, update or delete anything,
and cannot read `feedback_daily` (verified 2026-09-26 by running each operation as the `anon` role;
security advisors: 0 findings).

**What is stored:** model id, app version, scan status, predicted produce, confidence, yes/no. No photos,
no user or device identifiers (see `docs/legal/privacy-policy-he.md`).

**Reading results:** Supabase dashboard → SQL editor: `select * from feedback_daily order by day desc;`
The service-role key must never be put in the app or the repo.

**Known limits:** anonymous inserts can be spammed; before a public launch add rate limiting (e.g. an Edge
Function in front of the insert, or a per-IP limit at the API gateway).

**Note:** to stay within the free plan's 2-active-project limit, the project `ipl-fc27` was paused on
2026-09-26 at the owner's request. Restore it from the Supabase dashboard (Project → Restore) when needed;
that will require pausing another project or upgrading.
