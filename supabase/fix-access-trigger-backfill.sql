-- IA em Loop — correção pós-deadlock Supabase
-- Rode este arquivo em blocos separados no SQL Editor.
-- A tabela public.access_requests já existe; este script evita recriar tudo.

-- BLOCO 1 — trigger seguro para criar pedido pendente ao criar usuário
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

-- BLOCO 2 — recriar trigger, se necessário
-- Se der lock/deadlock aqui, aguarde 60s e rode só este bloco novamente.
drop trigger if exists on_auth_user_created_access_request on auth.users;
create trigger on_auth_user_created_access_request
after insert on auth.users
for each row execute function public.handle_new_access_request();

-- BLOCO 3 — backfill do usuário que você já cadastrou/confirmou
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

-- BLOCO 4 — conferir pedidos
select created_at, email, full_name, status
from public.access_requests
order by created_at desc;

-- BLOCO 5 — aprovar seu usuário, depois de confirmar o e-mail certo
-- update public.access_requests
-- set status = 'approved',
--     approved_at = now(),
--     approved_by_email = 'equipeiaemloop@gmail.com',
--     updated_at = now()
-- where email = 'SEU_EMAIL_AQUI';
