-- IA em Loop — Phase 3 secure administration of application access
-- Apply after supabase/access-control.sql.

begin;

create schema if not exists private;

-- Phase 3 depends on the Phase 0 access table and Auth catalog. Never create a
-- look-alike table or continue against a partial deployment.
do $phase3_catalog_preflight$
begin
  if pg_catalog.to_regclass('auth.users') is null then
    raise exception 'Phase 3 requires auth.users';
  end if;
  if pg_catalog.to_regclass('public.access_requests') is null then
    raise exception 'Phase 3 requires public.access_requests from access-control.sql';
  end if;
end
$phase3_catalog_preflight$;

alter table public.access_requests
  add column if not exists role text;

update public.access_requests
set role = 'user'
where role is null;

alter table public.access_requests
  alter column role set default 'user',
  alter column role set not null;

alter table public.access_requests
  drop constraint if exists access_requests_role_check;
alter table public.access_requests
  add constraint access_requests_role_check check (role in ('user', 'admin'));

create table if not exists private.admin_members (
  user_id uuid,
  created_at timestamptz,
  created_by uuid
);

alter table private.admin_members add column if not exists user_id uuid;
alter table private.admin_members add column if not exists created_at timestamptz;
alter table private.admin_members add column if not exists created_by uuid;

create table if not exists private.access_status_audit (
  id bigint,
  actor_user_id uuid,
  target_user_id uuid,
  previous_status text,
  new_status text,
  reason text,
  decided_at timestamptz
);

alter table private.access_status_audit add column if not exists id bigint;
alter table private.access_status_audit add column if not exists actor_user_id uuid;
alter table private.access_status_audit add column if not exists target_user_id uuid;
alter table private.access_status_audit add column if not exists previous_status text;
alter table private.access_status_audit add column if not exists new_status text;
alter table private.access_status_audit add column if not exists reason text;
alter table private.access_status_audit add column if not exists decided_at timestamptz;

-- Fail closed before tightening legacy tables. Existing rows are never deleted,
-- reassigned, or supplied with guessed security identities/statuses.
do $phase3_definition_preflight$
declare
  problem text;
begin
  select pg_catalog.string_agg(c.table_name || '.' || c.column_name || ' is ' || c.data_type, ', ')
    into problem
    from information_schema.columns as c
   where c.table_schema = 'private'
     and (
       (c.table_name = 'admin_members' and c.column_name in ('user_id', 'created_by') and c.data_type <> 'uuid')
       or (c.table_name = 'admin_members' and c.column_name = 'created_at' and c.data_type <> 'timestamp with time zone')
       or (c.table_name = 'access_status_audit' and c.column_name = 'id' and c.data_type <> 'bigint')
       or (c.table_name = 'access_status_audit' and c.column_name in ('actor_user_id', 'target_user_id') and c.data_type <> 'uuid')
       or (c.table_name = 'access_status_audit' and c.column_name in ('previous_status', 'new_status', 'reason') and c.data_type <> 'text')
       or (c.table_name = 'access_status_audit' and c.column_name = 'decided_at' and c.data_type <> 'timestamp with time zone')
     );
  if problem is not null then
    raise exception 'Phase 3 found incompatible existing column definitions: %', problem;
  end if;

  if exists (select 1 from private.admin_members where user_id is null) then
    raise exception 'Cannot reconcile private.admin_members: NULL user_id requires manual repair';
  end if;
  if exists (select 1 from private.admin_members where created_at is null) then
    raise exception 'Cannot reconcile private.admin_members: NULL created_at requires manual repair';
  end if;
  if exists (
    select user_id from private.admin_members group by user_id having pg_catalog.count(*) > 1
  ) then
    raise exception 'Cannot reconcile private.admin_members: duplicate user_id requires manual repair';
  end if;
  if exists (
    select 1 from private.admin_members as am
    left join auth.users as u on u.id = am.user_id
    where u.id is null
  ) then
    raise exception 'Cannot reconcile private.admin_members: orphan user_id requires manual repair';
  end if;
  if exists (
    select 1 from private.admin_members as am
    left join auth.users as u on u.id = am.created_by
    where am.created_by is not null and u.id is null
  ) then
    raise exception 'Cannot reconcile private.admin_members: orphan created_by requires manual repair';
  end if;

  if exists (
    select 1
      from pg_catalog.pg_constraint as c
     where c.conrelid = 'private.admin_members'::regclass
       and c.contype = 'p'
       and c.conkey <> array[(select a.attnum from pg_catalog.pg_attribute as a where a.attrelid = c.conrelid and a.attname = 'user_id')]::smallint[]
  ) then
    raise exception 'Cannot reconcile private.admin_members: conflicting primary key requires manual repair';
  end if;

  if exists (select 1 from private.access_status_audit where id is null) then
    raise exception 'Cannot reconcile private.access_status_audit: NULL id requires manual repair';
  end if;
  if exists (select id from private.access_status_audit group by id having pg_catalog.count(*) > 1) then
    raise exception 'Cannot reconcile private.access_status_audit: duplicate id requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where actor_user_id is null) then
    raise exception 'Cannot reconcile private.access_status_audit: NULL actor_user_id requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where target_user_id is null) then
    raise exception 'Cannot reconcile private.access_status_audit: NULL target_user_id requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where previous_status is null or previous_status not in ('pending', 'approved', 'rejected')) then
    raise exception 'Cannot reconcile private.access_status_audit: invalid previous_status requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where new_status is null or new_status not in ('pending', 'approved', 'rejected')) then
    raise exception 'Cannot reconcile private.access_status_audit: invalid new_status requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where previous_status = new_status) then
    raise exception 'Cannot reconcile private.access_status_audit: unchanged status rows require manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where reason is not null and pg_catalog.length(reason) > 500) then
    raise exception 'Cannot reconcile private.access_status_audit: overlong reason requires manual repair';
  end if;
  if exists (select 1 from private.access_status_audit where decided_at is null) then
    raise exception 'Cannot reconcile private.access_status_audit: NULL decided_at requires manual repair';
  end if;
  if exists (
    select 1 from private.access_status_audit as audit
    left join auth.users as u on u.id = audit.actor_user_id
    where u.id is null
  ) then
    raise exception 'Cannot reconcile private.access_status_audit: orphan actor_user_id requires manual repair';
  end if;
  if exists (
    select 1 from private.access_status_audit as audit
    left join auth.users as u on u.id = audit.target_user_id
    where u.id is null
  ) then
    raise exception 'Cannot reconcile private.access_status_audit: orphan target_user_id requires manual repair';
  end if;
  if exists (
    select 1
      from pg_catalog.pg_constraint as c
     where c.conrelid = 'private.access_status_audit'::regclass
       and c.contype = 'p'
       and c.conkey <> array[(select a.attnum from pg_catalog.pg_attribute as a where a.attrelid = c.conrelid and a.attname = 'id')]::smallint[]
  ) then
    raise exception 'Cannot reconcile private.access_status_audit: conflicting primary key requires manual repair';
  end if;
end
$phase3_definition_preflight$;

alter table private.admin_members
  alter column user_id set not null,
  alter column created_at set default pg_catalog.now(),
  alter column created_at set not null;

alter table private.access_status_audit
  alter column id set not null,
  alter column actor_user_id set not null,
  alter column target_user_id set not null,
  alter column previous_status set not null,
  alter column new_status set not null,
  alter column decided_at set default pg_catalog.now(),
  alter column decided_at set not null;

-- Reconcile an existing bigint/serial audit key to GENERATED ALWAYS identity and
-- advance its sequence beyond preserved legacy rows.
do $phase3_audit_identity_reconcile$
declare
  identity_kind "char";
  sequence_name text;
  max_id bigint;
begin
  select a.attidentity into identity_kind
    from pg_catalog.pg_attribute as a
   where a.attrelid = 'private.access_status_audit'::regclass
     and a.attname = 'id'
     and not a.attisdropped;

  if identity_kind = 'd' then
    alter table private.access_status_audit alter column id set generated always;
  elsif identity_kind = '' then
    alter table private.access_status_audit alter column id drop default;
    alter table private.access_status_audit alter column id add generated always as identity;
  end if;

  sequence_name := pg_catalog.pg_get_serial_sequence('private.access_status_audit', 'id');
  if sequence_name is null then
    raise exception 'Could not reconcile private.access_status_audit.id identity sequence';
  end if;
  select pg_catalog.max(id) into max_id from private.access_status_audit;
  if max_id is null then
    perform pg_catalog.setval(sequence_name::regclass, 1, false);
  else
    perform pg_catalog.setval(sequence_name::regclass, max_id, true);
  end if;
end
$phase3_audit_identity_reconcile$;

-- Add the required keys only when an equivalent catalog definition is absent.
do $phase3_key_reconcile$
declare
  user_id_attnum smallint;
  created_by_attnum smallint;
  audit_id_attnum smallint;
  actor_attnum smallint;
  target_attnum smallint;
  auth_id_attnum smallint;
begin
  select attnum into user_id_attnum from pg_catalog.pg_attribute where attrelid = 'private.admin_members'::regclass and attname = 'user_id';
  select attnum into created_by_attnum from pg_catalog.pg_attribute where attrelid = 'private.admin_members'::regclass and attname = 'created_by';
  select attnum into audit_id_attnum from pg_catalog.pg_attribute where attrelid = 'private.access_status_audit'::regclass and attname = 'id';
  select attnum into actor_attnum from pg_catalog.pg_attribute where attrelid = 'private.access_status_audit'::regclass and attname = 'actor_user_id';
  select attnum into target_attnum from pg_catalog.pg_attribute where attrelid = 'private.access_status_audit'::regclass and attname = 'target_user_id';
  select attnum into auth_id_attnum from pg_catalog.pg_attribute where attrelid = 'auth.users'::regclass and attname = 'id';

  if not exists (select 1 from pg_catalog.pg_constraint where conrelid = 'private.admin_members'::regclass and contype = 'p') then
    alter table private.admin_members add constraint admin_members_pkey primary key (user_id);
  end if;
  if not exists (select 1 from pg_catalog.pg_constraint where conrelid = 'private.access_status_audit'::regclass and contype = 'p') then
    alter table private.access_status_audit add constraint access_status_audit_pkey primary key (id);
  end if;

  if exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.admin_members'::regclass and contype = 'f'
       and conkey = array[user_id_attnum]::smallint[]
       and not (confrelid = 'auth.users'::regclass and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'c')
  ) then
    raise exception 'Cannot reconcile private.admin_members.user_id: conflicting foreign key requires manual repair';
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.admin_members'::regclass and contype = 'f'
       and conkey = array[user_id_attnum]::smallint[] and confrelid = 'auth.users'::regclass
       and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'c'
  ) then
    alter table private.admin_members add constraint admin_members_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade;
  end if;

  if exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.admin_members'::regclass and contype = 'f'
       and conkey = array[created_by_attnum]::smallint[]
       and not (confrelid = 'auth.users'::regclass and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'n')
  ) then
    raise exception 'Cannot reconcile private.admin_members.created_by: conflicting foreign key requires manual repair';
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.admin_members'::regclass and contype = 'f'
       and conkey = array[created_by_attnum]::smallint[] and confrelid = 'auth.users'::regclass
       and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'n'
  ) then
    alter table private.admin_members add constraint admin_members_created_by_fkey foreign key (created_by) references auth.users(id) on delete set null;
  end if;

  if exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.access_status_audit'::regclass and contype = 'f'
       and conkey in (array[actor_attnum]::smallint[], array[target_attnum]::smallint[])
       and not (confrelid = 'auth.users'::regclass and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'r')
  ) then
    raise exception 'Cannot reconcile private.access_status_audit: conflicting user foreign key requires manual repair';
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.access_status_audit'::regclass and contype = 'f'
       and conkey = array[actor_attnum]::smallint[] and confrelid = 'auth.users'::regclass
       and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'r'
  ) then
    alter table private.access_status_audit add constraint access_status_audit_actor_user_id_fkey foreign key (actor_user_id) references auth.users(id) on delete restrict;
  end if;
  if not exists (
    select 1 from pg_catalog.pg_constraint
     where conrelid = 'private.access_status_audit'::regclass and contype = 'f'
       and conkey = array[target_attnum]::smallint[] and confrelid = 'auth.users'::regclass
       and confkey = array[auth_id_attnum]::smallint[] and confdeltype = 'r'
  ) then
    alter table private.access_status_audit add constraint access_status_audit_target_user_id_fkey foreign key (target_user_id) references auth.users(id) on delete restrict;
  end if;
end
$phase3_key_reconcile$;

alter table private.access_status_audit drop constraint if exists access_status_audit_previous_status_check;
alter table private.access_status_audit add constraint access_status_audit_previous_status_check check (previous_status in ('pending', 'approved', 'rejected'));
alter table private.access_status_audit drop constraint if exists access_status_audit_new_status_check;
alter table private.access_status_audit add constraint access_status_audit_new_status_check check (new_status in ('pending', 'approved', 'rejected'));
alter table private.access_status_audit drop constraint if exists access_status_audit_status_changed_check;
alter table private.access_status_audit add constraint access_status_audit_status_changed_check check (previous_status <> new_status);
alter table private.access_status_audit drop constraint if exists access_status_audit_reason_length_check;
alter table private.access_status_audit add constraint access_status_audit_reason_length_check check (reason is null or pg_catalog.length(reason) <= 500);

drop index if exists private.phase3_admin_members_created_by_idx;
create index phase3_admin_members_created_by_idx on private.admin_members (created_by) where created_by is not null;
drop index if exists private.phase3_access_status_audit_target_decided_idx;
create index phase3_access_status_audit_target_decided_idx on private.access_status_audit (target_user_id, decided_at desc);
drop index if exists private.phase3_access_status_audit_actor_decided_idx;
create index phase3_access_status_audit_actor_decided_idx on private.access_status_audit (actor_user_id, decided_at desc);

alter table private.admin_members enable row level security;
alter table private.admin_members force row level security;
alter table private.access_status_audit enable row level security;
alter table private.access_status_audit force row level security;

-- No policy is needed: browser roles receive no table privileges and the RPCs
-- below run as their definer. Remove stale policies from prior deployments.
do $phase3_drop_private_policies$
declare
  policy_record record;
begin
  for policy_record in
    select schemaname, tablename, policyname
      from pg_catalog.pg_policies
     where schemaname = 'private'
       and tablename in ('admin_members', 'access_status_audit')
  loop
    execute pg_catalog.format('drop policy if exists %I on %I.%I', policy_record.policyname, policy_record.schemaname, policy_record.tablename);
  end loop;
end
$phase3_drop_private_policies$;

revoke all on table private.admin_members from public;
revoke all on table private.admin_members from anon;
revoke all on table private.admin_members from authenticated;
revoke all on table private.access_status_audit from public;
revoke all on table private.access_status_audit from anon;
revoke all on table private.access_status_audit from authenticated;

create or replace function private.reject_access_status_audit_mutation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception 'private.access_status_audit is append-only';
end;
$$;

revoke all on function private.reject_access_status_audit_mutation() from public;
revoke all on function private.reject_access_status_audit_mutation() from anon;
revoke all on function private.reject_access_status_audit_mutation() from authenticated;

drop trigger if exists phase3_access_status_audit_append_only on private.access_status_audit;
create trigger phase3_access_status_audit_append_only
before update or delete on private.access_status_audit
for each row execute function private.reject_access_status_audit_mutation();

drop trigger if exists phase3_access_status_audit_no_truncate on private.access_status_audit;
create trigger phase3_access_status_audit_no_truncate
before truncate on private.access_status_audit
for each statement execute function private.reject_access_status_audit_mutation();

-- Bootstrap is intentionally tied to existing Auth rows only during migration.
-- Runtime authorization and displayed roles use immutable UUID membership.
do $phase3_admin_bootstrap$
declare
  bootstrap_count bigint;
  bootstrap_user_id uuid;
  bootstrap_email text;
  bootstrap_name text;
  ordinary_count bigint;
  ordinary_user_id uuid;
  ordinary_email text;
  ordinary_name text;
begin
  select pg_catalog.count(*), pg_catalog.min(u.id::text)::uuid, pg_catalog.min(u.email),
         pg_catalog.min(coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name', ''))
    into bootstrap_count, bootstrap_user_id, bootstrap_email, bootstrap_name
    from auth.users as u
    where pg_catalog.lower(u.email) = 'diegoremmurd@gmail.com';

  if bootstrap_count <> 1 then
    raise exception 'Phase 3 bootstrap requires exactly one auth.users row for diegoremmurd@gmail.com; found %', bootstrap_count;
  end if;

  insert into private.admin_members (user_id, created_by)
  values (bootstrap_user_id, bootstrap_user_id)
  on conflict (user_id) do nothing;

  insert into public.access_requests (user_id, email, full_name, status, role, approved_at, updated_at)
  values (bootstrap_user_id, bootstrap_email, bootstrap_name, 'approved', 'admin', pg_catalog.now(), pg_catalog.now())
  on conflict (user_id) do update
    set email = excluded.email,
        full_name = coalesce(nullif(excluded.full_name, ''), public.access_requests.full_name),
        status = 'approved',
        role = 'admin',
        approved_at = coalesce(public.access_requests.approved_at, pg_catalog.now()),
        updated_at = pg_catalog.now();

  select pg_catalog.count(*), pg_catalog.min(u.id::text)::uuid, pg_catalog.min(u.email),
         pg_catalog.min(coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name', ''))
    into ordinary_count, ordinary_user_id, ordinary_email, ordinary_name
    from auth.users as u
    where pg_catalog.lower(u.email) = 'diegoremmurd@hotmail.com';

  if ordinary_count <> 1 then
    raise exception 'Phase 3 bootstrap requires exactly one auth.users row for diegoremmurd@hotmail.com; found %', ordinary_count;
  end if;

  delete from private.admin_members as am where am.user_id = ordinary_user_id;

  insert into public.access_requests (user_id, email, full_name, status, role, approved_at, updated_at)
  values (ordinary_user_id, ordinary_email, ordinary_name, 'approved', 'user', pg_catalog.now(), pg_catalog.now())
  on conflict (user_id) do update
    set email = excluded.email,
        full_name = coalesce(nullif(excluded.full_name, ''), public.access_requests.full_name),
        status = 'approved',
        role = 'user',
        approved_at = coalesce(public.access_requests.approved_at, pg_catalog.now()),
        updated_at = pg_catalog.now();

  update public.access_requests as ar
     set role = case when exists (select 1 from private.admin_members as am where am.user_id = ar.user_id) then 'admin' else 'user' end,
         updated_at = case
           when ar.role is distinct from case when exists (select 1 from private.admin_members as am where am.user_id = ar.user_id) then 'admin' else 'user' end
             then pg_catalog.now()
           else ar.updated_at
         end;
end
$phase3_admin_bootstrap$;

create or replace function public.admin_is_current_user()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select (select auth.uid()) is not null
    and exists (
      select 1 from private.admin_members as am
      where am.user_id = (select auth.uid())
    );
$$;

create or replace function public.admin_list_access_requests(
  p_status text default null,
  p_search text default null,
  p_limit integer default 50,
  p_offset integer default 0
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  caller_id uuid := (select auth.uid());
  normalized_status text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_status, 'all')));
  normalized_search text := pg_catalog.btrim(coalesce(p_search, ''));
  search_pattern text;
  bounded_limit integer;
  bounded_offset integer;
  result jsonb;
begin
  if caller_id is null or not exists (
    select 1 from private.admin_members as am where am.user_id = caller_id
  ) then
    raise exception using errcode = '42501', message = 'Administrator access required';
  end if;
  if normalized_status not in ('all', 'pending', 'approved', 'rejected') then
    raise exception using errcode = '22023', message = 'Invalid status filter';
  end if;
  if pg_catalog.length(normalized_search) > 120 then
    raise exception using errcode = '22023', message = 'Search is limited to 120 characters';
  end if;

  bounded_limit := least(greatest(coalesce(p_limit, 50), 1), 200);
  bounded_offset := greatest(coalesce(p_offset, 0), 0);
  search_pattern := '%' || pg_catalog.replace(pg_catalog.replace(pg_catalog.replace(
    normalized_search, pg_catalog.chr(92), pg_catalog.chr(92) || pg_catalog.chr(92)
  ), '%', pg_catalog.chr(92) || '%'), '_', pg_catalog.chr(92) || '_') || '%';

  with filtered as (
    select
      ar.user_id,
      u.email::text as email,
      ar.full_name,
      ar.status,
      case when am.user_id is not null then 'admin'::text else 'user'::text end as role,
      ar.approved_at,
      ar.created_at,
      ar.updated_at,
      u.last_sign_in_at
    from public.access_requests as ar
    join auth.users as u on u.id = ar.user_id
    left join private.admin_members as am on am.user_id = ar.user_id
    where (normalized_status = 'all' or ar.status = normalized_status)
      and (
        normalized_search = ''
        or coalesce(u.email, '') ilike search_pattern escape pg_catalog.chr(92)
        or coalesce(ar.full_name, '') ilike search_pattern escape pg_catalog.chr(92)
      )
  ), page_rows as (
    select * from filtered
    order by case status when 'pending' then 0 when 'approved' then 1 else 2 end, created_at desc, user_id
    limit bounded_limit offset bounded_offset
  ), counts as (
    select
      pg_catalog.count(*) filter (where requests.status = 'pending') as pending_count,
      pg_catalog.count(*) filter (where requests.status = 'approved') as approved_count,
      pg_catalog.count(*) filter (where requests.status = 'rejected') as rejected_count,
      pg_catalog.count(*) as total_count
    from public.access_requests as requests
  )
  select pg_catalog.jsonb_build_object(
    'items', coalesce((select pg_catalog.jsonb_agg(pg_catalog.to_jsonb(page_rows) order by case status when 'pending' then 0 when 'approved' then 1 else 2 end, created_at desc, user_id) from page_rows), '[]'::jsonb),
    'filtered_count', (select pg_catalog.count(*) from filtered),
    'counts', pg_catalog.jsonb_build_object(
      'pending', counts.pending_count,
      'approved', counts.approved_count,
      'rejected', counts.rejected_count,
      'total', counts.total_count
    )
  ) into result
  from counts;

  return result;
end;
$$;

create or replace function public.admin_set_access_status(
  p_target_user_id uuid,
  p_expected_status text,
  p_new_status text,
  p_reason text default null
)
returns table (
  user_id uuid,
  email text,
  full_name text,
  status text,
  role text,
  approved_at timestamptz,
  created_at timestamptz,
  updated_at timestamptz,
  last_sign_in_at timestamptz
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  caller_id uuid := (select auth.uid());
  current_status text;
  normalized_expected text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_expected_status, '')));
  normalized_new text := pg_catalog.lower(pg_catalog.btrim(coalesce(p_new_status, '')));
  normalized_reason text := nullif(pg_catalog.btrim(coalesce(p_reason, '')), '');
  affected_rows integer;
begin
  if caller_id is null or not exists (
    select 1 from private.admin_members as am where am.user_id = caller_id
  ) then
    raise exception using errcode = '42501', message = 'Administrator access required';
  end if;
  if p_target_user_id is null then
    raise exception using errcode = '22023', message = 'Target user UUID is required';
  end if;
  if p_target_user_id = caller_id then
    raise exception using errcode = '42501', message = 'Administrators cannot modify their own access';
  end if;
  if exists (select 1 from private.admin_members as am where am.user_id = p_target_user_id) then
    raise exception using errcode = '42501', message = 'Administrator targets cannot be modified here';
  end if;
  if normalized_expected not in ('pending', 'approved', 'rejected') or normalized_new not in ('pending', 'approved', 'rejected') then
    raise exception using errcode = '22023', message = 'Invalid access status';
  end if;
  if normalized_expected = normalized_new then
    raise exception using errcode = '22023', message = 'New status must differ from expected status';
  end if;
  if normalized_reason is not null and pg_catalog.length(normalized_reason) > 500 then
    raise exception using errcode = '22023', message = 'Reason is limited to 500 characters';
  end if;

  select ar.status into current_status
    from public.access_requests as ar
    where ar.user_id = p_target_user_id
    for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'Access request not found';
  end if;
  if current_status <> normalized_expected then
    raise exception using errcode = '40001', message = 'Access request changed; reload before deciding';
  end if;

  update public.access_requests as ar
     set status = normalized_new,
         role = 'user',
         approved_at = case when normalized_new = 'approved' then pg_catalog.now() else null end,
         approved_by_email = null,
         updated_at = pg_catalog.now()
   where ar.user_id = p_target_user_id and ar.status = normalized_expected;
  get diagnostics affected_rows = row_count;
  if affected_rows <> 1 then
    raise exception using errcode = '40001', message = 'Access request changed; reload before deciding';
  end if;

  insert into private.access_status_audit (actor_user_id, target_user_id, previous_status, new_status, reason)
  values (caller_id, p_target_user_id, normalized_expected, normalized_new, normalized_reason);

  return query
  select ar.user_id, u.email::text, ar.full_name, ar.status,
         case when am.user_id is not null then 'admin'::text else 'user'::text end,
         ar.approved_at, ar.created_at, ar.updated_at, u.last_sign_in_at
    from public.access_requests as ar
    join auth.users as u on u.id = ar.user_id
    left join private.admin_members as am on am.user_id = ar.user_id
   where ar.user_id = p_target_user_id;
end;
$$;

revoke all on function public.admin_is_current_user() from public;
revoke all on function public.admin_is_current_user() from anon;
revoke all on function public.admin_is_current_user() from authenticated;
grant execute on function public.admin_is_current_user() to authenticated;

revoke all on function public.admin_list_access_requests(text, text, integer, integer) from public;
revoke all on function public.admin_list_access_requests(text, text, integer, integer) from anon;
revoke all on function public.admin_list_access_requests(text, text, integer, integer) from authenticated;
grant execute on function public.admin_list_access_requests(text, text, integer, integer) to authenticated;

revoke all on function public.admin_set_access_status(uuid, text, text, text) from public;
revoke all on function public.admin_set_access_status(uuid, text, text, text) from anon;
revoke all on function public.admin_set_access_status(uuid, text, text, text) from authenticated;
grant execute on function public.admin_set_access_status(uuid, text, text, text) to authenticated;

commit;
