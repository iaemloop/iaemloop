#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'js/privado/portfolio-engine.js'
QUOTES = ROOT / 'js/privado/portfolio-quotes.js'
SERVICES = ROOT / 'js/privado/portfolio-services.js'
API = ROOT / 'js/privado/api.js'
IMPORTER = ROOT / 'js/privado/portfolio-import.js'
MIGRATION = ROOT / 'supabase/phase4-portfolio-services.sql'
PAGES = [ROOT / 'privado/minha-carteira.html', ROOT / 'privado/v2/minha-carteira.html']

failures = []

def require(text, marker, label):
    if marker not in text:
        failures.append(f'{label}: missing {marker!r}')

def forbid(text, marker, label):
    if marker in text:
        failures.append(f'{label}: forbidden {marker!r}')

engine = ENGINE.read_text()
quotes = QUOTES.read_text()
services = SERVICES.read_text()
api = API.read_text()
importer = IMPORTER.read_text()
migration = MIGRATION.read_text()

for page in PAGES:
    text = page.read_text()
    label = page.relative_to(ROOT)
    for marker in ('id="analise"', 'id="aporte-mensal"', 'id="importar-custodia"', 'id="import-confirm"', 'data-portfolio-select', 'contribution-reviewed-tickers', 'contribution-dossier-tickers', 'value="discover"', 'Ainda não sigo um método', 'portfolio-engine.js?v=2', 'portfolio-quotes.js?v=1', 'portfolio-services.js?v=2', 'portfolio-import.js?v=2', 'exceljs@4.4.0'):
        require(text, marker, str(label))
    forbid(text, 'Próximos serviços', str(label))

for source, label in ((engine, 'engine'), (quotes, 'quotes'), (services, 'services'), (importer, 'importer')):
    for marker in ('.innerHTML', 'document.write', 'eval('):
        forbid(source, marker, label)

for marker in (
    'window.IAEMLOOPAuth.requireApprovedSession()',
    'api.listPortfolios()',
    'api.listAccounts()',
    'api.listHoldings()',
    "document.addEventListener('iaemloop:session-invalidated', clearOutputs)",
    "const RISK_GATE_URL = '/outputs/risk_gate_all_2026-10.json?v=20261009'",
    "plan.residualMinor ?? plan.availableMinor ?? 0",
    "await window.IAEMLOOPAuth.requireApprovedSession();",
    "requestId !== contributionGeneration",
    "source: 'informada manualmente'",
    "approvedReviewTickers: parseTickerList",
    "approvedDossierTickers: parseTickerList",
    "engine.discoverMethodology",
    "renderMethodDiscovery",
):
    require(services, marker, 'services')

for marker in (
    "automaticExecutionAllowed: false",
    "execution: { performed: false, ordersSubmitted: 0 }",
    "status: 'AWAITING_HUMAN_APPROVAL'",
    "side: 'BUY'",
    "Math.max(0, 15 - held.size)",
    "requested = Math.max(3, requested)",
    "row.currency === expectedCurrency",
    "portfolio.strategy_key !== sleeve",
    "approvedReviews.has(row.ticker)",
    "approvedDossiers.has(row.ticker)",
    "function discoverMethodology(input)",
    "suggestedSleeves",
    "BRL e USD nunca são somados",
    "não compara carteiras",
):
    require(engine, marker, 'engine')

for marker in ('private_pages', 'service_role', 'SUPABASE_SERVICE_ROLE_KEY'):
    forbid(engine + quotes + services, marker, 'portfolio service scripts')

for marker in ('monthlyReviewConfirmed', 'newTickerDossiersConfirmed', 'plan.residualMinor || plan.availableMinor'):
    forbid(engine + services, marker, 'portfolio service semantics')

for marker in ('strategy_key', 'setPortfolioStrategy', ".eq('user_id', context.user.id)"):
    require(api, marker, 'api')

for marker in (
    'createHoldings',
    'insertMany',
    'MAX_FILE_BYTES',
    "signature !== '%PDF-'",
    'isEvalSupported: false',
    'document.numPages > 50',
    'sheet.actualRowCount > 1001',
    "root.IAEMLOOPAuth.requireApprovedSession()",
    "root.document.addEventListener('iaemloop:session-invalidated'",
):
    require(api + importer, marker, 'portfolio import')

for marker in ('FileReader.readAsDataURL', 'fetch(file', 'localStorage', 'sessionStorage'):
    forbid(importer, marker, 'portfolio import privacy')

for marker in ('add column if not exists strategy_key', 'portfolios_strategy_currency_check', 'portfolios_one_strategy_per_user_idx', 'enforce_portfolio_strategy_immutable', 'bind_portfolio_strategy', "strategy_key can only be assigned once", 'from anon'):
    require(migration, marker, 'phase4 migration')

if failures:
    print('PORTFOLIO_SERVICES_VERIFICATION_FAILED')
    for failure in failures:
        print('-', failure)
    raise SystemExit(1)

print('PORTFOLIO_SERVICES_VERIFICATION_OK')
