-- Applied to produce-scanner-il on 2026-09-27 (as 004_photo_donations). Verified as role anon in SQL: registered
-- upload accepted; unregistered name -> RLS violation; bad name -> check violation; rows and objects unreadable;
-- security advisors: 0 findings.
-- Opt-in photo donations: the user explicitly chooses to share ONE scan photo (per-photo consent in the
-- app) so it can be graded and used to train the model on real Israeli photos (docs/data-collection-protocol.md).
-- Flow (publishable key only): 1) INSERT a row into public.photo_donations (rate-limited by the same trigger
-- as feedback) naming a random object, 2) upload that one object to the private bucket. The storage policy
-- only accepts an object whose name was registered in step 1 within the last 10 minutes, so the key cannot
-- be used as free file hosting. Nothing can be read back with the publishable key.
-- The app re-encodes the photo (1024 px wide JPEG), which drops EXIF, including GPS location.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values ('scan-donations', 'scan-donations', false, 2097152, array['image/jpeg'])
  on conflict (id) do update set public = false, file_size_limit = 2097152, allowed_mime_types = array['image/jpeg'];

create table if not exists public.photo_donations (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  object_name text not null unique
    check (object_name ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.jpg$'),
  model_id text not null check (length(model_id) between 1 and 120),
  app_version text check (length(app_version) <= 40),
  predicted text check (length(predicted) <= 40),
  correct boolean,
  consent_version text not null check (consent_version in ('v1'))
);
comment on table public.photo_donations is
  'Opt-in donated scan photos (objects in storage bucket scan-donations). Insert-only for anon; licence: user consent v1 (app strings he.donateConsent).';

alter table public.photo_donations enable row level security;
revoke all on table public.photo_donations from anon, authenticated;
grant insert (object_name, model_id, app_version, predicted, correct, consent_version)
  on table public.photo_donations to anon, authenticated;
create policy "app can register a donation" on public.photo_donations
  for insert to anon, authenticated
  with check (created_at >= now() - interval '1 minute');

drop trigger if exists photo_donations_rate_limit on public.photo_donations;
create trigger photo_donations_rate_limit
  before insert on public.photo_donations
  for each row execute function private.enforce_feedback_rate();

-- Storage policy helper: may this object name be uploaded now? (registered, recent)
create or replace function private.donation_slot_open(p_name text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.photo_donations d
    where d.object_name = p_name and d.created_at > now() - interval '10 minutes'
  );
$$;
revoke all on function private.donation_slot_open(text) from public;
grant usage on schema private to anon, authenticated;
grant execute on function private.donation_slot_open(text) to anon, authenticated;

drop policy if exists "app can upload a registered donation" on storage.objects;
create policy "app can upload a registered donation" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'scan-donations' and private.donation_slot_open(name));
