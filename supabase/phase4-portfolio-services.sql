begin;

alter table public.portfolios
  add column if not exists strategy_key text;

alter table public.portfolios
  drop constraint if exists portfolios_strategy_key_check;

alter table public.portfolios
  add constraint portfolios_strategy_key_check
  check (strategy_key is null or strategy_key in ('besst-b3', 'magic-b3', 'besst-usd', 'magic-usd'));

alter table public.portfolios
  drop constraint if exists portfolios_strategy_currency_check;

alter table public.portfolios
  add constraint portfolios_strategy_currency_check
  check (
    strategy_key is null
    or (strategy_key in ('besst-b3', 'magic-b3') and base_currency = 'BRL')
    or (strategy_key in ('besst-usd', 'magic-usd') and base_currency = 'USD')
  );

create unique index if not exists portfolios_one_strategy_per_user_idx
  on public.portfolios (user_id, strategy_key)
  where strategy_key is not null;

comment on column public.portfolios.strategy_key is
  'Permanent IA em Loop sleeve binding used by portfolio analysis and monthly contribution planning.';

create or replace function private.enforce_portfolio_strategy_immutable()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.strategy_key is not null and new.strategy_key is distinct from old.strategy_key then
    raise exception 'strategy_key can only be assigned once';
  end if;
  return new;
end;
$$;

revoke all on function private.enforce_portfolio_strategy_immutable() from public;

drop trigger if exists portfolios_strategy_immutable on public.portfolios;
create trigger portfolios_strategy_immutable
before update of strategy_key on public.portfolios
for each row execute function private.enforce_portfolio_strategy_immutable();

create or replace function public.bind_portfolio_strategy(
  p_portfolio_id uuid,
  p_strategy_key text
)
returns public.portfolios
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := auth.uid();
  v_currency text;
  v_portfolio public.portfolios;
begin
  if v_user_id is null or not private.is_approved_user() then
    raise exception 'approved authenticated user required';
  end if;

  if p_strategy_key not in ('besst-b3', 'magic-b3', 'besst-usd', 'magic-usd') then
    raise exception 'invalid strategy_key';
  end if;

  v_currency := case when p_strategy_key in ('besst-b3', 'magic-b3') then 'BRL' else 'USD' end;

  select * into v_portfolio
  from public.portfolios
  where id = p_portfolio_id and user_id = v_user_id
  for update;

  if not found then
    raise exception 'portfolio not found';
  end if;

  if v_portfolio.strategy_key is not null then
    if v_portfolio.strategy_key <> p_strategy_key then
      raise exception 'portfolio is already bound to another strategy';
    end if;
    return v_portfolio;
  end if;

  if exists (
    select 1 from public.portfolios
    where user_id = v_user_id
      and strategy_key = p_strategy_key
      and id <> p_portfolio_id
  ) then
    raise exception 'another portfolio is already bound to this strategy';
  end if;

  update public.portfolios
  set strategy_key = p_strategy_key,
      base_currency = v_currency
  where id = p_portfolio_id
    and user_id = v_user_id
    and strategy_key is null
  returning * into v_portfolio;

  if not found then
    raise exception 'portfolio binding changed concurrently; reload and retry';
  end if;

  return v_portfolio;
end;
$$;

revoke all on function public.bind_portfolio_strategy(uuid, text) from public;
revoke all on function public.bind_portfolio_strategy(uuid, text) from anon;
grant execute on function public.bind_portfolio_strategy(uuid, text) to authenticated;

commit;
