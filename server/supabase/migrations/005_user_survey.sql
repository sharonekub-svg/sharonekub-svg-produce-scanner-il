-- In-app user survey ("since you started using Scan Fruit AI ..."). Anonymous, insert-only for the app.
-- Shown once, after >= 5 scans spread over >= 3 days (app/src/survey.ts). No photo, no account, no device id:
-- only the question, the answer, how many scans the user had (bucket) and the app version.
-- Results are read with the service role only (view survey_summary) and are the ONLY basis for any
-- marketing claim such as "X% of users who answered say ...".
create table if not exists public.user_survey (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  app_version text check (length(app_version) <= 40),
  question text not null check (question in ('better_fruit', 'less_waste')),
  answer text not null check (answer in ('a_lot', 'a_little', 'no_change', 'not_sure')),
  scans_bucket text not null check (scans_bucket in ('5-9', '10-29', '30+'))
);

comment on table public.user_survey is
  'Anonymous in-app survey answers. Insert-only for anon/authenticated; read with service role only.';

alter table public.user_survey enable row level security;
revoke all on table public.user_survey from anon, authenticated;
grant insert (app_version, question, answer, scans_bucket) on table public.user_survey to anon, authenticated;

create policy "app can insert survey answers" on public.user_survey
  for insert to anon, authenticated
  with check (created_at >= now() - interval '1 minute');

create index if not exists user_survey_created_at_idx on public.user_survey (created_at);

-- Same per-client rate limit as scan_feedback (002): <= 10 inserts per client per minute.
drop trigger if exists user_survey_rate_limit on public.user_survey;
create trigger user_survey_rate_limit
  before insert on public.user_survey
  for each row execute function private.enforce_feedback_rate();

-- Share of answers per question (service role only).
create or replace view public.survey_summary with (security_invoker = true) as
  select question, answer, count(*) as n,
         round(100.0 * count(*) / sum(count(*)) over (partition by question), 1) as pct
  from public.user_survey
  group by question, answer;
revoke all on public.survey_summary from anon, authenticated;
