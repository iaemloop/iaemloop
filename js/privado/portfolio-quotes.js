(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IAEMLOOPPortfolioQuotes = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function extractJson(text) {
    const source = String(text || '');
    const start = source.indexOf('{');
    const end = source.lastIndexOf('}');
    if (start < 0 || end <= start) return null;
    try { return JSON.parse(source.slice(start, end + 1)); } catch (_) { return null; }
  }

  function parseYahooSpark(text) {
    const json = extractJson(text);
    const result = json?.spark?.result || [];
    const quotes = {};
    result.forEach((item) => {
      const meta = item?.response?.[0]?.meta || {};
      const price = Number(meta.regularMarketPrice);
      if (item.symbol && Number.isFinite(price) && price > 0) {
        quotes[String(item.symbol).replace(/-/g, '.').toUpperCase()] = {
          price,
          currency: meta.currency || 'USD',
          quotedAt: meta.regularMarketTime ? new Date(meta.regularMarketTime * 1000).toISOString() : new Date().toISOString(),
          source: 'Yahoo Finance via Jina'
        };
      }
    });
    return quotes;
  }

  async function fetchB3(tickers, deadline) {
    const quotes = {};
    for (let index = 0; index < tickers.length; index += 4) {
      if (Date.now() >= deadline) break;
      const batch = tickers.slice(index, index + 4);
      const url = `https://brapi.dev/api/quote/${batch.map(encodeURIComponent).join(',')}?range=1d&interval=1d&fundamental=false&dividends=false`;
      try {
        const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(Math.max(500, Math.min(5000, deadline - Date.now()))) });
        if (!response.ok) continue;
        const data = await response.json();
        (data.results || []).forEach((item) => {
          const price = Number(item.regularMarketPrice);
          if (item.symbol && Number.isFinite(price) && price > 0) quotes[String(item.symbol).toUpperCase()] = { price, currency: 'BRL', quotedAt: item.regularMarketTime ? new Date(item.regularMarketTime).toISOString() : new Date().toISOString(), source: 'brapi.dev' };
        });
      } catch (_) {}
    }
    return quotes;
  }

  async function fetchUsd(tickers, deadline) {
    const quotes = {};
    for (let index = 0; index < tickers.length; index += 20) {
      if (Date.now() >= deadline) break;
      const batch = tickers.slice(index, index + 20).map((symbol) => symbol.replace(/\./g, '-'));
      const target = `https://query1.finance.yahoo.com/v7/finance/spark?symbols=${encodeURIComponent(batch.join(','))}&range=1d&interval=1d`;
      try {
        const response = await fetch(`https://r.jina.ai/${target}`, { cache: 'no-store', signal: AbortSignal.timeout(Math.max(500, Math.min(7000, deadline - Date.now()))) });
        if (!response.ok) continue;
        Object.assign(quotes, parseYahooSpark(await response.text()));
      } catch (_) {}
    }
    return quotes;
  }

  async function fetchQuotes(tickers, sleeve, timeoutMs = 12000) {
    const unique = [...new Set((tickers || []).map((value) => String(value || '').trim().toUpperCase()).filter(Boolean))];
    const deadline = Date.now() + timeoutMs;
    return sleeve.endsWith('-b3') ? fetchB3(unique, deadline) : fetchUsd(unique, deadline);
  }

  return { extractJson, parseYahooSpark, fetchQuotes };
});
