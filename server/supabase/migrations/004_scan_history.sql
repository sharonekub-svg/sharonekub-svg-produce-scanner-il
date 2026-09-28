-- Applied to produce-scanner-il on 2026-09-28 as 005_scan_history.
-- Per-account scan history (Google sign-in, optional). Each signed-in user can read, add and delete only their own
-- rows (RLS on auth.uid()); anon has no access. Stored: the scan result JSON and a small thumbnail (data URL,
-- ~15 KB) so history follows the user across devices. The full photo is never stored here.
-- delete_my_account() lets a user delete their account and all its rows (cascade) from the app.

create table if not exists public.scan_history (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  t bigint not null,                                         -- client timestamp (ms), also the client-side id
  result jsonb not null check (pg_column_size(result) <= 16384),
  thumb text check (thumb is null or (length(thumb) <= 60000 and thumb like 'data:image/jpeg;base64,%')),
  unique (user_id, t)
);
comment on table public.scan_history is 'Signed-in users'' own scan history (result + thumbnail). RLS: owner only.';
create index if not exists scan_history_user_idx on public.scan_history (user_id, t desc);

alter table public.scan_history enable row level security;
revoke all on table public.scan_history from anon, authenticated;
grant select, delete on table public.scan_history to authenticated;
grant insert (t, result, thumb) on table public.scan_history to authenticated;

create policy "own rows: read" on public.scan_history for select to authenticated using (user_id = (select auth.uid()));
create policy "own rows: add" on public.scan_history for insert to authenticated with check (user_id = (select auth.uid()));
create policy "own rows: delete" on public.scan_history for delete to authenticated using (user_id = (select auth.uid()));

drop trigger if exists scan_history_rate_limit on public.scan_history;
create trigger scan_history_rate_limit
  before insert on public.scan_history
  for each row execute function private.enforce_feedback_rate();

create or replace function public.delete_my_account()
returns void
language sql
security definer
set search_path = ''
as $$
  delete from auth.users where id = (select auth.uid());
$$;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
