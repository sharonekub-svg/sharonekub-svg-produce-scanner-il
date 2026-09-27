-- Rate limit for anonymous feedback inserts: <= 10 per client per minute, <= 2000 per minute total.
-- The client key is md5(secret_salt || first X-Forwarded-For IP): raw IPs are never stored, and
-- buckets older than 1 hour are deleted. Applied to produce-scanner-il on 2026-09-27
-- (as 002_feedback_rate_limit + 003_fix_rate_limit_ambiguity; this file is the combined final state).
-- Verified: 12 inserts from one IP -> 10 accepted, 2 rejected; another IP unaffected; advisors: 0 findings.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.settings (key text primary key, value text not null);
insert into private.settings (key, value)
  values ('rate_salt', encode(extensions.gen_random_bytes(32), 'hex'))
  on conflict (key) do nothing;

create table if not exists private.feedback_rate (
  bucket timestamptz not null,
  client text not null,
  n integer not null default 0,
  primary key (bucket, client)
);
create index if not exists feedback_rate_bucket_idx on private.feedback_rate (bucket);

create or replace function private.enforce_feedback_rate()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_headers json := nullif(current_setting('request.headers', true), '')::json;
  v_ip text := coalesce(nullif(trim(split_part(v_headers ->> 'x-forwarded-for', ',', 1)), ''), v_headers ->> 'x-real-ip', 'unknown');
  v_salt text := (select s.value from private.settings s where s.key = 'rate_salt');
  v_client text := md5(v_salt || v_ip);
  v_bucket timestamptz := date_trunc('minute', now());
  v_per_client integer;
  v_total integer;
begin
  insert into private.feedback_rate as r (bucket, client, n) values (v_bucket, v_client, 1)
    on conflict (bucket, client) do update set n = r.n + 1
    returning r.n into v_per_client;
  select coalesce(sum(r.n), 0) into v_total from private.feedback_rate r where r.bucket = v_bucket;
  if v_per_client > 10 or v_total > 2000 then
    raise exception 'rate limit exceeded' using errcode = 'P0001';
  end if;
  delete from private.feedback_rate r where r.bucket < now() - interval '1 hour';
  return new;
end;
$$;
revoke all on function private.enforce_feedback_rate() from public, anon, authenticated;

drop trigger if exists scan_feedback_rate_limit on public.scan_feedback;
create trigger scan_feedback_rate_limit
  before insert on public.scan_feedback
  for each row execute function private.enforce_feedback_rate();
