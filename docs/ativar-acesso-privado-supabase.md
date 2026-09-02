# IA em Loop — ativar acesso privado grátis

Sistema já implementado no front-end do site:

- Login com Supabase Auth.
- Cadastro com senha.
- Recuperação de senha via Supabase.
- Pedido de cadastro salvo como `pending` por trigger seguro em `auth.users`.
- Notificação do pedido para `equipeiaemloop@gmail.com` via FormSubmit; na primeira vez, o FormSubmit pode exigir ativação no próprio e-mail.
- Acesso privado só passa se `access_requests.status = 'approved'`.

## 1. Criar projeto Supabase grátis

1. Abrir https://supabase.com/
2. Criar projeto no plano Free.
3. Em Authentication → Providers, deixar Email habilitado.
4. Em Authentication → URL Configuration:
   - Site URL: `https://iaemloop.com.br`
   - Redirect URLs:
     - `https://iaemloop.com.br/area_privada.html`
     - `https://iaemloop.com.br/privado/*`

## 2. Criar tabela e regras

No Supabase → SQL Editor, rodar:

```sql
-- conteúdo em supabase/access-control.sql
```

Ou copiar/colar o arquivo:

```text
supabase/access-control.sql
```

## 3. Preencher configuração pública

Editar:

```text
js/iaemloop-auth-config.js
```

Preencher:

```js
supabaseUrl: "https://SEU-PROJETO.supabase.co",
supabaseAnonKey: "SUA_ANON_PUBLIC_KEY",
```

A anon public key é pública por design. Não colocar service_role key no site.

## 4. Criar primeiro usuário Diego

1. Abrir `https://iaemloop.com.br/area_privada.html`.
2. Ir em `Cadastro`.
3. Informar nome, e-mail e senha.
4. Confirmar o e-mail recebido do Supabase.
5. O pedido chega em `equipeiaemloop@gmail.com`.

## 5. Aprovar manualmente

No Supabase SQL Editor:

```sql
select created_at, email, full_name, status
from public.access_requests
order by created_at desc;
```

Aprovar Diego:

```sql
update public.access_requests
set status = 'approved',
    approved_at = now(),
    approved_by_email = 'equipeiaemloop@gmail.com',
    updated_at = now()
where email = 'EMAIL_DO_DIEGO';
```

Após isso, o login passa a liberar as rotas:

- `/privado/carteira_besst.html`
- `/privado/carteira_magic_formula.html`
- `/privado/carteira_besst_dolarizada.html`
- `/privado/carteira_magic_formula_dolarizada.html`

## 6. E-mail após aprovação

Sem backend pago, a confirmação de aprovação pode ser feita de duas formas:

1. Manualmente, respondendo o e-mail do pedido.
2. Próxima fase: Supabase Edge Function + Resend free tier para disparo automático quando `status` mudar para `approved`.

Não usar apenas JavaScript público para aprovar usuários, porque isso permitiria fraude.

## Segurança

- As páginas públicas/translúcidas não contêm dados reais.
- As rotas `/privado` criadas agora também não contêm custódia real em HTML público.
- Antes de publicar dados reais, eles devem vir de Supabase Storage/Database com RLS ou Cloudflare Access.
- Nunca publicar `service_role` no GitHub Pages.
