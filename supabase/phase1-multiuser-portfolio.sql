-- IA em Loop — Phase 1 private multi-user portfolio schema
-- Run after supabase/access-control.sql.

begin;

create schema if not exists private;
revoke all on schema private from public;
revoke all on schema private from anon;
revoke all on schema private from authenticated;
grant usage on schema private to authenticated;

create or replace function private.is_approved_user()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.access_requests as ar
    where ar.user_id = (select auth.uid())
      and ar.status = 'approved'
  );
$$;

revoke all on function private.is_approved_user() from public;
revoke all on function private.is_approved_user() from anon;
revoke all on function private.is_approved_user() from authenticated;
grant execute on function private.is_approved_user() to authenticated;

create table if not exists public.portfolios (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (length(btrim(name)) between 1 and 120),
  base_currency text not null default 'BRL' check (base_currency ~ '^[A-Z]{3}$'),
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, id),
  unique (user_id, name)
);

create table if not exists public.portfolio_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  name text not null check (length(btrim(name)) between 1 and 120),
  institution text,
  account_type text not null default 'brokerage' check (account_type in ('brokerage', 'bank', 'retirement', 'crypto', 'other')),
  currency text not null default 'BRL' check (currency ~ '^[A-Z]{3}$'),
  cash_balance numeric(20, 6) not null default 0 check (cash_balance >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, id),
  unique (user_id, portfolio_id, id),
  unique (user_id, portfolio_id, name),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade
);

create table if not exists public.holdings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  account_id uuid not null,
  symbol text not null check (length(btrim(symbol)) between 1 and 32),
  asset_type text not null default 'equity' check (asset_type in ('equity', 'fund', 'fixed_income', 'crypto', 'cash', 'other')),
  quantity numeric(28, 10) not null check (quantity > 0),
  average_cost numeric(20, 6) not null check (average_cost >= 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  acquired_at date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, id),
  unique (user_id, account_id, symbol),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade,
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade
);

create table if not exists public.portfolio_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  account_id uuid not null,
  transaction_type text not null check (transaction_type in ('buy', 'sell', 'dividend', 'interest', 'deposit', 'withdrawal', 'fee', 'tax')),
  symbol text,
  quantity numeric(28, 10) check (quantity > 0),
  unit_price numeric(20, 6) check (unit_price > 0),
  amount numeric(20, 6) not null check (amount <> 0),
  fees numeric(20, 6) not null default 0 check (fees >= 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  occurred_at timestamptz not null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, id),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade,
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade,
  constraint portfolio_transactions_trade_fields_check check (
    transaction_type not in ('buy', 'sell')
    or (
      symbol is not null
      and length(btrim(symbol)) between 1 and 32
      and quantity is not null
      and quantity > 0
      and unit_price is not null
      and unit_price > 0
    )
  )
);

create table if not exists public.portfolio_documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  account_id uuid,
  storage_path text not null check (storage_path like user_id::text || '/%'),
  original_filename text not null check (length(btrim(original_filename)) between 1 and 255),
  mime_type text not null check (mime_type in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')),
  file_size_bytes bigint not null check (file_size_bytes > 0 and file_size_bytes <= 10485760),
  document_type text not null default 'other' check (document_type in ('broker_note', 'statement', 'tax', 'receipt', 'other')),
  uploaded_at timestamptz not null default now(),
  unique (user_id, id),
  unique (user_id, portfolio_id, id),
  unique (user_id, storage_path),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade,
  -- PostgreSQL 15+ supports a column list for SET NULL. Only the nullable
  -- account_id is cleared, preserving the document's owner and portfolio.
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete set null (account_id)
);

create table if not exists public.portfolio_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  document_id uuid,
  analysis_type text not null check (analysis_type in ('allocation', 'risk', 'performance', 'document', 'other')),
  status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
  result jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (user_id, id),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade,
  foreign key (user_id, portfolio_id, document_id) references public.portfolio_documents(user_id, portfolio_id, id) on delete set null (document_id),
  check ((status = 'completed' and result is not null) or status <> 'completed')
);

create table if not exists public.contribution_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  portfolio_id uuid not null,
  name text not null check (length(btrim(name)) between 1 and 120),
  amount numeric(20, 6) not null check (amount > 0),
  currency text not null check (currency ~ '^[A-Z]{3}$'),
  frequency text not null check (frequency in ('weekly', 'monthly', 'quarterly', 'yearly')),
  day_of_month smallint check (day_of_month between 1 and 28),
  active boolean not null default true,
  next_contribution_on date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, id),
  unique (user_id, portfolio_id, name),
  foreign key (user_id, portfolio_id) references public.portfolios(user_id, id) on delete cascade
);

-- Centralized timestamp maintenance. The function is private, has no ambient
-- search path, and cannot be invoked directly by browser roles.
create or replace function private.set_updated_at()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.updated_at := pg_catalog.now();
  return new;
end;
$$;

revoke all on function private.set_updated_at() from public;
revoke all on function private.set_updated_at() from anon;
revoke all on function private.set_updated_at() from authenticated;

drop trigger if exists phase1_set_updated_at on public.portfolios;
create trigger phase1_set_updated_at before update on public.portfolios
for each row execute function private.set_updated_at();
drop trigger if exists phase1_set_updated_at on public.portfolio_accounts;
create trigger phase1_set_updated_at before update on public.portfolio_accounts
for each row execute function private.set_updated_at();
drop trigger if exists phase1_set_updated_at on public.holdings;
create trigger phase1_set_updated_at before update on public.holdings
for each row execute function private.set_updated_at();
drop trigger if exists phase1_set_updated_at on public.portfolio_transactions;
create trigger phase1_set_updated_at before update on public.portfolio_transactions
for each row execute function private.set_updated_at();
drop trigger if exists phase1_set_updated_at on public.contribution_plans;
create trigger phase1_set_updated_at before update on public.contribution_plans
for each row execute function private.set_updated_at();

-- Reconcile constraints on reruns as well as fresh databases. Earlier Phase 1
-- drafts used owner/account pairs, so remove both legacy and current FK names
-- before rebuilding the candidate keys and portfolio-bound triple FKs.
-- Fail closed before replacing the trade-fields constraint: CHECK constraints
-- accept NULL/unknown, so every BUY/SELL predicate is tested explicitly.
do $phase1_trade_fields_preflight$
declare
  invalid_trade_count bigint;
begin
  select pg_catalog.count(*)
    into invalid_trade_count
    from public.portfolio_transactions
   where transaction_type in ('buy', 'sell')
     and (
       symbol is null
       or length(btrim(symbol)) not between 1 and 32
       or quantity is null
       or quantity <= 0
       or unit_price is null
       or unit_price <= 0
     );

  if invalid_trade_count > 0 then
    raise exception 'cannot enforce public.portfolio_transactions BUY/SELL integrity: % legacy row(s) require a nonempty symbol, quantity > 0, and unit_price > 0',
      invalid_trade_count;
  end if;
end;
$phase1_trade_fields_preflight$;

alter table public.portfolio_transactions drop constraint if exists portfolio_transactions_check;
alter table public.portfolio_transactions drop constraint if exists portfolio_transactions_trade_fields_check;
alter table public.portfolio_transactions
  add constraint portfolio_transactions_trade_fields_check check (
    transaction_type not in ('buy', 'sell')
    or (
      symbol is not null
      and length(btrim(symbol)) between 1 and 32
      and quantity is not null
      and quantity > 0
      and unit_price is not null
      and unit_price > 0
    )
  ) not valid;
alter table public.portfolio_transactions validate constraint portfolio_transactions_trade_fields_check;

alter table public.holdings drop constraint if exists holdings_user_id_account_id_fkey;
alter table public.holdings drop constraint if exists holdings_user_id_portfolio_id_account_id_fkey;
alter table public.portfolio_transactions drop constraint if exists portfolio_transactions_user_id_account_id_fkey;
alter table public.portfolio_transactions drop constraint if exists portfolio_transactions_user_id_portfolio_id_account_id_fkey;
alter table public.portfolio_documents drop constraint if exists portfolio_documents_user_id_account_id_fkey;
alter table public.portfolio_documents drop constraint if exists portfolio_documents_user_id_portfolio_id_account_id_fkey;
alter table public.portfolio_analyses drop constraint if exists portfolio_analyses_user_id_document_id_fkey;
alter table public.portfolio_analyses drop constraint if exists portfolio_analyses_user_id_portfolio_id_document_id_fkey;

alter table public.portfolio_accounts drop constraint if exists portfolio_accounts_user_id_portfolio_id_id_key;
alter table public.portfolio_documents drop constraint if exists portfolio_documents_user_id_portfolio_id_id_key;
alter table public.portfolio_accounts add constraint portfolio_accounts_user_id_portfolio_id_id_key unique (user_id, portfolio_id, id);
alter table public.portfolio_documents add constraint portfolio_documents_user_id_portfolio_id_id_key unique (user_id, portfolio_id, id);

alter table public.holdings add constraint holdings_user_id_portfolio_id_account_id_fkey
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade;
alter table public.portfolio_transactions add constraint portfolio_transactions_user_id_portfolio_id_account_id_fkey
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete cascade;
alter table public.portfolio_documents add constraint portfolio_documents_user_id_portfolio_id_account_id_fkey
  foreign key (user_id, portfolio_id, account_id) references public.portfolio_accounts(user_id, portfolio_id, id) on delete set null (account_id);
alter table public.portfolio_analyses add constraint portfolio_analyses_user_id_portfolio_id_document_id_fkey
  foreign key (user_id, portfolio_id, document_id) references public.portfolio_documents(user_id, portfolio_id, id) on delete set null (document_id);

create index if not exists portfolios_user_id_created_at_idx on public.portfolios (user_id, created_at desc);
create index if not exists portfolio_accounts_user_id_portfolio_id_idx on public.portfolio_accounts (user_id, portfolio_id);
create index if not exists holdings_user_id_portfolio_id_idx on public.holdings (user_id, portfolio_id);
create index if not exists portfolio_transactions_user_id_portfolio_occurred_idx on public.portfolio_transactions (user_id, portfolio_id, occurred_at desc);
create index if not exists portfolio_documents_user_id_portfolio_uploaded_idx on public.portfolio_documents (user_id, portfolio_id, uploaded_at desc);
create index if not exists portfolio_analyses_user_id_portfolio_created_idx on public.portfolio_analyses (user_id, portfolio_id, created_at desc);
create index if not exists contribution_plans_user_id_portfolio_active_idx on public.contribution_plans (user_id, portfolio_id, active);

-- Reset privileges explicitly before granting the browser role only its RLS-gated DML.
revoke all on table public.portfolios from public;
revoke all on table public.portfolios from anon;
revoke all on table public.portfolios from authenticated;
grant select, insert, update, delete on table public.portfolios to authenticated;
revoke all on table public.portfolio_accounts from public;
revoke all on table public.portfolio_accounts from anon;
revoke all on table public.portfolio_accounts from authenticated;
grant select, insert, update, delete on table public.portfolio_accounts to authenticated;
revoke all on table public.holdings from public;
revoke all on table public.holdings from anon;
revoke all on table public.holdings from authenticated;
grant select, insert, update, delete on table public.holdings to authenticated;
revoke all on table public.portfolio_transactions from public;
revoke all on table public.portfolio_transactions from anon;
revoke all on table public.portfolio_transactions from authenticated;
grant select, insert, update, delete on table public.portfolio_transactions to authenticated;
revoke all on table public.portfolio_documents from public;
revoke all on table public.portfolio_documents from anon;
revoke all on table public.portfolio_documents from authenticated;
grant select, insert, update, delete on table public.portfolio_documents to authenticated;
revoke all on table public.portfolio_analyses from public;
revoke all on table public.portfolio_analyses from anon;
revoke all on table public.portfolio_analyses from authenticated;
grant select, insert, update, delete on table public.portfolio_analyses to authenticated;
revoke all on table public.contribution_plans from public;
revoke all on table public.contribution_plans from anon;
revoke all on table public.contribution_plans from authenticated;
grant select, insert, update, delete on table public.contribution_plans to authenticated;

alter table public.portfolios enable row level security;
alter table public.portfolios force row level security;
alter table public.portfolio_accounts enable row level security;
alter table public.portfolio_accounts force row level security;
alter table public.holdings enable row level security;
alter table public.holdings force row level security;
alter table public.portfolio_transactions enable row level security;
alter table public.portfolio_transactions force row level security;
alter table public.portfolio_documents enable row level security;
alter table public.portfolio_documents force row level security;
alter table public.portfolio_analyses enable row level security;
alter table public.portfolio_analyses force row level security;
alter table public.contribution_plans enable row level security;
alter table public.contribution_plans force row level security;

-- Remove every pre-existing policy from the seven financial tables before
-- rebuilding the exact Phase 1 policy set. This prevents stale permissive
-- policies (including policies from older migration revisions) from surviving.
do $phase1_financial_policy_sweep$
declare
  target_table text;
  existing_policy text;
begin
  foreach target_table in array array[
    'portfolios',
    'portfolio_accounts',
    'holdings',
    'portfolio_transactions',
    'portfolio_documents',
    'portfolio_analyses',
    'contribution_plans'
  ]
  loop
    for existing_policy in
      select policyname
      from pg_catalog.pg_policies
      where schemaname = 'public'
        and tablename = target_table
    loop
      execute format('drop policy if exists %I on public.%I', existing_policy, target_table);
    end loop;
  end loop;
end
$phase1_financial_policy_sweep$;

-- Legacy names are also listed explicitly for readability and idempotency.
drop policy if exists portfolios_select_own_approved on public.portfolios;
drop policy if exists portfolios_insert_own_approved on public.portfolios;
drop policy if exists portfolios_update_own_approved on public.portfolios;
drop policy if exists portfolios_delete_own_approved on public.portfolios;
create policy phase1_portfolios_select_own_approved on public.portfolios for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolios_insert_own_approved on public.portfolios for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolios_update_own_approved on public.portfolios for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolios_delete_own_approved on public.portfolios for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists portfolio_accounts_select_own_approved on public.portfolio_accounts;
drop policy if exists portfolio_accounts_insert_own_approved on public.portfolio_accounts;
drop policy if exists portfolio_accounts_update_own_approved on public.portfolio_accounts;
drop policy if exists portfolio_accounts_delete_own_approved on public.portfolio_accounts;
create policy phase1_portfolio_accounts_select_own_approved on public.portfolio_accounts for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_accounts_insert_own_approved on public.portfolio_accounts for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_accounts_update_own_approved on public.portfolio_accounts for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_accounts_delete_own_approved on public.portfolio_accounts for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists holdings_select_own_approved on public.holdings;
drop policy if exists holdings_insert_own_approved on public.holdings;
drop policy if exists holdings_update_own_approved on public.holdings;
drop policy if exists holdings_delete_own_approved on public.holdings;
create policy phase1_holdings_select_own_approved on public.holdings for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_holdings_insert_own_approved on public.holdings for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_holdings_update_own_approved on public.holdings for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_holdings_delete_own_approved on public.holdings for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists portfolio_transactions_select_own_approved on public.portfolio_transactions;
drop policy if exists portfolio_transactions_insert_own_approved on public.portfolio_transactions;
drop policy if exists portfolio_transactions_update_own_approved on public.portfolio_transactions;
drop policy if exists portfolio_transactions_delete_own_approved on public.portfolio_transactions;
create policy phase1_portfolio_transactions_select_own_approved on public.portfolio_transactions for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_transactions_insert_own_approved on public.portfolio_transactions for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_transactions_update_own_approved on public.portfolio_transactions for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_transactions_delete_own_approved on public.portfolio_transactions for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists portfolio_documents_select_own_approved on public.portfolio_documents;
drop policy if exists portfolio_documents_insert_own_approved on public.portfolio_documents;
drop policy if exists portfolio_documents_update_own_approved on public.portfolio_documents;
drop policy if exists portfolio_documents_delete_own_approved on public.portfolio_documents;
create policy phase1_portfolio_documents_select_own_approved on public.portfolio_documents for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_documents_insert_own_approved on public.portfolio_documents for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_documents_update_own_approved on public.portfolio_documents for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_documents_delete_own_approved on public.portfolio_documents for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists portfolio_analyses_select_own_approved on public.portfolio_analyses;
drop policy if exists portfolio_analyses_insert_own_approved on public.portfolio_analyses;
drop policy if exists portfolio_analyses_update_own_approved on public.portfolio_analyses;
drop policy if exists portfolio_analyses_delete_own_approved on public.portfolio_analyses;
create policy phase1_portfolio_analyses_select_own_approved on public.portfolio_analyses for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_analyses_insert_own_approved on public.portfolio_analyses for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_analyses_update_own_approved on public.portfolio_analyses for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_portfolio_analyses_delete_own_approved on public.portfolio_analyses for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

drop policy if exists contribution_plans_select_own_approved on public.contribution_plans;
drop policy if exists contribution_plans_insert_own_approved on public.contribution_plans;
drop policy if exists contribution_plans_update_own_approved on public.contribution_plans;
drop policy if exists contribution_plans_delete_own_approved on public.contribution_plans;
create policy phase1_contribution_plans_select_own_approved on public.contribution_plans for select to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_contribution_plans_insert_own_approved on public.contribution_plans for insert to authenticated with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_contribution_plans_update_own_approved on public.contribution_plans for update to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id) with check (private.is_approved_user() and (select auth.uid()) = user_id);
create policy phase1_contribution_plans_delete_own_approved on public.contribution_plans for delete to authenticated using (private.is_approved_user() and (select auth.uid()) = user_id);

-- Fail the migration if the sweep/rebuild did not leave exactly the owned set.
do $phase1_financial_policy_assertion$
declare
  target_table text;
  policy_count integer;
  unexpected_policies text;
begin
  foreach target_table in array array[
    'portfolios',
    'portfolio_accounts',
    'holdings',
    'portfolio_transactions',
    'portfolio_documents',
    'portfolio_analyses',
    'contribution_plans'
  ]
  loop
    select count(*)
      into policy_count
      from pg_catalog.pg_policies
      where schemaname = 'public'
        and tablename = target_table;

    select pg_catalog.string_agg(
             pg_catalog.format('%I[%s,%s]', policyname, cmd, permissive),
             ', ' order by policyname
           )
      into unexpected_policies
      from pg_catalog.pg_policies
      where schemaname = 'public'
        and tablename = target_table
        and (
          policyname <> pg_catalog.format('phase1_%s_%s_own_approved', target_table, pg_catalog.lower(cmd))
          or cmd not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
          or permissive <> 'PERMISSIVE'
          or roles <> array['authenticated']::name[]
        );

    if policy_count <> 4 or unexpected_policies is not null then
      raise exception 'Unexpected RLS policy set on public.% (count=%, unexpected=%)',
        target_table,
        policy_count,
        pg_catalog.coalesce(unexpected_policies, '<none>');
    end if;
  end loop;
end
$phase1_financial_policy_assertion$;

-- Private storage: 10 MiB, supported statement/receipt formats only.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'user-documents',
  'user-documents',
  false,
  10485760,
  array['application/pdf', 'image/jpeg', 'image/png', 'image/webp']::text[]
)
on conflict (id) do update
set name = excluded.name,
    public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- Sweep only this migration's namespace so unrelated bucket policies remain
-- untouched. Restrictive guards below make broad permissive policies harmless
-- for user-documents while evaluating TRUE for every other bucket.
do $phase1_storage_policy_sweep$
declare
  existing_policy text;
begin
  for existing_policy in
    select policyname
    from pg_catalog.pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname like 'phase1_user_documents_%'
  loop
    execute format('drop policy if exists %I on storage.objects', existing_policy);
  end loop;
end
$phase1_storage_policy_sweep$;

drop policy if exists user_documents_select_own_path on storage.objects;
drop policy if exists user_documents_insert_own_path on storage.objects;
drop policy if exists user_documents_update_own_path on storage.objects;
drop policy if exists user_documents_delete_own_path on storage.objects;
create policy phase1_user_documents_select_own_path on storage.objects for select to authenticated using (private.is_approved_user() and bucket_id = 'user-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy phase1_user_documents_insert_own_path on storage.objects for insert to authenticated with check (private.is_approved_user() and bucket_id = 'user-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy phase1_user_documents_update_own_path on storage.objects for update to authenticated using (private.is_approved_user() and bucket_id = 'user-documents' and (storage.foldername(name))[1] = (select auth.uid())::text) with check (private.is_approved_user() and bucket_id = 'user-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy phase1_user_documents_delete_own_path on storage.objects for delete to authenticated using (private.is_approved_user() and bucket_id = 'user-documents' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy phase1_user_documents_guard_select on storage.objects as restrictive for select to authenticated
using (bucket_id <> 'user-documents' or (private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text));
create policy phase1_user_documents_guard_insert on storage.objects as restrictive for insert to authenticated
with check (bucket_id <> 'user-documents' or (private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text));
create policy phase1_user_documents_guard_update on storage.objects as restrictive for update to authenticated
using (bucket_id <> 'user-documents' or (private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text))
with check (bucket_id <> 'user-documents' or (private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text));
create policy phase1_user_documents_guard_delete on storage.objects as restrictive for delete to authenticated
using (bucket_id <> 'user-documents' or (private.is_approved_user() and (storage.foldername(name))[1] = (select auth.uid())::text));

-- Anonymous callers must never reach the private bucket, even if another
-- migration has installed a broad permissive policy for anon or PUBLIC.
-- These guards deliberately evaluate TRUE for unrelated buckets.
create policy phase1_user_documents_anon_guard_select on storage.objects as restrictive for select to anon
using (bucket_id <> 'user-documents');
create policy phase1_user_documents_anon_guard_insert on storage.objects as restrictive for insert to anon
with check (bucket_id <> 'user-documents');
create policy phase1_user_documents_anon_guard_update on storage.objects as restrictive for update to anon
using (bucket_id <> 'user-documents')
with check (bucket_id <> 'user-documents');
create policy phase1_user_documents_anon_guard_delete on storage.objects as restrictive for delete to anon
using (bucket_id <> 'user-documents');

commit;
