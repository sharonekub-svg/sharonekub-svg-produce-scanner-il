# Supabase — scan feedback and photo-donation backend

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

**Rate limiting** (`migrations/002_feedback_rate_limit.sql`): ≤ 10 inserts per client per minute and ≤ 2000
per minute overall, enforced by a trigger. Clients are keyed by a salted hash of the first
`X-Forwarded-For` address (raw IPs are never stored; buckets are deleted after an hour). Verified in-database:
12 inserts from one address → 10 accepted, 2 rejected; a second address unaffected. Advisors: 0 findings.

**Photo donations** (`migrations/003_photo_donations.sql`): opt-in, per photo, after the user reads the consent text.
The app registers a row in `photo_donations` (same rate-limit trigger), then uploads that one object to the
**private** bucket `scan-donations` (JPEG only, ≤ 2 MB). The storage policy accepts only names registered in the
last 10 minutes, so the publishable key can't be used as file hosting. Nothing can be listed or read back with it.
Verified as `anon` in SQL on 2026-09-27: registered upload accepted; unregistered name → RLS violation; malformed
name → check violation; rows and objects unreadable. Advisors: 0 findings. To review donations: dashboard →
Storage → `scan-donations`, joined with `select * from photo_donations order by created_at desc;`.

**Note:** to stay within the free plan's 2-active-project limit, the project `ipl-fc27` was paused on
2026-09-26 at the owner's request. Restore it from the Supabase dashboard (Project → Restore) when needed;
that will require pausing another project or upgrading.
