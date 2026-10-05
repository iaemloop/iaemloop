# IA em Loop — ativar acesso privado no Supabase

Este procedimento publica a Fase 1 da **Minha Carteira**: autenticação, aprovação manual por UUID, carteiras, contas, posições e movimentações isoladas por usuário com RLS.

## 1. Preparar o projeto

1. Crie ou abra o projeto Supabase correto.
2. Em **Authentication → Providers**, mantenha Email habilitado.
3. Em **Authentication → URL Configuration**, configure:
   - Site URL: `https://iaemloop.com.br`
   - Redirect URLs: `https://iaemloop.com.br/area_privada.html` e `https://iaemloop.com.br/privado/*`
4. Faça backup antes de aplicar as migrações em um projeto que já possua dados.

## 2. Aplicar as migrações na ordem segura

No SQL Editor, execute cada arquivo inteiro e aguarde o `COMMIT` antes do próximo:

1. `supabase/access-control.sql`
2. `supabase/phase1-multiuser-portfolio.sql`

`access-control.sql` cria/reconcilia `public.access_requests`, o trigger de cadastro e a leitura da própria solicitação. A migração `phase1-multiuser-portfolio.sql` depende disso para criar as tabelas financeiras, chaves compostas, RLS e o bucket privado.

Use `supabase/fix-access-trigger-backfill.sql` somente para reparar uma instalação anterior do controle de acesso. Se usado, execute-o **antes** de `phase1-multiuser-portfolio.sql`; ele não substitui a migração da Fase 1.

## 3. Configurar apenas a chave pública do navegador

Edite `js/iaemloop-auth-config.js` com a URL do mesmo projeto e uma chave **anon/publishable** completa:

```js
supabaseUrl: "https://SEU-PROJETO.supabase.co",
supabaseAnonKey: "SUA_CHAVE_PUBLICA_COMPLETA",
```

Não use `service_role`, `sb_secret_*` nem qualquer chave privilegiada. O front-end rejeita placeholders, chaves truncadas, formatos desconhecidos e JWT público pertencente a outro projeto.

## 4. Criar usuários e aprovar pelo UUID imutável

1. Abra `https://iaemloop.com.br/area_privada.html`.
2. Cadastre o usuário e confirme o e-mail.
3. Liste solicitações com o UUID:

```sql
select user_id, created_at, email, full_name, status
from public.access_requests
order by created_at desc;
```

4. Confirme que o UUID corresponde ao usuário esperado em `auth.users`:

```sql
select id, email, created_at
from auth.users
where id = 'UUID_DO_USUARIO'::uuid;
```

5. Aprove usando **somente o UUID**, nunca o e-mail mutável:

```sql
update public.access_requests
set status = 'approved',
    approved_at = now(),
    approved_by_email = 'equipeiaemloop@gmail.com',
    updated_at = now()
where user_id = 'UUID_DO_USUARIO'::uuid
returning user_id, status, approved_at;
```

O `RETURNING` deve mostrar exatamente uma linha. Se retornar zero ou mais de uma, interrompa e investigue.

## 5. Validar a Minha Carteira

Após a aprovação, o login direciona para `/privado/index.html`. O painel **Minha Carteira** permite criar e excluir:

- carteiras;
- contas/corretoras;
- posições;
- movimentações.

Os arquivos antigos de carteiras compartilhadas não são a fonte de dados da Fase 1. Não copie blobs, HTML de custódia ou uma carteira comum entre usuários. Cada operação usa o UUID autenticado e as políticas RLS do Supabase.

A sessão privada expira após cinco minutos sem atividade. Na expiração, o front-end limpa o estado privado, bloqueia/redireciona a tela e exige novo login. O servidor continua sendo a autoridade: toda leitura ou gravação também é revalidada e protegida por RLS.

## 6. Matriz obrigatória de isolamento pós-deploy

Crie dois usuários de teste, `USUARIO_A` e `USUARIO_B`, com UUIDs diferentes, e mantenha uma janela anônima. Execute e registre a matriz:

| Cenário | Resultado esperado |
|---|---|
| A aprovado cria carteira/conta/posição/movimentação | sucesso; linhas têm `user_id = UUID_A` |
| B aprovado cria dados próprios | sucesso; linhas têm `user_id = UUID_B` |
| A lista/edita/exclui dados de B, inclusive por ID conhecido | nenhuma linha visível ou alterada |
| B lista/edita/exclui dados de A, inclusive por ID conhecido | nenhuma linha visível ou alterada |
| Usuário autenticado pendente/rejeitado acessa tabelas financeiras | negado/zero linhas pelas políticas |
| Navegador anônimo acessa tabelas financeiras | negado |
| A acessa caminho de Storage iniciado por `UUID_B/` | negado |
| B acessa caminho de Storage iniciado por `UUID_A/` | negado |
| Navegador anônimo acessa o bucket `user-documents` | negado |
| Sessão aprovada fica cinco minutos sem atividade | DOM privado limpo e novo login exigido |
| Aprovação é revogada e o usuário tenta atualizar/criar/excluir | operação bloqueada e sessão encerrada |

## 7. Readback no banco

Confira a distribuição sem expor conteúdo financeiro:

```sql
select 'portfolios' as tabela, user_id, count(*) from public.portfolios group by user_id
union all
select 'portfolio_accounts', user_id, count(*) from public.portfolio_accounts group by user_id
union all
select 'holdings', user_id, count(*) from public.holdings group by user_id
union all
select 'portfolio_transactions', user_id, count(*) from public.portfolio_transactions group by user_id
order by tabela, user_id;
```

Verifique políticas e RLS:

```sql
select schemaname, tablename, policyname, roles, cmd
from pg_policies
where (schemaname = 'public' and tablename in (
  'access_requests', 'portfolios', 'portfolio_accounts', 'holdings',
  'portfolio_transactions', 'portfolio_documents', 'portfolio_analyses', 'contribution_plans'
)) or (schemaname = 'storage' and tablename = 'objects')
order by schemaname, tablename, policyname;

select relname, relrowsecurity, relforcerowsecurity
from pg_class
where relname in (
  'access_requests', 'portfolios', 'portfolio_accounts', 'holdings',
  'portfolio_transactions', 'portfolio_documents', 'portfolio_analyses', 'contribution_plans'
)
order by relname;
```

Antes de publicar, execute os três verificadores do repositório e os checks de sintaxe descritos no processo de release. Não publique se a chave pública completa não pertencer claramente ao projeto configurado ou se qualquer caso da matriz falhar.
