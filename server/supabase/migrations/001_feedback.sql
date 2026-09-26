-- Opt-in scan feedback. Written by the app with the publishable key; that key can only INSERT.
-- No photos, no user identifiers, no device identifiers.
-- Applied to project produce-scanner-il (ref ucaahtdudyicliqwpvcu) on 2026-09-26.
create table if not exists public.scan_feedback (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  model_id text not null check (length(model_id) between 1 and 120),
  app_version text check (length(app_version) <= 40),
  status text not null check (status in ('ok', 'retake', 'unsure', 'not_produce')),
  produce text check (length(produce) <= 40),
  confidence real check (confidence between 0 and 1),
  correct boolean not null
);

comment on table public.scan_feedback is
  'Anonymous "was this right?" answers from the app. Insert-only for anon; read with service role only.';

alter table public.scan_feedback enable row level security;

-- Least privilege: anon/authenticated may only INSERT these columns.
revoke all on table public.scan_feedback from anon, authenticated;
grant insert (model_id, app_version, status, produce, confidence, correct) on table public.scan_feedback to anon, authenticated;

create policy "app can insert feedback" on public.scan_feedback
  for insert to anon, authenticated
  with check (length(model_id) > 0 and created_at >= now() - interval '1 minute');

create index if not exists scan_feedback_created_at_idx on public.scan_feedback (created_at);

-- Beta dashboard aggregate. security_invoker => evaluated with the caller's rights (service role only).
create or replace view public.feedback_daily with (security_invoker = true) as
  select date_trunc('day', created_at) as day, model_id, produce,
         count(*) as n, avg(case when correct then 1.0 else 0.0 end) as accuracy
  from public.scan_feedback
  where status = 'ok'
  group by 1, 2, 3;
revoke all on public.feedback_daily from anon, authenticated;
