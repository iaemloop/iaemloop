# Fase 1 — Área Privada Multiusuário Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transformar a área privada em um aplicativo multiusuário no qual cada login acessa exclusivamente suas próprias carteiras, contas, posições e movimentações.

**Architecture:** O GitHub Pages continuará servindo somente o shell estático. O Supabase Auth identifica o usuário; PostgreSQL Row Level Security (RLS), e não o JavaScript, será a fronteira de autorização. Todas as tabelas financeiras terão `user_id` direto e chaves estrangeiras compostas para impedir referências cruzadas entre usuários.

**Tech Stack:** HTML/CSS/JavaScript sem build, Supabase JS v2, Supabase Auth, PostgreSQL/RLS, Supabase Storage privado, Python para verificações estáticas.

---

### Task 1: Criar esquema financeiro multiusuário

**Objective:** Criar tabelas normalizadas, vínculos de propriedade e políticas RLS por operação.

**Files:**
- Create: `supabase/phase1-multiuser-portfolio.sql`
- Create: `scripts/verify_phase1_multiuser_security.py`

**Steps:**
1. Criar verificador inicialmente falhando porque a migração ainda não existe ou não contém as garantias exigidas.
2. Rodar `python3 scripts/verify_phase1_multiuser_security.py` e confirmar falha.
3. Criar tabelas `portfolios`, `portfolio_accounts`, `holdings`, `portfolio_transactions`, `portfolio_documents`, `portfolio_analyses` e `contribution_plans`.
4. Adicionar `user_id not null` a todas, FKs compostas e índices iniciados por `user_id`.
5. Criar `private.is_approved_user()` com `security definer` e `search_path = ''`.
6. Habilitar RLS e criar políticas separadas de select/insert/update/delete para usuários autenticados e aprovados, sempre exigindo `auth.uid() = user_id`.
7. Revogar acesso de `anon`, conceder somente CRUD necessário a `authenticated`.
8. Criar bucket privado `user-documents` e políticas limitadas ao primeiro diretório igual ao UUID autenticado.
9. Rodar o verificador; esperado: `PHASE1_MULTIUSER_SECURITY_OK`.

### Task 2: Endurecer aprovação de acesso

**Objective:** Impedir que usuários alterem o próprio status de aprovação e fixar o contexto de segurança do trigger.

**Files:**
- Modify: `supabase/access-control.sql`
- Modify: `supabase/fix-access-trigger-backfill.sql`
- Test: `scripts/verify_phase1_multiuser_security.py`

**Steps:**
1. Alterar `handle_new_access_request()` para `set search_path = ''` e referências qualificadas.
2. Remover políticas de insert/update do navegador para `access_requests`.
3. Conceder a `authenticated` somente select da própria linha.
4. Atualizar exemplos administrativos para aprovação por UUID imutável.
5. Rodar o verificador e confirmar aprovação protegida.

### Task 3: Criar API JavaScript segura da carteira

**Objective:** Implementar CRUD estruturado sempre sob sessão autenticada e aprovada.

**Files:**
- Create: `js/privado/api.js`
- Create: `js/privado/render.js`
- Modify: `js/iaemloop-auth.js`
- Create: `scripts/verify_phase1_frontend_security.py`

**Steps:**
1. Criar teste estático que rejeite `innerHTML` com dados do banco, `service_role` e consultas privadas sem filtro explícito de usuário.
2. Expor no módulo de autenticação uma função segura para obter a sessão aprovada atual.
3. Implementar listagem/criação/edição/exclusão de carteiras, contas, posições e movimentações usando o cliente já existente.
4. Acrescentar `.eq('user_id', user.id)` como defesa em profundidade; RLS permanece a fronteira real.
5. Renderizar texto vindo do banco apenas com `textContent`/criação explícita de DOM.
6. Rodar o teste estático; esperado: `PHASE1_FRONTEND_SECURITY_OK`.

### Task 4: Construir painel Minha Carteira

**Objective:** Entregar uma interface útil para Diego cadastrar e visualizar seus próprios dados.

**Files:**
- Modify: `privado/index.html`
- Create: `css/privado-app.css`
- Create: `js/privado/app.js`

**Steps:**
1. Trocar o catálogo de páginas compartilhadas por dashboard do usuário.
2. Adicionar indicadores de número de carteiras, contas, ativos, custo total e movimentações.
3. Adicionar formulários para criar carteira, conta, posição e movimentação.
4. Adicionar tabelas com edição/exclusão confirmada e estados de vazio/erro/carregamento.
5. Exibir Análise de Carteira e Sugestão de Aporte como módulos da próxima fase, sem produzir recomendação prematura.
6. Verificar em navegador que a página carrega, a autenticação bloqueia o conteúdo e não há erros JavaScript antes da migração.

### Task 5: Ampliar guardas e verificar integração

**Objective:** Impedir publicação acidental de custódia e validar a entrega completa.

**Files:**
- Modify: `scripts/verify_no_private_custody_public.py`
- Modify: `docs/area-privada-newsletter-roadmap.md`

**Steps:**
1. Ampliar a varredura para JavaScript, CSV e JSON públicos, com exclusões explícitas somente para schemas/testes.
2. Documentar que aprovação é somente portão de entrada; propriedade por RLS é a autorização de dados.
3. Rodar os três verificadores Python e testes existentes.
4. Revisar `git diff` para garantir que alterações antigas não relacionadas foram preservadas.
5. Aplicar a migração no projeto Supabase somente com acesso administrativo disponível.
6. Testar com usuário A, usuário B, usuário pendente e cliente anônimo; a Fase 1 só está operacionalmente concluída quando o isolamento remoto estiver comprovado.
