# In-app user survey

Asked once per install, on the result screen of a real scan (not a sample, not from history), after >= 5 scans
spread over >= 3 days. Two questions, one at a time; "not now" snoozes 7 days, "don't ask again" or answering ends it.
Anonymous: question, answer, scan-count bucket (5-9 / 10-29 / 30+), app version. Code: `app/src/survey.ts`,
`app/src/ui/Survey.tsx`. Table: `server/supabase/migrations/005_user_survey.sql` (insert-only for the app, rate-limited).

| id | question (Hebrew in the app) |
|---|---|
| better_fruit | Since you started using the app, do you choose better fruit and vegetables? |
| less_waste | Since you started using the app, do you throw away less fruit and vegetables? |

Answers: a_lot (כן, הרבה) · a_little (קצת) · no_change (לא השתנה) · not_sure (לא בטוח/ה).

## Reading the results (Supabase SQL editor, service role)
```sql
select * from public.survey_summary order by question, answer;
```

## Using it in marketing
Only with the real numbers and who they describe, e.g. "72% of users who answered say they choose better fruit"
(a_lot + a_little), with the number of answers behind it. Wait for at least ~100 answers per question before
publishing a percentage. The survey measures what users say, not their nutrition: never turn it into a health claim.
