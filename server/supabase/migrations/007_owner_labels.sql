-- Labelling mode: the project owner (and anyone added to private.labelers) photographs produce and labels it
-- good / early problems / rotten in the app, for the types no licensed dataset covers (pear, watermelon, melon …).
-- Same path as an opt-in donation (photo_donations row + one object in the private bucket), plus two label columns.
-- The labeler column is set by the server from the caller's JWT, only when that account is in private.labelers:
-- a label sent with the publishable key alone, or by any other account, is stored without a labeler and is not
-- used as ground truth. Labeler accounts are added with SQL by the owner (not from the app, not in this file).

create table if not exists private.labelers (
  user_id uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now()
);
revoke all on table private.labelers from public, anon, authenticated;

-- The app asks this to show the labelling card (no list of labelers is exposed).
create or replace function public.am_i_labeler()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from private.labelers l where l.user_id = auth.uid());
$$;
revoke all on function public.am_i_labeler() from public, anon;
grant execute on function public.am_i_labeler() to authenticated;

alter table public.photo_donations add column if not exists label_condition text
  check (label_condition in ('good', 'early', 'rotten'));
alter table public.photo_donations add column if not exists label_produce text
  check (label_produce ~ '^[a-z_]{2,30}$');
alter table public.photo_donations add column if not exists labeler uuid;
grant insert (label_condition, label_produce) on table public.photo_donations to anon, authenticated;

create or replace function private.stamp_labeler()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.labeler := (select l.user_id from private.labelers l where l.user_id = auth.uid());
  return new;
end;
$$;
revoke all on function private.stamp_labeler() from public, anon, authenticated;

drop trigger if exists photo_donations_stamp_labeler on public.photo_donations;
create trigger photo_donations_stamp_labeler
  before insert on public.photo_donations
  for each row execute function private.stamp_labeler();

-- Owner's view of the labelled set (service role only).
create or replace view public.owner_labels_summary with (security_invoker = true) as
  select label_produce, label_condition, count(*) as n, min(created_at) as first, max(created_at) as last
  from public.photo_donations
  where labeler is not null
  group by label_produce, label_condition;
revoke all on public.owner_labels_summary from anon, authenticated;
