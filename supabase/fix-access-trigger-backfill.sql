-- IA em Loop — safe access-request trigger/backfill repair
-- The table public.access_requests must already exist.

begin;

-- BLOCK 1 — hardened trigger function
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

-- BLOCK 2 — recreate trigger
-- If this block encounters a lock, wait for the conflicting transaction to finish and retry.
drop trigger if exists on_auth_user_created_access_request on auth.users;
create trigger on_auth_user_created_access_request
after insert on auth.users
for each row execute function public.handle_new_access_request();

-- BLOCK 3 — backfill existing Auth users
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

-- Never guess, attach, or delete legacy orphan rows. Fail before changing
-- policies/privileges so the transaction rolls the entire repair back.
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

-- BLOCK 4 — reset privileges and all policies to the read-only browser contract
alter table public.access_requests enable row level security;
alter table public.access_requests force row level security;

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

-- BLOCK 5 — inspect requests in the trusted SQL Editor
select created_at, user_id, email, full_name, status
from public.access_requests
order by created_at desc;

-- Approve only after confirming the immutable Auth user ID:
-- update public.access_requests
-- set status = 'approved',
--     approved_at = pg_catalog.now(),
--     approved_by_email = 'equipeiaemloop@gmail.com',
--     updated_at = pg_catalog.now()
-- where user_id = '00000000-0000-0000-0000-000000000000'::uuid;

commit;
