(function () {
  'use strict';

  const api = window.IAEMLOOPPortfolioAPI;
  const engine = window.IAEMLOOPPortfolioEngine;
  const quoteService = window.IAEMLOOPPortfolioQuotes;
  const RISK_GATE_URL = '/outputs/risk_gate_all_2026-10.json?v=20261009';
  const MAX_QUOTE_AGE_MS = 96 * 60 * 60 * 1000;
  const STRATEGY_NAMES = Object.freeze({
    'besst-b3': 'BESST & Buffett Brasil',
    'magic-b3': 'Magic Formula Brasil',
    'besst-usd': 'BESST & Buffett Dolarizado',
    'magic-usd': 'Magic Formula Dolarizada'
  });
  const STATUS_NAMES = Object.freeze({
    AWAITING_HUMAN_APPROVAL: 'Aguardando revisão humana',
    INVALID_INPUT: 'Dados inválidos',
    BLOCKED_REVIEW: 'Bloqueado por revisão mensal',
    BLOCKED_DOSSIER: 'Bloqueado por dossiê',
    BLOCKED_CAPACITY: 'Bloqueado por limite de ativos',
    BLOCKED_BUDGET: 'Bloqueado pelo valor disponível',
    BLOCKED_US_MINIMUM_NAMES: 'Bloqueado pelo mínimo de ações dos EUA',
    NO_ELIGIBLE_CANDIDATES: 'Sem candidatos elegíveis'
  });
  const REJECTION_NAMES = Object.freeze({
    RISK_VETO: 'veto do gate de risco',
    MONTHLY_REVIEW_REQUIRED: 'revisão mensal não informada',
    DOSSIER_REQUIRED: 'dossiê vigente não informado',
    ASSET_LIMIT: 'limite de 15 ativos',
    QUOTE_REQUIRED: 'cotação válida ausente',
    BUDGET: 'valor insuficiente para a quantidade mínima'
  });

  let riskGatePromise = null;
  let privateDataCache = null;
  let analysisGeneration = 0;
  let contributionGeneration = 0;

  const byId = (id) => document.getElementById(id);
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text != null) element.textContent = String(text);
    return element;
  };

  function moneyMinor(value, currency) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency }).format(Number(value ?? 0) / 100);
  }

  function percent(value) {
    return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(Number(value || 0))}%`;
  }

  async function loadRiskGate() {
    if (!riskGatePromise) {
      riskGatePromise = fetch(RISK_GATE_URL, { cache: 'no-store' }).then((response) => {
        if (!response.ok) throw new Error('O gate mensal de risco não está disponível.');
        return response.json();
      }).then((data) => data.assets || []).catch((error) => {
        riskGatePromise = null;
        throw error;
      });
    }
    return riskGatePromise;
  }

  async function loadPrivateData(force = false) {
    await window.IAEMLOOPAuth.requireApprovedSession();
    if (!force && privateDataCache) return privateDataCache;
    const [portfolios, accounts, holdings] = await Promise.all([
      api.listPortfolios(), api.listAccounts(), api.listHoldings()
    ]);
    privateDataCache = { portfolios, accounts, holdings };
    return privateDataCache;
  }

  function selectedPortfolio(data, selectId) {
    const id = byId(selectId)?.value;
    return data.portfolios.find((item) => item.id === id) || null;
  }

  function populateSelect(select, portfolios) {
    if (!select) return;
    const current = select.value;
    select.replaceChildren(node('option', 'Selecione a carteira'));
    select.firstChild.value = '';
    portfolios.forEach((portfolio) => {
      const method = STRATEGY_NAMES[portfolio.strategy_key] || 'método pendente';
      const option = node('option', `${portfolio.name} · ${method} · ${portfolio.base_currency}`);
      option.value = portfolio.id;
      select.appendChild(option);
    });
    if (portfolios.some((item) => item.id === current)) select.value = current;
  }

  function syncMethodForPortfolio(data, portfolioSelectId, sleeveSelectId, allowDiscovery = false) {
    const portfolio = selectedPortfolio(data, portfolioSelectId);
    const sleeveSelect = byId(sleeveSelectId);
    if (!sleeveSelect) return;
    if (portfolio?.strategy_key) {
      sleeveSelect.value = portfolio.strategy_key;
      sleeveSelect.disabled = true;
      sleeveSelect.title = 'Método permanente vinculado à carteira.';
    } else {
      sleeveSelect.disabled = false;
      if (allowDiscovery) {
        sleeveSelect.value = 'discover';
        sleeveSelect.title = 'A IA analisará os ativos cadastrados e sugerirá BESST & Buffett, Magic Formula ou ambas.';
      } else {
        sleeveSelect.title = 'Escolha um método somente depois de analisar os ativos; o primeiro aporte confirmará o vínculo permanente.';
        if (portfolio?.base_currency === 'USD' && !sleeveSelect.value.endsWith('-usd')) sleeveSelect.value = 'besst-usd';
        if (portfolio?.base_currency === 'BRL' && !sleeveSelect.value.endsWith('-b3')) sleeveSelect.value = 'besst-b3';
      }
    }
  }

  async function syncServicePortfolios(force = true) {
    const data = await loadPrivateData(force);
    populateSelect(byId('analysis-portfolio'), data.portfolios);
    populateSelect(byId('contribution-portfolio'), data.portfolios);
    syncMethodForPortfolio(data, 'analysis-portfolio', 'analysis-sleeve', true);
    syncMethodForPortfolio(data, 'contribution-portfolio', 'contribution-sleeve');
    return data;
  }

  async function ensurePermanentStrategy(portfolio, sleeve) {
    if (portfolio.strategy_key) {
      if (portfolio.strategy_key !== sleeve) throw new Error('O método escolhido não corresponde ao vínculo permanente da carteira.');
      return portfolio;
    }
    const label = STRATEGY_NAMES[sleeve] || sleeve;
    if (!window.confirm(`Vincular permanentemente a carteira “${portfolio.name}” ao método “${label}”?`)) throw new Error('Vínculo do método cancelado.');
    const updated = await api.setPortfolioStrategy(portfolio.id, sleeve);
    privateDataCache = null;
    return updated;
  }

  function addMetric(container, label, value) {
    const card = node('article', null, 'service-metric');
    card.append(node('span', label), node('strong', value));
    container.appendChild(card);
  }

  function addList(container, title, values, emptyText) {
    const block = node('section', null, 'service-list');
    block.appendChild(node('h4', title));
    if (!values.length) block.appendChild(node('p', emptyText, 'muted-copy'));
    else {
      const list = node('ul');
      values.forEach((value) => list.appendChild(node('li', value)));
      block.appendChild(list);
    }
    container.appendChild(block);
  }

  function renderAnalysis(result, portfolio) {
    const output = byId('analysis-output');
    output.replaceChildren();
    const heading = node('div', null, 'service-result-heading');
    heading.append(node('h3', `Análise de ${portfolio.name}`), node('p', `${STRATEGY_NAMES[result.sleeve]} · ${result.methodology}`, 'muted-copy'));
    output.appendChild(heading);
    const metrics = node('div', null, 'service-metrics');
    addMetric(metrics, 'Ativos', result.assetCount);
    addMetric(metrics, 'Vagas até o limite', result.capacityRemaining);
    addMetric(metrics, 'Custo conhecido', moneyMinor(result.knownCostMinor, result.currency));
    addMetric(metrics, 'No ranking mensal', result.rankedHoldings.length);
    output.appendChild(metrics);
    addList(output, 'Maiores posições por custo cadastrado', result.topPositions.slice(0, 5).map((item) => `${item.ticker}: ${percent(item.weightPct)} · ${moneyMinor(item.knownCostMinor, result.currency)}`), 'Não há posições com custo conhecido para comparar.');
    addList(output, 'Ativos fora do ranking atual', result.outOfRanking, result.assetCount ? 'Todos os ativos considerados aparecem no ranking selecionado.' : 'Não há posições para comparar.');
    addList(output, 'Posições excluídas por moeda', result.excludedCurrencyHoldings, 'Nenhuma posição em moeda incompatível foi encontrada.');
    addList(output, 'Bloqueados para novos aportes', result.blockedHoldings, 'Nenhum ativo em custódia está sob veto do gate atual.');
    addList(output, 'Alertas', result.warnings, 'Nenhum alerta estrutural foi identificado pelos dados cadastrados.');
    output.appendChild(node('p', 'Prévia local não assinada, calculada no navegador com os dados privados da sessão. Ela não envia ordens, não comprova aprovação institucional e não recomenda venda automática.', 'service-disclaimer'));
  }

  function recommendationName(value) {
    return ({ besst: 'BESST & Buffett', magic: 'Magic Formula', both: 'BESST & Buffett e Magic Formula', inconclusive: 'Revisão individual antes de escolher' })[value] || value;
  }

  function renderMethodDiscovery(result, portfolio) {
    const output = byId('analysis-output');
    output.replaceChildren();
    const heading = node('div', null, 'service-result-heading');
    heading.append(node('h3', `Sugestão de metodologia para ${portfolio.name}`), node('p', result.methodology, 'muted-copy'));
    output.appendChild(heading);
    if (!result.markets.length) {
      output.appendChild(node('p', 'Cadastre ou importe pelo menos uma ação ou stock antes de solicitar a análise.', 'service-alert'));
      return;
    }
    result.markets.forEach((market) => {
      const block = node('section', null, 'service-list methodology-discovery');
      block.appendChild(node('h4', `${market.currency}: ${recommendationName(market.recommendation)}`));
      const metrics = node('div', null, 'service-metrics');
      addMetric(metrics, 'Ativos analisados', market.assetCount);
      addMetric(metrics, 'Aderência B&B', `${market.fits.besst.score}/100`);
      addMetric(metrics, 'Aderência Magic Formula', `${market.fits.magic.score}/100`);
      addMetric(metrics, 'Maior concentração', percent(market.largestWeightPct));
      block.appendChild(metrics);
      addList(block, 'Por que esta sugestão', market.reasons, 'Sem evidências suficientes.');
      addList(block, 'Ativos aderentes ao B&B', market.fits.besst.matchedTickers, 'Nenhum ativo apareceu no universo mensal B&B.');
      addList(block, 'Ativos aderentes à Magic Formula', market.fits.magic.matchedTickers, 'Nenhum ativo apareceu no universo mensal Magic Formula.');
      addList(block, 'Pontos de atenção', market.warnings, 'Nenhum alerta adicional foi identificado.');
      block.appendChild(node('p', market.disclaimer, 'service-disclaimer'));
      output.appendChild(block);
    });
    output.appendChild(node('p', 'A recomendação não altera automaticamente o método da carteira. Depois de revisar a explicação, escolha o método desejado no seletor e confirme o vínculo permanente. Se a sugestão for “ambas”, mantenha carteiras separadas para cada método.', 'service-disclaimer'));
  }

  function setServiceStatus(id, message, kind = 'info') {
    const element = byId(id);
    if (!element) return;
    element.textContent = message;
    element.dataset.kind = kind;
  }

  function setPending(form, pending) {
    form.querySelectorAll('button, input, select, textarea').forEach((element) => {
      if (!pending && (element.id === 'analysis-sleeve' || element.id === 'contribution-sleeve')) {
        const portfolioSelectId = element.id === 'analysis-sleeve' ? 'analysis-portfolio' : 'contribution-portfolio';
        const portfolio = privateDataCache?.portfolios?.find((item) => item.id === byId(portfolioSelectId)?.value);
        element.disabled = Boolean(portfolio?.strategy_key);
      } else element.disabled = pending;
    });
  }

  async function handleAnalysis(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const requestId = ++analysisGeneration;
    byId('analysis-output').replaceChildren();
    setPending(form, true);
    setServiceStatus('analysis-status', 'Calculando a análise...', 'info');
    try {
      const [data, riskAssets] = await Promise.all([loadPrivateData(true), loadRiskGate()]);
      let portfolio = selectedPortfolio(data, 'analysis-portfolio');
      const sleeve = byId('analysis-sleeve').value;
      if (!portfolio) throw new Error('Selecione uma carteira.');
      if (sleeve === 'discover') {
        if (portfolio.strategy_key) throw new Error('Esta carteira já possui método permanente. Use a análise do método vinculado.');
        const discovery = engine.discoverMethodology({ portfolio, holdings: data.holdings, riskAssets });
        await window.IAEMLOOPAuth.requireApprovedSession();
        if (requestId !== analysisGeneration) return;
        renderMethodDiscovery(discovery, portfolio);
        setServiceStatus('analysis-status', discovery.status === 'READY' ? 'Sugestão concluída com base nos ativos cadastrados e nos universos mensais dos dois métodos.' : 'Cadastre ou importe posições para receber uma sugestão de metodologia.', discovery.status === 'READY' ? 'ok' : 'warn');
        return;
      }
      portfolio = await ensurePermanentStrategy(portfolio, sleeve);
      const result = engine.analyzePortfolio({ portfolio, accounts: data.accounts, holdings: data.holdings, riskAssets, sleeve });
      await window.IAEMLOOPAuth.requireApprovedSession();
      if (requestId !== analysisGeneration) return;
      renderAnalysis(result, portfolio);
      setServiceStatus('analysis-status', result.assetCount ? 'Análise concluída com dados privados da sessão e gate mensal de outubro.' : 'Análise incompleta: cadastre posições para obter pesos e concentração.', result.assetCount ? 'ok' : 'warn');
      await syncServicePortfolios(true);
    } catch (error) {
      if (requestId === analysisGeneration) setServiceStatus('analysis-status', `Não foi possível analisar: ${error.message}`, 'error');
    } finally {
      if (requestId === analysisGeneration) setPending(form, false);
    }
  }

  function parseTickerList(text) {
    return [...new Set(String(text || '').toUpperCase().split(/[\s,;]+/).map((value) => value.trim()).filter((value) => /^[A-Z0-9.\-]+$/.test(value)))];
  }

  function parseManualQuotes(text) {
    const quotes = {};
    const invalidLines = [];
    String(text || '').split(/\r?\n/).forEach((line) => {
      if (!line.trim()) return;
      const match = line.trim().match(/^([A-Za-z0-9.\-]+)\s*[=:;]\s*(\d+(?:[.,]\d+)?)$/);
      if (!match) invalidLines.push(line.trim());
      else quotes[match[1].toUpperCase()] = match[2].replace(',', '.');
    });
    return { quotes, invalidLines };
  }

  function validatedFetchedQuotes(fetched, currency) {
    const quotes = {};
    const metadata = {};
    const warnings = [];
    if (!Object.keys(fetched || {}).length) warnings.push('O provedor público não retornou cotações; informe preços manualmente para os tickers desejados.');
    const now = Date.now();
    Object.entries(fetched || {}).forEach(([symbol, meta]) => {
      const quotedAt = Date.parse(meta.quotedAt || '');
      if (meta.currency !== currency) warnings.push(`${symbol}: moeda da cotação incompatível.`);
      else if (!Number.isFinite(quotedAt) || now - quotedAt > MAX_QUOTE_AGE_MS || quotedAt - now > 5 * 60 * 1000) warnings.push(`${symbol}: cotação pública ausente ou antiga.`);
      else {
        quotes[symbol] = meta.price;
        metadata[symbol] = meta;
      }
    });
    return { quotes, metadata, warnings };
  }

  function renderContribution(plan, portfolio, quoteMetadata, inputSummary) {
    const output = byId('contribution-output');
    output.replaceChildren();
    const heading = node('div', null, 'service-result-heading');
    const status = STATUS_NAMES[plan.status] || plan.status;
    heading.append(node('h3', `Sugestão para ${portfolio.name}`), node('p', `${STRATEGY_NAMES[plan.sleeve]} · ${status}. ${inputSummary}`, 'muted-copy'));
    output.appendChild(heading);
    if (plan.message) output.appendChild(node('p', plan.message, 'service-alert'));
    const currency = plan.currency || portfolio.base_currency;
    const metrics = node('div', null, 'service-metrics');
    addMetric(metrics, 'Disponível', moneyMinor(plan.availableMinor ?? 0, currency));
    addMetric(metrics, 'Ordens sugeridas', plan.orders.length);
    addMetric(metrics, 'Saldo residual', moneyMinor(plan.residualMinor ?? plan.availableMinor ?? 0, currency));
    addMetric(metrics, 'Ativos após aporte', plan.assetCountAfter == null ? '—' : plan.assetCountAfter);
    output.appendChild(metrics);

    if (plan.orders.length) {
      const wrap = node('div', null, 'table-wrap service-table');
      const table = node('table');
      const head = node('thead');
      const headRow = node('tr');
      ['Ticker', 'Ação', 'Quantidade/estimativa', 'Preço usado', 'Valor', 'Origem da cotação'].forEach((label) => headRow.appendChild(node('th', label)));
      head.appendChild(headRow);
      const body = node('tbody');
      plan.orders.forEach((order) => {
        const row = node('tr');
        const quantity = order.quantity == null ? `≈ ${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 6 }).format(order.estimatedQuantity || 0)} fração` : String(order.quantity);
        const quote = quoteMetadata[order.ticker] || {};
        const quoteTime = quote.quotedAt ? ` · ${new Date(quote.quotedAt).toLocaleString('pt-BR')}` : '';
        [order.ticker, 'COMPRAR', quantity, moneyMinor(order.unitPriceMinor, currency), moneyMinor(order.totalMinor, currency), `${quote.source || 'informada manualmente'}${quoteTime}`].forEach((value) => row.appendChild(node('td', value)));
        body.appendChild(row);
      });
      table.append(head, body);
      wrap.appendChild(table);
      output.appendChild(wrap);
    }
    addList(output, 'Candidatos não utilizados', plan.rejectedCandidates.map((item) => `${item.ticker}: ${REJECTION_NAMES[item.reason] || item.reason}`), 'Nenhum candidato adicional foi rejeitado.');
    addList(output, 'Avisos', plan.warnings || [], 'Sem avisos adicionais.');
    output.appendChild(node('p', 'Prévia local não assinada e não executável. Nenhuma ordem, câmbio, remessa ou movimentação foi realizada. Alterar preço, valor, revisão, dossiê ou ticker exige uma nova proposta.', 'service-disclaimer'));
  }

  async function handleContribution(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const requestId = ++contributionGeneration;
    byId('contribution-output').replaceChildren();
    setPending(form, true);
    setServiceStatus('contribution-status', 'Consultando rankings, risco e cotações públicas...', 'info');
    try {
      const [data, riskAssets] = await Promise.all([loadPrivateData(true), loadRiskGate()]);
      let portfolio = selectedPortfolio(data, 'contribution-portfolio');
      const sleeve = byId('contribution-sleeve').value;
      if (!portfolio) throw new Error('Selecione uma carteira.');
      portfolio = await ensurePermanentStrategy(portfolio, sleeve);
      const candidates = riskAssets.filter((row) => row.sleeve === sleeve && !String(row.aporte_status || '').startsWith('bloqueado'));
      const fetched = await quoteService.fetchQuotes(candidates.map((row) => row.ticker), sleeve);
      const expectedCurrency = engine.SLEEVES[sleeve].currency;
      const validated = validatedFetchedQuotes(fetched, expectedCurrency);
      const manual = parseManualQuotes(byId('contribution-manual-quotes').value);
      if (manual.invalidLines.length) throw new Error(`Cotações manuais inválidas: ${manual.invalidLines.join(' | ')}`);
      const quotes = { ...validated.quotes, ...manual.quotes };
      const quoteMetadata = { ...validated.metadata };
      Object.entries(manual.quotes).forEach(([symbol, price]) => {
        quoteMetadata[symbol] = { price: Number(price), currency: expectedCurrency, quotedAt: new Date().toISOString(), source: 'informada manualmente' };
      });
      const plan = engine.planContribution({
        portfolio,
        accounts: data.accounts,
        holdings: data.holdings,
        riskAssets,
        sleeve,
        amount: byId('contribution-amount').value,
        proceeds: byId('contribution-proceeds').value,
        fees: byId('contribution-fees').value,
        requestedOrderCount: byId('contribution-count').value,
        approvedReviewTickers: parseTickerList(byId('contribution-reviewed-tickers').value),
        approvedDossierTickers: parseTickerList(byId('contribution-dossier-tickers').value),
        quotes
      });
      plan.warnings = [...(plan.warnings || []), ...validated.warnings];
      await window.IAEMLOOPAuth.requireApprovedSession();
      if (requestId !== contributionGeneration) return;
      const inputSummary = `Base ${byId('contribution-amount').value}; proventos/sobras ${byId('contribution-proceeds').value}; taxas ${byId('contribution-fees').value}.`;
      renderContribution(plan, portfolio, quoteMetadata, inputSummary);
      const kind = plan.status === 'AWAITING_HUMAN_APPROVAL' ? 'ok' : 'warn';
      setServiceStatus('contribution-status', plan.status === 'AWAITING_HUMAN_APPROVAL' ? 'Sugestão preparada. Revise preços e ordens antes de qualquer execução manual.' : (plan.message || 'A proposta ficou bloqueada pelos critérios informados.'), kind);
      await syncServicePortfolios(true);
    } catch (error) {
      if (requestId === contributionGeneration) setServiceStatus('contribution-status', `Não foi possível preparar o aporte: ${error.message}`, 'error');
    } finally {
      if (requestId === contributionGeneration) setPending(form, false);
    }
  }

  function clearOutputs() {
    analysisGeneration += 1;
    contributionGeneration += 1;
    privateDataCache = null;
    ['analysis-output', 'contribution-output'].forEach((id) => byId(id)?.replaceChildren());
    ['analysis-portfolio', 'contribution-portfolio'].forEach((id) => {
      const select = byId(id);
      if (select) select.replaceChildren(node('option', 'Sessão encerrada'));
    });
    ['contribution-manual-quotes', 'contribution-reviewed-tickers', 'contribution-dossier-tickers'].forEach((id) => { if (byId(id)) byId(id).value = ''; });
    [byId('analysis-form'), byId('contribution-form')].filter(Boolean).forEach((form) => setPending(form, true));
    setServiceStatus('analysis-status', 'Sessão encerrada; a análise foi removida da tela.', 'warn');
    setServiceStatus('contribution-status', 'Sessão encerrada; a sugestão foi removida da tela.', 'warn');
  }

  async function refreshServiceState() {
    privateDataCache = null;
    try { await syncServicePortfolios(true); } catch (_) {}
  }

  async function start() {
    if (!byId('analysis-form') || !byId('contribution-form')) return;
    byId('analysis-form').addEventListener('submit', handleAnalysis);
    byId('contribution-form').addEventListener('submit', handleContribution);
    byId('analysis-portfolio').addEventListener('change', async () => syncMethodForPortfolio(await loadPrivateData(), 'analysis-portfolio', 'analysis-sleeve', true));
    byId('contribution-portfolio').addEventListener('change', async () => syncMethodForPortfolio(await loadPrivateData(), 'contribution-portfolio', 'contribution-sleeve'));
    document.addEventListener('iaemloop:session-invalidated', clearOutputs);
    document.addEventListener('iaemloop:portfolio-data-refreshed', refreshServiceState);
    try { await syncServicePortfolios(true); } catch (error) {
      setServiceStatus('analysis-status', `Serviço indisponível: ${error.message}`, 'error');
      setServiceStatus('contribution-status', `Serviço indisponível: ${error.message}`, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', start);
})();
