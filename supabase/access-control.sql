-- IA em Loop — Supabase Auth + manual approval
-- Run in the Supabase SQL Editor before the Phase 1 portfolio schema.

begin;

create extension if not exists pgcrypto;

create table if not exists public.access_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  approved_at timestamptz,
  approved_by_email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.access_requests enable row level security;
alter table public.access_requests force row level security;

-- Auth owns request creation. Browser roles cannot create or edit approval rows.
create or replace function public.handle_new_access_request()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.access_requests (user_id, email, full_name, status)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', ''),
    'pending'
  )
  on conflict (user_id) do update
    set email = excluded.email,
        full_name = coalesce(nullif(excluded.full_name, ''), public.access_requests.full_name),
        updated_at = pg_catalog.now();
  return new;
end;
$$;

revoke all on function public.handle_new_access_request() from public;
revoke all on function public.handle_new_access_request() from anon;
revoke all on function public.handle_new_access_request() from authenticated;

drop trigger if exists on_auth_user_created_access_request on auth.users;
create trigger on_auth_user_created_access_request
after insert on auth.users
for each row execute function public.handle_new_access_request();

insert into public.access_requests (user_id, email, full_name, status)
select
  u.id,
  u.email,
  coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name', ''),
  'pending'
from auth.users as u
where not exists (
  select 1 from public.access_requests as ar where ar.user_id = u.id
);

-- Existing orphan rows are never guessed, reassigned, or deleted. Stop with a
-- count so an operator can repair them deliberately before enforcing NOT NULL.
do $access_requests_user_id_preflight$
declare
  null_user_id_count bigint;
begin
  select pg_catalog.count(*)
    into null_user_id_count
    from public.access_requests
    where user_id is null;

  if null_user_id_count > 0 then
    raise exception
      'Cannot set public.access_requests.user_id NOT NULL: % row(s) still have NULL user_id',
      null_user_id_count;
  end if;
end
$access_requests_user_id_preflight$;

alter table public.access_requests alter column user_id set not null;

-- Remove every old policy first; this prevents a rerun from preserving a stale write policy.
do $$
declare
  policy_record record;
begin
  for policy_record in
    select policyname
    from pg_catalog.pg_policies
    where schemaname = 'public' and tablename = 'access_requests'
  loop
    execute pg_catalog.format(
      'drop policy if exists %I on public.access_requests',
      policy_record.policyname
    );
  end loop;
end;
$$;

revoke all on table public.access_requests from public;
revoke all on table public.access_requests from anon;
revoke all on table public.access_requests from authenticated;
grant select on table public.access_requests to authenticated;

create policy users_read_own_access_request
  on public.access_requests
  for select to authenticated
  using ((select auth.uid()) = user_id);

-- Manual approval must run in the trusted SQL Editor and target immutable auth user ID.
-- update public.access_requests
-- set status = 'approved',
--     approved_at = pg_catalog.now(),
--     approved_by_email = 'equipeiaemloop@gmail.com',
--     updated_at = pg_catalog.now()
-- where user_id = '00000000-0000-0000-0000-000000000000'::uuid;

-- Manual rejection by immutable auth user ID:
-- update public.access_requests
-- set status = 'rejected', updated_at = pg_catalog.now()
-- where user_id = '00000000-0000-0000-0000-000000000000'::uuid;

-- Pending queue (trusted SQL Editor only):
-- select created_at, user_id, email, full_name, status
-- from public.access_requests
-- where status = 'pending'
-- order by created_at desc;

commit;
