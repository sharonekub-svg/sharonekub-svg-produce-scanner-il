-- "How was the analysis?" on the result screen (great / okay / poor), asked once per scan instead of 👍/👎.
-- Anonymous, insert-only for the app (no photo, no account, no device id). Stored with the type and the score
-- shown, so "poor" answers point at the real-world cases the quality heads miss (they were trained on
-- studio/kitchen datasets).
create table if not exists public.quality_feedback (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  model_id text not null check (length(model_id) between 1 and 120),
  app_version text check (length(app_version) <= 40),
  produce text check (length(produce) <= 40),
  score smallint check (score between 1 and 10),  -- null when the type has no score yet
  verdict text not null check (verdict in ('great', 'okay', 'poor'))
);

comment on table public.quality_feedback is
  'Anonymous "how was the analysis?" answers (great/okay/poor). Insert-only for anon; service role reads.';

alter table public.quality_feedback enable row level security;
revoke all on table public.quality_feedback from anon, authenticated;
grant insert (model_id, app_version, produce, score, verdict) on table public.quality_feedback to anon, authenticated;

create policy "app can insert quality feedback" on public.quality_feedback
  for insert to anon, authenticated
  with check (length(model_id) > 0 and created_at >= now() - interval '1 minute');

create index if not exists quality_feedback_created_at_idx on public.quality_feedback (created_at);

drop trigger if exists quality_feedback_rate_limit on public.quality_feedback;
create trigger quality_feedback_rate_limit
  before insert on public.quality_feedback
  for each row execute function private.enforce_feedback_rate();

-- A donated photo can carry the same verdict, which makes it a labelled real-world example.
alter table public.photo_donations add column if not exists score smallint check (score between 1 and 10);
alter table public.photo_donations add column if not exists quality_verdict text
  check (quality_verdict in ('great', 'okay', 'poor'));
grant insert (score, quality_verdict) on table public.photo_donations to anon, authenticated;

-- Per type: share of great/okay/poor and the average score shown (service role only).
create or replace view public.quality_feedback_summary with (security_invoker = true) as
  select produce, verdict, count(*) as n, round(avg(score), 1) as avg_score
  from public.quality_feedback
  group by produce, verdict;
revoke all on public.quality_feedback_summary from anon, authenticated;
