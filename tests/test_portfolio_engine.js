const assert = require('node:assert/strict');
const engine = require('../js/privado/portfolio-engine.js');

const riskAssets = [
  { sleeve: 'magic-b3', ticker: 'PSSA3', rank_final: '1', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'sem_alerta_experimental', setor: 'Seguros' },
  { sleeve: 'magic-b3', ticker: 'QUAL3', rank_final: '2', aporte_status: 'bloqueado_por_veto_experimental', risco_estrutural_status: 'veto_experimental', setor: 'Saúde' },
  { sleeve: 'magic-b3', ticker: 'MILS3', rank_final: '3', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'sem_alerta_experimental', setor: 'Serviços' },
  { sleeve: 'magic-b3', ticker: 'LEVE3', rank_final: '4', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'sem_alerta_experimental', setor: 'Autopeças' },
  { sleeve: 'magic-usd', ticker: 'GDDY', rank: '1', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'revisao_corporativa_obrigatoria' },
  { sleeve: 'magic-usd', ticker: 'ALL', rank: '2', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'revisao_corporativa_obrigatoria' },
  { sleeve: 'magic-usd', ticker: 'LVS', rank: '3', aporte_status: 'depende_de_dossie_e_decisao_mensal', risco_estrutural_status: 'revisao_corporativa_obrigatoria' }
];

const portfolio = { id: 'p1', name: 'Magic Brasil', base_currency: 'BRL', strategy_key: 'magic-b3' };
const accounts = [{ id: 'a1', portfolio_id: 'p1', currency: 'BRL', cash_balance: '20' }];
const holdings = [
  { portfolio_id: 'p1', account_id: 'a1', symbol: 'PSSA3', quantity: '2', average_cost: '40', currency: 'BRL', asset_type: 'equity' },
  { portfolio_id: 'p1', account_id: 'a1', symbol: 'OLD3', quantity: '1', average_cost: '20', currency: 'BRL', asset_type: 'equity' }
];
const approvedB3Reviews = ['PSSA3', 'MILS3', 'LEVE3'];
const approvedB3Dossiers = ['MILS3', 'LEVE3'];

{
  const discoveryRiskAssets = [
    ...riskAssets,
    { sleeve: 'besst-b3', ticker: 'PETR4', rank: '1', dividend_yield: '8.0', anos_com_dividendos: '19', classificacao_setor: 'PERENE' },
    { sleeve: 'besst-b3', ticker: 'PSSA3', rank: '2', dividend_yield: '5.0', anos_com_dividendos: '15', classificacao_setor: 'PERENE' }
  ];
  const discovery = engine.discoverMethodology({
    portfolio: { id: 'd1', name: 'Custódia anterior', base_currency: 'BRL', strategy_key: null },
    holdings: [
      { portfolio_id: 'd1', account_id: 'a1', symbol: 'PETR4', quantity: '10', average_cost: '30', currency: 'BRL', asset_type: 'equity' },
      { portfolio_id: 'd1', account_id: 'a1', symbol: 'PSSA3', quantity: '2', average_cost: '40', currency: 'BRL', asset_type: 'equity' },
      { portfolio_id: 'd1', account_id: 'a1', symbol: 'OLD3', quantity: '1', average_cost: '20', currency: 'BRL', asset_type: 'equity' }
    ],
    riskAssets: discoveryRiskAssets
  });
  assert.equal(discovery.markets.length, 1);
  assert.equal(discovery.markets[0].currency, 'BRL');
  assert.equal(discovery.markets[0].recommendation, 'besst');
  assert.ok(discovery.markets[0].reasons.some((reason) => reason.includes('BESST & Buffett')));
  assert.ok(discovery.markets[0].warnings.some((warning) => warning.includes('fora do ranking')));
}

{
  const both = engine.discoverMethodology({
    portfolio: { id: 'd2', name: 'Custódia híbrida', base_currency: 'BRL', strategy_key: null },
    holdings: [
      { portfolio_id: 'd2', account_id: 'a1', symbol: 'PSSA3', quantity: '2', average_cost: '40', currency: 'BRL', asset_type: 'equity' },
      { portfolio_id: 'd2', account_id: 'a1', symbol: 'PETR4', quantity: '2', average_cost: '40', currency: 'BRL', asset_type: 'equity' }
    ],
    riskAssets: [
      { sleeve: 'besst-b3', ticker: 'PSSA3', rank: '1', dividend_yield: '5', anos_com_dividendos: '15' },
      { sleeve: 'besst-b3', ticker: 'PETR4', rank: '2', dividend_yield: '8', anos_com_dividendos: '19' },
      { sleeve: 'magic-b3', ticker: 'PSSA3', rank_final: '1', roic: '0.7', earnings_yield: '0.3' },
      { sleeve: 'magic-b3', ticker: 'PETR4', rank_final: '2', roic: '0.2', earnings_yield: '0.18' }
    ]
  });
  assert.equal(both.markets[0].recommendation, 'both');
  assert.deepEqual(both.markets[0].suggestedSleeves, ['besst-b3', 'magic-b3']);
}

{
  const empty = engine.discoverMethodology({
    portfolio: { id: 'd3', name: 'Vazia', base_currency: 'USD', strategy_key: null },
    holdings: [],
    riskAssets
  });
  assert.equal(empty.status, 'NO_HOLDINGS');
  assert.equal(empty.markets.length, 0);
}

{
  const analysis = engine.analyzePortfolio({ portfolio, accounts, holdings, riskAssets, sleeve: 'magic-b3' });
  assert.equal(analysis.assetCount, 2);
  assert.equal(analysis.capacityRemaining, 13);
  assert.equal(analysis.knownCostMinor, 10000);
  assert.equal(analysis.rankedHoldings.length, 1);
  assert.equal(analysis.outOfRanking.length, 1);
  assert.equal(analysis.topPositions[0].ticker, 'PSSA3');
  assert.equal(analysis.topPositions[0].weightPct, 80);
}

{
  const blocked = engine.planContribution({
    portfolio, accounts, holdings, riskAssets, sleeve: 'magic-b3', amount: '500', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: [], approvedDossierTickers: approvedB3Dossiers,
    quotes: { PSSA3: '50', QUAL3: '10', MILS3: '10', LEVE3: '20' }
  });
  assert.equal(blocked.status, 'BLOCKED_REVIEW');
  assert.equal(blocked.orders.length, 0);
}

{
  const plan = engine.planContribution({
    portfolio, accounts, holdings, riskAssets, sleeve: 'magic-b3', amount: '500', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: approvedB3Reviews, approvedDossierTickers: approvedB3Dossiers,
    quotes: { PSSA3: '50', QUAL3: '10', MILS3: '10', LEVE3: '20' }
  });
  assert.equal(plan.status, 'AWAITING_HUMAN_APPROVAL');
  assert.equal(plan.automaticExecutionAllowed, false);
  assert.ok(plan.orders.length > 0);
  assert.ok(plan.orders.every((order) => order.side === 'BUY'));
  assert.ok(!plan.orders.some((order) => order.ticker === 'QUAL3'));
  assert.equal(plan.orders.reduce((sum, order) => sum + order.totalMinor, 0) + plan.residualMinor + plan.feesMinor, 50000);
  assert.ok(plan.orders.every((order) => Number.isInteger(order.quantity)));
}

{
  const noDossier = engine.planContribution({
    portfolio, accounts, holdings, riskAssets, sleeve: 'magic-b3', amount: '500', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: approvedB3Reviews, approvedDossierTickers: [],
    quotes: { PSSA3: '50', MILS3: '10', LEVE3: '20' }
  });
  assert.deepEqual(noDossier.orders.map((order) => order.ticker), ['PSSA3']);
  assert.ok(noDossier.rejectedCandidates.some((item) => item.reason === 'DOSSIER_REQUIRED'));
}

{
  const usd = engine.planContribution({
    portfolio: { id: 'u1', name: 'Magic USD', base_currency: 'USD', strategy_key: 'magic-usd' }, accounts: [], holdings: [], riskAssets, sleeve: 'magic-usd',
    amount: '300', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: ['GDDY', 'ALL', 'LVS'], approvedDossierTickers: ['GDDY', 'ALL', 'LVS'],
    quotes: { GDDY: '100', ALL: '200', LVS: '50' }
  });
  assert.equal(usd.status, 'AWAITING_HUMAN_APPROVAL');
  assert.equal(usd.orders.length, 3);
  assert.equal(usd.orders.reduce((sum, order) => sum + order.totalMinor, 0), 30000);
  assert.ok(usd.orders.every((order) => order.quantity === null && order.totalMinor > 0));
}

{
  const atCapacity = Array.from({ length: 15 }, (_, i) => ({ portfolio_id: 'p1', account_id: 'a1', symbol: i === 0 ? 'PSSA3' : `OLD${i}`, quantity: '1', average_cost: '10', currency: 'BRL', asset_type: 'equity' }));
  const plan = engine.planContribution({
    portfolio, accounts, holdings: atCapacity, riskAssets, sleeve: 'magic-b3', amount: '200', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: approvedB3Reviews, approvedDossierTickers: approvedB3Dossiers,
    quotes: { PSSA3: '50', MILS3: '10', LEVE3: '20' }
  });
  assert.deepEqual(plan.orders.map((order) => order.ticker), ['PSSA3']);
  assert.ok(plan.rejectedCandidates.some((item) => item.reason === 'ASSET_LIMIT'));
}

{
  const mixed = engine.analyzePortfolio({
    portfolio, accounts, riskAssets, sleeve: 'magic-b3',
    holdings: [...holdings, { portfolio_id: 'p1', account_id: 'a2', symbol: 'USDONLY', quantity: '1', average_cost: '100', currency: 'USD', asset_type: 'equity' }]
  });
  assert.equal(mixed.knownCostMinor, 10000);
  assert.deepEqual(mixed.excludedCurrencyHoldings, ['USDONLY']);
  assert.ok(mixed.warnings.some((warning) => warning.includes('moeda incompatível')));
}

{
  const wrongSleeve = engine.planContribution({
    portfolio, accounts, holdings, riskAssets, sleeve: 'besst-b3', amount: '500', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: [], approvedDossierTickers: [], quotes: {}
  });
  assert.equal(wrongSleeve.status, 'INVALID_INPUT');
}

{
  const mixedPlan = engine.planContribution({
    portfolio, accounts, riskAssets, sleeve: 'magic-b3', amount: '500', proceeds: '0', fees: '0', requestedOrderCount: 3,
    holdings: [...holdings, { portfolio_id: 'p1', account_id: 'a2', symbol: 'USDONLY', quantity: '1', average_cost: '100', currency: 'USD', asset_type: 'equity' }],
    approvedReviewTickers: approvedB3Reviews, approvedDossierTickers: approvedB3Dossiers, quotes: { PSSA3: '50', MILS3: '10', LEVE3: '20' }
  });
  assert.equal(mixedPlan.status, 'INVALID_INPUT');
}

{
  const tinyUsd = engine.planContribution({
    portfolio: { id: 'u1', name: 'Magic USD', base_currency: 'USD', strategy_key: 'magic-usd' }, accounts: [], holdings: [], riskAssets, sleeve: 'magic-usd',
    amount: '0.01', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: ['GDDY', 'ALL', 'LVS'], approvedDossierTickers: ['GDDY', 'ALL', 'LVS'], quotes: { GDDY: '100', ALL: '200', LVS: '50' }
  });
  assert.equal(tinyUsd.status, 'BLOCKED_US_MINIMUM_NAMES');
  assert.equal(tinyUsd.orders.length, 0);
}

assert.equal(engine.toMinor('9'.repeat(400)), null);

{
  const large = engine.planContribution({
    portfolio, accounts, holdings, riskAssets, sleeve: 'magic-b3', amount: '100000000', proceeds: '0', fees: '0', requestedOrderCount: 3,
    approvedReviewTickers: approvedB3Reviews, approvedDossierTickers: approvedB3Dossiers,
    quotes: { PSSA3: '0.01', MILS3: '0.01', LEVE3: '0.01' }
  });
  assert.equal(large.status, 'AWAITING_HUMAN_APPROVAL');
  assert.equal(large.orders.reduce((sum, order) => sum + order.totalMinor, 0) + large.residualMinor, 10000000000);
}
console.log('PORTFOLIO_ENGINE_TESTS_OK');
