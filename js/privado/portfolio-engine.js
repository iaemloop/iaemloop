(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IAEMLOOPPortfolioEngine = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SLEEVES = Object.freeze({
    'besst-b3': { currency: 'BRL', market: 'B3', minimumNames: 1 },
    'magic-b3': { currency: 'BRL', market: 'B3', minimumNames: 1 },
    'besst-usd': { currency: 'USD', market: 'US', minimumNames: 3 },
    'magic-usd': { currency: 'USD', market: 'US', minimumNames: 3 }
  });

  function ticker(value) {
    return String(value || '').trim().toUpperCase();
  }

  function finiteNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function toMinor(value) {
    const normalized = String(value == null ? '0' : value).trim().replace(',', '.');
    if (!/^-?\d+(?:\.\d+)?$/.test(normalized)) return null;
    const sign = normalized.startsWith('-') ? -1 : 1;
    const absolute = normalized.replace(/^-/, '');
    const [whole, fraction = ''] = absolute.split('.');
    const cents = `${fraction}00`.slice(0, 2);
    const third = Number(`${fraction}000`.charAt(2));
    const result = sign * (Number(whole) * 100 + Number(cents) + (third >= 5 ? 1 : 0));
    return Number.isSafeInteger(result) && Math.abs(result) <= 10000000000 ? result : null;
  }

  function rankOf(row, index) {
    const raw = row.rank_final ?? row.rank ?? row.rank_geral ?? row.posicao;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : index + 1;
  }

  function sleeveRows(riskAssets, sleeve) {
    return (riskAssets || [])
      .filter((row) => row.sleeve === sleeve)
      .map((row, index) => ({ ...row, ticker: ticker(row.ticker), normalizedRank: rankOf(row, index), sourceRow: index + 1 }))
      .sort((a, b) => a.normalizedRank - b.normalizedRank || a.sourceRow - b.sourceRow || a.ticker.localeCompare(b.ticker));
  }

  function aggregateHoldings(holdings, portfolioId, expectedCurrency) {
    const grouped = new Map();
    (holdings || []).filter((row) => row.portfolio_id === portfolioId && Number(row.quantity) > 0 && (!expectedCurrency || row.currency === expectedCurrency)).forEach((row) => {
      const symbol = ticker(row.symbol);
      if (!symbol) return;
      const quantity = finiteNumber(row.quantity) || 0;
      const averageCost = finiteNumber(row.average_cost);
      const current = grouped.get(symbol) || { ticker: symbol, quantity: 0, knownCostMinor: 0, unknownCostRows: 0, currencies: new Set(), assetTypes: new Set(), accounts: new Set() };
      current.quantity += quantity;
      if (averageCost == null) current.unknownCostRows += 1;
      else current.knownCostMinor += Math.round(quantity * averageCost * 100);
      current.currencies.add(String(row.currency || ''));
      current.assetTypes.add(String(row.asset_type || 'other'));
      current.accounts.add(String(row.account_id || ''));
      grouped.set(symbol, current);
    });
    return [...grouped.values()].sort((a, b) => a.ticker.localeCompare(b.ticker));
  }

  function analyzePortfolio(input) {
    const portfolio = input.portfolio || {};
    const sleeve = input.sleeve;
    const config = SLEEVES[sleeve];
    if (!config) throw new Error('Estratégia inválida.');
    if (portfolio.strategy_key && portfolio.strategy_key !== sleeve) throw new Error('O método selecionado não corresponde ao vínculo permanente desta carteira.');
    const positions = aggregateHoldings(input.holdings, portfolio.id, config.currency);
    const excludedCurrencyHoldings = [...new Set((input.holdings || [])
      .filter((row) => row.portfolio_id === portfolio.id && Number(row.quantity) > 0 && row.currency !== config.currency)
      .map((row) => ticker(row.symbol)).filter(Boolean))].sort();
    const ranking = sleeveRows(input.riskAssets, sleeve);
    const ranked = new Map(ranking.map((row) => [row.ticker, row]));
    const knownCostMinor = positions.reduce((sum, row) => sum + row.knownCostMinor, 0);
    const topPositions = positions.map((row) => ({
      ticker: row.ticker,
      knownCostMinor: row.knownCostMinor,
      weightPct: knownCostMinor > 0 ? Math.round((row.knownCostMinor / knownCostMinor) * 10000) / 100 : 0,
      quantity: row.quantity
    })).sort((a, b) => b.knownCostMinor - a.knownCostMinor || a.ticker.localeCompare(b.ticker));
    const rankedHoldings = positions.filter((row) => ranked.has(row.ticker)).map((row) => ({ ticker: row.ticker, rank: ranked.get(row.ticker).normalizedRank }));
    const outOfRanking = positions.filter((row) => !ranked.has(row.ticker)).map((row) => row.ticker);
    const blockedHoldings = positions.filter((row) => {
      const gate = ranked.get(row.ticker);
      return gate && (String(gate.aporte_status || '').startsWith('bloqueado') || String(gate.risco_estrutural_status || '').includes('veto'));
    }).map((row) => row.ticker);
    const accountCash = {};
    (input.accounts || []).filter((row) => row.portfolio_id === portfolio.id).forEach((row) => {
      const currency = String(row.currency || portfolio.base_currency || config.currency);
      accountCash[currency] = (accountCash[currency] || 0) + (toMinor(row.cash_balance) || 0);
    });
    const warnings = [];
    if (portfolio.base_currency && portfolio.base_currency !== config.currency) warnings.push(`A moeda-base ${portfolio.base_currency} não corresponde à estratégia ${config.currency}.`);
    if (excludedCurrencyHoldings.length) warnings.push(`Há ${excludedCurrencyHoldings.length} ativo(s) em moeda incompatível; eles foram excluídos dos totais e pesos.`);
    if (!positions.length) warnings.push('Cadastre posições nesta carteira para obter uma análise completa.');
    if (positions.length > 15) warnings.push('A carteira ultrapassa o limite operacional de 15 ativos.');
    if (positions.some((row) => row.unknownCostRows)) warnings.push('Há posições sem custo conhecido; os pesos por custo são parciais.');
    if (blockedHoldings.length) warnings.push('Há ativos em custódia bloqueados para novos aportes pelo gate atual; isso não gera venda automática.');
    if (topPositions[0]?.weightPct > 35) warnings.push('A maior posição supera 35% do custo conhecido da carteira.');
    return {
      sleeve,
      currency: config.currency,
      assetCount: positions.length,
      capacityRemaining: Math.max(0, 15 - positions.length),
      knownCostMinor,
      unknownCostRows: positions.reduce((sum, row) => sum + row.unknownCostRows, 0),
      topPositions,
      rankedHoldings,
      outOfRanking,
      blockedHoldings,
      excludedCurrencyHoldings,
      accountCash,
      warnings,
      methodology: 'Pesos calculados pelo custo cadastrado; BRL e USD nunca são somados.'
    };
  }

  function round2(value) {
    return Math.round(Number(value || 0) * 100) / 100;
  }

  function methodologyFit(positions, riskAssets, sleeve) {
    const ranking = sleeveRows(riskAssets, sleeve);
    const byTicker = new Map(ranking.map((row) => [row.ticker, row]));
    const matched = positions.filter((position) => byTicker.has(position.ticker));
    const totalKnownCostMinor = positions.reduce((sum, position) => sum + position.knownCostMinor, 0);
    const matchedKnownCostMinor = matched.reduce((sum, position) => sum + position.knownCostMinor, 0);
    const countCoveragePct = positions.length ? (matched.length / positions.length) * 100 : 0;
    const costCoveragePct = totalKnownCostMinor > 0 ? (matchedKnownCostMinor / totalKnownCostMinor) * 100 : countCoveragePct;
    const rankQualityPct = matched.length ? matched.reduce((sum, position) => {
      const rank = byTicker.get(position.ticker).normalizedRank;
      const denominator = Math.max(1, ranking.length - 1);
      return sum + Math.max(0, Math.min(100, 100 - ((rank - 1) / denominator) * 100));
    }, 0) / matched.length : 0;
    const score = totalKnownCostMinor > 0
      ? costCoveragePct * 0.65 + countCoveragePct * 0.25 + rankQualityPct * 0.10
      : countCoveragePct * 0.80 + rankQualityPct * 0.20;
    return {
      sleeve,
      score: round2(score),
      matchedCount: matched.length,
      countCoveragePct: round2(countCoveragePct),
      costCoveragePct: round2(costCoveragePct),
      rankQualityPct: round2(rankQualityPct),
      matchedTickers: matched.map((position) => position.ticker),
      unmatchedTickers: positions.filter((position) => !byTicker.has(position.ticker)).map((position) => position.ticker),
      evidence: matched.map((position) => {
        const row = byTicker.get(position.ticker);
        return {
          ticker: position.ticker,
          rank: row.normalizedRank,
          setor: row.setor || row.segmento || null,
          dividendYield: finiteNumber(row.dividend_yield),
          dividendYears: finiteNumber(row.anos_com_dividendos),
          roic: finiteNumber(row.roic),
          earningsYield: finiteNumber(row.earnings_yield)
        };
      })
    };
  }

  function fitReason(label, fit, positionsCount) {
    const costPart = fit.costCoveragePct > 0 ? ` e ${fit.costCoveragePct}% do custo conhecido` : '';
    return `${label}: ${fit.matchedCount} de ${positionsCount} ativo(s) aparecem no universo mensal do método${costPart}; pontuação explicável ${fit.score}/100.`;
  }

  function discoverMarketMethodology(portfolio, holdings, riskAssets, currency) {
    const suffix = currency === 'USD' ? 'usd' : 'b3';
    const besstSleeve = `besst-${suffix}`;
    const magicSleeve = `magic-${suffix}`;
    const positions = aggregateHoldings(holdings, portfolio.id, currency);
    if (!positions.length) return null;
    const besst = methodologyFit(positions, riskAssets, besstSleeve);
    const magic = methodologyFit(positions, riskAssets, magicSleeve);
    const difference = Math.abs(besst.score - magic.score);
    let recommendation = 'inconclusive';
    let suggestedSleeves = [];
    if (besst.matchedCount || magic.matchedCount) {
      if (besst.matchedCount && magic.matchedCount && difference <= 15) {
        recommendation = 'both';
        suggestedSleeves = [besstSleeve, magicSleeve];
      } else if (besst.score > magic.score) {
        recommendation = 'besst';
        suggestedSleeves = [besstSleeve];
      } else if (magic.score > besst.score) {
        recommendation = 'magic';
        suggestedSleeves = [magicSleeve];
      } else {
        recommendation = 'both';
        suggestedSleeves = [besstSleeve, magicSleeve];
      }
    }
    const top = [...positions].sort((a, b) => b.knownCostMinor - a.knownCostMinor || a.ticker.localeCompare(b.ticker));
    const knownCostMinor = positions.reduce((sum, position) => sum + position.knownCostMinor, 0);
    const largestWeightPct = knownCostMinor > 0 && top[0] ? round2((top[0].knownCostMinor / knownCostMinor) * 100) : 0;
    const reasons = [
      fitReason('BESST & Buffett', besst, positions.length),
      fitReason('Magic Formula', magic, positions.length)
    ];
    if (recommendation === 'both') reasons.push('Há aderência relevante e próxima aos dois métodos. “Ambas” significa que os ativos atuais oferecem pontos de partida para as duas abordagens; não significa misturar carteiras nem vender posições automaticamente.');
    if (recommendation === 'besst') reasons.push('A maior aderência está no BESST & Buffett, que prioriza qualidade, perenidade, histórico e retorno ao acionista.');
    if (recommendation === 'magic') reasons.push('A maior aderência está na Magic Formula, que prioriza retorno sobre capital e preço relativo aos resultados.');
    if (recommendation === 'inconclusive') reasons.push('Os ativos atuais não aparecem nos universos mensais usados. É necessária revisão fundamentalista individual antes de escolher um método.');
    const warnings = [];
    const outsideBoth = positions.filter((position) => !besst.matchedTickers.includes(position.ticker) && !magic.matchedTickers.includes(position.ticker)).map((position) => position.ticker);
    if (outsideBoth.length) warnings.push(`${outsideBoth.join(', ')}: fora do ranking mensal dos dois métodos; ausência no ranking não prova que o ativo seja inadequado.`);
    if (positions.length > 15) warnings.push('A custódia ultrapassa 15 ativos; revise pulverização antes de abrir novas posições.');
    if (largestWeightPct > 35) warnings.push(`${top[0].ticker} representa ${largestWeightPct}% do custo conhecido; há alerta de concentração.`);
    if (positions.some((position) => position.unknownCostRows)) warnings.push('Há posições sem custo conhecido; a aderência por peso é parcial.');
    return {
      currency,
      assetCount: positions.length,
      knownCostMinor,
      largestWeightPct,
      recommendation,
      suggestedSleeves,
      fits: { besst, magic },
      reasons,
      warnings,
      disclaimer: 'A sugestão mede aderência aos universos e critérios mensais disponíveis. Ela não compara carteiras, não ordena vendas e não substitui o dossiê individual de cada empresa.'
    };
  }

  function discoverMethodology(input) {
    const portfolio = input.portfolio || {};
    if (!portfolio.id) throw new Error('Carteira inválida.');
    const currencies = [...new Set((input.holdings || [])
      .filter((row) => row.portfolio_id === portfolio.id && Number(row.quantity) > 0)
      .map((row) => String(row.currency || portfolio.base_currency || 'BRL').toUpperCase())
      .filter((currency) => currency === 'BRL' || currency === 'USD'))];
    const markets = currencies.map((currency) => discoverMarketMethodology(portfolio, input.holdings, input.riskAssets, currency)).filter(Boolean);
    return {
      status: markets.length ? 'READY' : 'NO_HOLDINGS',
      portfolioId: portfolio.id,
      markets,
      methodology: 'Aderência calculada separadamente por moeda e pelos ativos cadastrados; BRL e USD nunca são somados.'
    };
  }

  function candidateIsBlocked(row) {
    return String(row.aporte_status || '').startsWith('bloqueado') || String(row.risco_estrutural_status || '').includes('veto');
  }

  function currentValuesByTicker(positions, quoteMinor) {
    const result = new Map();
    positions.forEach((position) => {
      const price = quoteMinor.get(position.ticker);
      result.set(position.ticker, price ? Math.round(position.quantity * price) : position.knownCostMinor);
    });
    return result;
  }

  function planContribution(input) {
    const sleeve = input.sleeve;
    const config = SLEEVES[sleeve];
    const portfolio = input.portfolio || {};
    const rejectedCandidates = [];
    const warnings = [];
    if (!config) return emptyPlan('INVALID_INPUT', sleeve, 'Estratégia inválida.');
    if (!portfolio.strategy_key || portfolio.strategy_key !== sleeve) return emptyPlan('INVALID_INPUT', sleeve, 'A carteira precisa estar vinculada permanentemente a este método.');
    if (portfolio.base_currency && portfolio.base_currency !== config.currency) return emptyPlan('INVALID_INPUT', sleeve, 'Moeda da carteira incompatível com a estratégia.');
    const amountMinor = toMinor(input.amount);
    const proceedsMinor = toMinor(input.proceeds || 0);
    const feesMinor = toMinor(input.fees || 0);
    if (amountMinor == null || proceedsMinor == null || feesMinor == null || amountMinor < 0 || proceedsMinor < 0 || feesMinor < 0) return emptyPlan('INVALID_INPUT', sleeve, 'Valores inválidos.');
    const availableMinor = amountMinor + proceedsMinor - feesMinor;
    if (availableMinor <= 0) return emptyPlan('BLOCKED_BUDGET', sleeve, 'Não há valor disponível após taxas.', { amountMinor, proceedsMinor, feesMinor });
    const mismatchedHoldings = (input.holdings || []).filter((row) => row.portfolio_id === portfolio.id && Number(row.quantity) > 0 && row.currency !== config.currency);
    if (mismatchedHoldings.length) return emptyPlan('INVALID_INPUT', sleeve, 'Existem posições em moeda incompatível nesta carteira. Corrija a custódia antes de gerar o aporte.', { amountMinor, proceedsMinor, feesMinor, availableMinor });
    const approvedReviews = new Set((input.approvedReviewTickers || []).map(ticker));
    const approvedDossiers = new Set((input.approvedDossierTickers || []).map(ticker));
    if (!approvedReviews.size) return emptyPlan('BLOCKED_REVIEW', sleeve, 'Informe os tickers com revisão corporativa mensal aprovada.', { amountMinor, proceedsMinor, feesMinor, availableMinor });

    const positions = aggregateHoldings(input.holdings, portfolio.id, config.currency);
    const held = new Set(positions.map((row) => row.ticker));
    const slots = Math.max(0, 15 - held.size);
    const quoteMinor = new Map(Object.entries(input.quotes || {}).map(([symbol, price]) => [ticker(symbol), toMinor(price)]));
    const currentValues = currentValuesByTicker(positions, quoteMinor);
    const candidates = [];
    sleeveRows(input.riskAssets, sleeve).forEach((row) => {
      const isHeld = held.has(row.ticker);
      let reason = null;
      if (candidateIsBlocked(row)) reason = 'RISK_VETO';
      else if (!approvedReviews.has(row.ticker)) reason = 'MONTHLY_REVIEW_REQUIRED';
      else if (!isHeld && !approvedDossiers.has(row.ticker)) reason = 'DOSSIER_REQUIRED';
      else if (!isHeld && slots <= 0) reason = 'ASSET_LIMIT';
      const priceMinor = quoteMinor.get(row.ticker);
      if (!reason && (!Number.isInteger(priceMinor) || priceMinor <= 0)) reason = 'QUOTE_REQUIRED';
      if (reason) rejectedCandidates.push({ ticker: row.ticker, rank: row.normalizedRank, reason });
      else candidates.push({ ...row, held: isHeld, priceMinor, currentValueMinor: currentValues.get(row.ticker) || 0 });
    });

    candidates.sort((a, b) => {
      if (slots <= 2 && a.held !== b.held) return a.held ? -1 : 1;
      return a.currentValueMinor - b.currentValueMinor || a.normalizedRank - b.normalizedRank || a.sourceRow - b.sourceRow || a.ticker.localeCompare(b.ticker);
    });

    let requested = Math.max(1, Math.floor(Number(input.requestedOrderCount) || config.minimumNames));
    if (config.market === 'US') requested = Math.max(3, requested);
    const selected = [];
    let newSelected = 0;
    for (const candidate of candidates) {
      if (selected.length >= requested) break;
      if (!candidate.held && newSelected >= slots) {
        rejectedCandidates.push({ ticker: candidate.ticker, rank: candidate.normalizedRank, reason: 'ASSET_LIMIT' });
        continue;
      }
      if (config.market === 'B3' && candidate.priceMinor > availableMinor) {
        rejectedCandidates.push({ ticker: candidate.ticker, rank: candidate.normalizedRank, reason: 'BUDGET' });
        continue;
      }
      selected.push(candidate);
      if (!candidate.held) newSelected += 1;
    }
    if (!selected.length) return emptyPlan('NO_ELIGIBLE_CANDIDATES', sleeve, 'Nenhum candidato elegível com cotação válida.', { amountMinor, proceedsMinor, feesMinor, availableMinor, rejectedCandidates });
    if (config.market === 'US' && selected.length < 3) return emptyPlan('BLOCKED_US_MINIMUM_NAMES', sleeve, 'A carteira dolarizada exige ao menos três nomes elegíveis.', { amountMinor, proceedsMinor, feesMinor, availableMinor, rejectedCandidates });
    if (config.market === 'US' && availableMinor < selected.length) return emptyPlan('BLOCKED_US_MINIMUM_NAMES', sleeve, 'O valor disponível não permite uma alocação positiva em pelo menos três nomes.', { amountMinor, proceedsMinor, feesMinor, availableMinor, rejectedCandidates });

    const orders = config.market === 'B3'
      ? allocateB3(selected, availableMinor)
      : allocateUsd(selected, availableMinor);
    if (!orders.length) return emptyPlan('BLOCKED_BUDGET', sleeve, 'O valor não compra a quantidade mínima dos candidatos.', { amountMinor, proceedsMinor, feesMinor, availableMinor, rejectedCandidates });
    const spentMinor = orders.reduce((sum, row) => sum + row.totalMinor, 0);
    const residualMinor = availableMinor - spentMinor;
    if (orders.length < requested) warnings.push(`A proposta contém ${orders.length} ativo(s), abaixo dos ${requested} solicitados, por limites de elegibilidade, preço ou capacidade.`);
    return {
      status: 'AWAITING_HUMAN_APPROVAL',
      sleeve,
      currency: config.currency,
      amountMinor,
      proceedsMinor,
      feesMinor,
      availableMinor,
      assetCountBefore: held.size,
      assetCountAfter: held.size + orders.filter((row) => row.isNewTicker).length,
      orders,
      residualMinor,
      rejectedCandidates: stableRejected(rejectedCandidates),
      warnings,
      automaticExecutionAllowed: false,
      execution: { performed: false, ordersSubmitted: 0 },
      approval: { required: true, status: 'pending' }
    };
  }

  function allocateB3(selected, availableMinor) {
    let remaining = availableMinor;
    const active = selected.filter((candidate) => candidate.priceMinor <= remaining).map((candidate) => ({ candidate, quantity: 0, projectedMinor: candidate.currentValueMinor }));
    for (const row of active) {
      if (row.candidate.priceMinor > remaining) continue;
      row.quantity += 1;
      row.projectedMinor += row.candidate.priceMinor;
      remaining -= row.candidate.priceMinor;
    }
    if (active.length && remaining > 0) {
      const baseProjected = active.map((row) => row.projectedMinor);
      const costAtTarget = (target) => active.reduce((sum, row, index) => {
        const steps = Math.max(0, Math.floor((target - baseProjected[index]) / row.candidate.priceMinor));
        return sum + steps * row.candidate.priceMinor;
      }, 0);
      let low = Math.min(...baseProjected);
      let high = Math.max(...baseProjected) + remaining + Math.max(...active.map((row) => row.candidate.priceMinor));
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        if (costAtTarget(middle) <= remaining) low = middle;
        else high = middle - 1;
      }
      active.forEach((row, index) => {
        const extra = Math.max(0, Math.floor((low - baseProjected[index]) / row.candidate.priceMinor));
        row.quantity += extra;
        row.projectedMinor += extra * row.candidate.priceMinor;
        remaining -= extra * row.candidate.priceMinor;
      });
      active.sort((a, b) => a.projectedMinor - b.projectedMinor || a.candidate.normalizedRank - b.candidate.normalizedRank || a.candidate.ticker.localeCompare(b.candidate.ticker));
      for (const row of active) {
        if (row.candidate.priceMinor <= remaining) {
          row.quantity += 1;
          row.projectedMinor += row.candidate.priceMinor;
          remaining -= row.candidate.priceMinor;
        }
      }
    }
    return active.filter((row) => row.quantity > 0).map((row) => ({
      ticker: row.candidate.ticker,
      side: 'BUY',
      quantity: row.quantity,
      unitPriceMinor: row.candidate.priceMinor,
      totalMinor: row.quantity * row.candidate.priceMinor,
      isNewTicker: !row.candidate.held,
      rank: row.candidate.normalizedRank
    })).sort((a, b) => a.rank - b.rank || a.ticker.localeCompare(b.ticker));
  }

  function allocateUsd(selected, availableMinor) {
    if (availableMinor < selected.length) return [];
    const allocations = selected.map((candidate) => ({ candidate, totalMinor: 1, projectedMinor: candidate.currentValueMinor + 1 }));
    let remaining = availableMinor - allocations.length;
    while (remaining > 0) {
      allocations.sort((a, b) => a.projectedMinor - b.projectedMinor || a.candidate.normalizedRank - b.candidate.normalizedRank || a.candidate.ticker.localeCompare(b.candidate.ticker));
      let groupSize = 1;
      while (groupSize < allocations.length && allocations[groupSize].projectedMinor === allocations[0].projectedMinor) groupSize += 1;
      const nextLevel = groupSize < allocations.length ? allocations[groupSize].projectedMinor : null;
      if (nextLevel != null) {
        const needed = (nextLevel - allocations[0].projectedMinor) * groupSize;
        if (needed <= remaining) {
          for (let index = 0; index < groupSize; index += 1) {
            const share = nextLevel - allocations[index].projectedMinor;
            allocations[index].totalMinor += share;
            allocations[index].projectedMinor += share;
          }
          remaining -= needed;
          continue;
        }
      }
      const share = Math.floor(remaining / groupSize);
      if (share > 0) {
        for (let index = 0; index < groupSize; index += 1) {
          allocations[index].totalMinor += share;
          allocations[index].projectedMinor += share;
        }
        remaining -= share * groupSize;
      }
      for (let index = 0; index < remaining; index += 1) {
        allocations[index].totalMinor += 1;
        allocations[index].projectedMinor += 1;
      }
      remaining = 0;
    }
    return allocations.map((row) => ({
      ticker: row.candidate.ticker,
      side: 'BUY',
      quantity: null,
      unitPriceMinor: row.candidate.priceMinor,
      totalMinor: row.totalMinor,
      estimatedQuantity: row.candidate.priceMinor > 0 ? Math.round((row.totalMinor / row.candidate.priceMinor) * 1000000) / 1000000 : null,
      isNewTicker: !row.candidate.held,
      rank: row.candidate.normalizedRank
    })).sort((a, b) => a.rank - b.rank || a.ticker.localeCompare(b.ticker));
  }

  function stableRejected(rows) {
    const seen = new Set();
    return rows.filter((row) => {
      const key = `${row.ticker}:${row.reason}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).sort((a, b) => (a.rank || 9999) - (b.rank || 9999) || a.ticker.localeCompare(b.ticker) || a.reason.localeCompare(b.reason));
  }

  function emptyPlan(status, sleeve, message, extra) {
    return {
      status,
      sleeve,
      message,
      orders: [],
      rejectedCandidates: extra?.rejectedCandidates || [],
      warnings: [],
      automaticExecutionAllowed: false,
      execution: { performed: false, ordersSubmitted: 0 },
      approval: { required: true, status: 'pending' },
      ...(extra || {})
    };
  }

  return { SLEEVES, analyzePortfolio, discoverMethodology, planContribution, toMinor, rankOf, aggregateHoldings };
});
