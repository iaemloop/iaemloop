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
