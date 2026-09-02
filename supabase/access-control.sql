-- IA em Loop — Supabase Auth + aprovação manual
-- Rode no Supabase SQL Editor depois de criar o projeto grátis.

create extension if not exists pgcrypto;

create table if not exists public.access_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  approved_at timestamptz,
  approved_by_email text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.access_requests enable row level security;

-- Cria automaticamente o pedido pendente quando um usuário nasce no Auth.
-- Isso evita erro de RLS no front-end durante cadastro/confirmacao de e-mail.
create or replace function public.handle_new_access_request()
returns trigger
language plpgsql
security definer
set search_path = public
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
        updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_access_request on auth.users;
create trigger on_auth_user_created_access_request
after insert on auth.users
for each row execute function public.handle_new_access_request();

-- Backfill: cria pedido para usuários já cadastrados antes deste trigger.
insert into public.access_requests (user_id, email, full_name, status)
select
  u.id,
  u.email,
  coalesce(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name', ''),
  'pending'
from auth.users u
where not exists (
  select 1 from public.access_requests ar where ar.user_id = u.id
);

-- O usuário pode ver apenas o próprio pedido.
drop policy if exists "users_read_own_access_request" on public.access_requests;
create policy "users_read_own_access_request"
  on public.access_requests
  for select
  using (auth.uid() = user_id);

-- O usuário autenticado pode criar/atualizar apenas o próprio pedido pendente.
drop policy if exists "users_insert_own_access_request" on public.access_requests;
create policy "users_insert_own_access_request"
  on public.access_requests
  for insert
  with check (auth.uid() = user_id and status = 'pending');

drop policy if exists "users_update_own_pending_access_request" on public.access_requests;
create policy "users_update_own_pending_access_request"
  on public.access_requests
  for update
  using (auth.uid() = user_id and status = 'pending')
  with check (auth.uid() = user_id and status = 'pending');

-- Aprovação manual: execute no SQL Editor após conferir o pedido.
-- Troque o e-mail abaixo pelo e-mail aprovado.
-- update public.access_requests
-- set status = 'approved', approved_at = now(), approved_by_email = 'equipeiaemloop@gmail.com', updated_at = now()
-- where email = 'SEU_EMAIL_AQUI';

-- Rejeição manual:
-- update public.access_requests
-- set status = 'rejected', updated_at = now()
-- where email = 'EMAIL_REJEITADO_AQUI';

-- Lista de pedidos pendentes:
-- select created_at, email, full_name, status from public.access_requests order by created_at desc;
