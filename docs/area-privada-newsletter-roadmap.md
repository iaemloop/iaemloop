# IA em Loop — Área privada, newsletter e acesso pago

Decisão: manter o site público com blog, rankings, metodologia e conteúdo educacional; retirar custódia/carteiras reais do público. Criar uma área privada real para Diego e, no futuro, para assinantes.

## Ponto crítico de segurança

Uma tela de login feita apenas em HTML/JavaScript dentro do GitHub Pages **não protege** carteiras reais. Se os dados estiverem no HTML, JSON, CSV ou JS do site público, qualquer pessoa consegue baixar ou inspecionar.

Portanto, a área privada precisa de **autenticação no servidor** ou de um provedor que bloqueie o arquivo antes de entregar ao navegador.

## Arquitetura recomendada

### Público — iaemloop.com.br

Hospedagem atual pode continuar estática/GitHub Pages:

- Home pública
- Blog
- Metodologias
- Rankings educacionais
- Ranking FGC
- Conteúdo de ações/stocks selecionadas para estudo
- Newsletter pública ou landing da newsletter

Não publicar:

- carteira real completa
- custódia
- notas, compras, quantidades, preço médio, corretora
- `carteira_*_real.html`
- JSON/CSV de ledgers privados

### Privado — app.iaemloop.com.br ou privado.iaemloop.com.br

Criar app separado com autenticação real:

- Login/senha
- Sessão/cookie segura
- Controle de usuário
- Área Diego/admin
- Futuro plano pago
- Conteúdo privado renderizado somente após autenticação

Stack sugerida:

1. **Cloudflare Pages + Cloudflare Workers/Functions** para hospedar app e proteger rotas.
2. **Supabase Auth** para login/senha/magic link.
3. **Supabase Postgres/Storage** para dados privados, se necessário.
4. **Resend/Brevo/Buttondown** para newsletter.
5. **Stripe** no futuro para assinatura paga.

Alternativa mais simples no curto prazo:

- Cloudflare Access protegendo `/privado` ou `privado.iaemloop.com.br` por e-mail autorizado.
- Bom para acesso pessoal/família.
- Menos ideal para venda futura, mas rápido e seguro.

## Fases

### Fase 0 — já implementada localmente

- Site público sem CTA de carteira real.
- Guard público contra vazamento de custódia.
- Servidor local privado com Basic Auth.
- Watchdog Hermes para manter o servidor ativo.

### Fase 1 — área privada online para Diego

Objetivo: acesso fora de casa sem depender de Wi-Fi local e sem custo inicial.

Opção A — Tailscale:
- Plano pessoal grátis costuma atender o uso próprio.
- Mais simples e seguro para uso pessoal.
- Sem exposição pública.
- Requer instalar/logar Tailscale nos aparelhos.

Opção B — Cloudflare Access / Zero Trust:
- Tem plano gratuito para começar em pequena escala, sujeito aos limites atuais da Cloudflare.
- `privado.iaemloop.com.br` protegido por e-mail/login.
- Acessa de qualquer rede/celular.
- Não exige Tailscale em todo aparelho.
- Melhor transição para produto futuro.

Opção C — Supabase Auth + app privado:
- Supabase tem plano gratuito para começar, sujeito a limites de projetos/uso/inatividade.
- Melhor base para cadastro, login/senha, recuperação de senha e futura assinatura paga.
- Exige construir um app/backend, não apenas HTML estático.

Recomendação sem custo agora: **Cloudflare Access** para proteger a área privada rapidamente, ou **Supabase Auth no free tier** se já quisermos construir login/cadastro/recuperação pensando em produto.

### Fase 1A — vitrine segura da área privada

Criar no site público uma página `area_privada.html` com:

- botão “Acompanhe a carteira” na home;
- box de login/cadastro/esqueci senha;
- fundo translúcido/blur com gráficos e KPIs **fictícios ou mascarados**;
- nenhum HTML/JSON/CSV real de carteira carregado no navegador público.

Regra: blur/transparência é apenas marketing/teaser. A segurança real vem de não entregar os dados privados ao usuário não autenticado.

### Fase 2 — newsletter pública

Criar página pública:

- `newsletter.html` ou seção na home.
- Coletar e-mail com consentimento.
- Enviar:
  - posts do blog;
  - atualizações dos rankings;
  - uma ação/stock comprada no mês, sem revelar a carteira completa;
  - comentários educacionais e metodologia.

Importante: não dizer “comprei X em tal corretora/quantidade/preço exato” na newsletter pública inicial. Usar formato:

> Ativo do mês em estudo/acompanhamento: TICKER. Entrou no radar/carteira privada por critérios X/Y/Z. Isto não é recomendação.

### Fase 3 — área privada para assinantes

Conteúdo privado:

- carteira completa;
- histórico de compras;
- racional mensal;
- metodologia completa;
- planilhas/dashboards;
- alertas de atualização;
- ranking com filtros avançados;
- comparação entre carteiras.

Controle:

- Supabase Auth para usuários;
- Stripe para assinatura;
- webhook Stripe atualiza plano do usuário;
- rotas privadas checam `subscription_status=active`.

### Fase 4 — comunidade/produto

- Área de membros;
- comentários/perguntas;
- relatórios mensais;
- possíveis vídeos quando o projeto YouTube voltar.

## Conteúdo público vs privado

| Conteúdo | Público | Privado |
|---|---:|---:|
| Blog macro/invest/geopolítica | sim | sim |
| Rankings Top 20 educacionais | sim | sim |
| Metodologia resumida | sim | sim |
| Metodologia completa operacional | parcial | sim |
| Uma ação/stock comprada no mês | sim, resumida | sim, completa |
| Carteira completa | não | sim |
| Custódia/quantidade/preço/corretora | não | sim |
| Notas/ledgers/CSV privados | não | sim |
| Dashboard de alocação | não | sim |

## Regra editorial nova

A rotina semanal/mensal continua atualizando blog, rankings e carteiras, mas o pipeline deve ter dois destinos:

1. **public_export** — somente conteúdo público permitido.
2. **private_export** — carteira/custódia completa, acessível apenas autenticado.

Antes de publicar, rodar:

```bash
python3 scripts/verify_no_private_custody_public.py
```

Se falhar, não publicar.

## Recomendação final

Não criar apenas uma tela de login dentro do GitHub Pages. Isso seria aparência de segurança.

Caminho recomendado para produto futuro:

1. manter GitHub Pages público;
2. criar `privado.iaemloop.com.br` com Cloudflare Access no curto prazo;
3. evoluir para app com Supabase Auth + Stripe quando houver interessados;
4. newsletter pública com conteúdo controlado e uma ação/stock do mês sem expor custódia completa.
