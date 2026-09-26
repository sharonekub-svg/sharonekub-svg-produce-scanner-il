-- Opt-in scan feedback. Written by the app with the anon key; nobody can read it with that key.
-- No photos, no user identifiers, no device identifiers.
create table if not exists public.scan_feedback (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  model_id text not null check (length(model_id) <= 120),
  app_version text check (length(app_version) <= 40),
  status text not null check (status in ('ok', 'retake', 'unsure', 'not_produce')),
  produce text check (length(produce) <= 40),
  confidence real check (confidence between 0 and 1),
  correct boolean not null
);

alter table public.scan_feedback enable row level security;

-- anon may INSERT only; no select/update/delete policies exist for anon/authenticated.
create policy "anon can insert feedback" on public.scan_feedback
  for insert to anon with check (true);

-- Aggregates for the beta dashboard (read with the service role only).
create or replace view public.feedback_daily as
  select date_trunc('day', created_at) as day, model_id, produce,
         count(*) as n, avg(case when correct then 1.0 else 0.0 end) as accuracy
  from public.scan_feedback where status = 'ok'
  group by 1, 2, 3;
revoke all on public.feedback_daily from anon, authenticated;
