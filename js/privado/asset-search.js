(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IAEMLOOPAssetSearch = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const APPROVED_CATALOG_URLS = Object.freeze([
    '/outputs/risk_gate_all_2026-10.json',
    '/outputs/besst_buffett_eua_latest.json',
    '/outputs/magic_formula_eua_latest.json'
  ]);

  const text = (value) => String(value == null ? '' : value).trim();
  const fold = (value) => text(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();

  function normalizedAsset(raw, source) {
    const symbol = text(raw.symbol || raw.ticker).toUpperCase();
    if (!/^[A-Z0-9.\-]{1,32}$/.test(symbol)) return null;
    const name = text(raw.name || raw.nome || raw.empresa || raw.company);
    const usd = text(raw.sleeve).endsWith('-usd') || !/\d/.test(symbol);
    return {
      symbol,
      name,
      currency: text(raw.currency || raw.moeda).toUpperCase() || (usd ? 'USD' : 'BRL'),
      assetType: text(raw.assetType || raw.asset_type) || 'equity',
      source
    };
  }

  function buildCatalog({ approvedAssets = [], holdings = [], transactions = [] } = {}) {
    const catalog = new Map();
    const add = (raw, source) => {
      const asset = normalizedAsset(raw, source);
      if (!asset) return;
      const current = catalog.get(asset.symbol);
      if (!current) catalog.set(asset.symbol, asset);
      else if (!current.name && asset.name) catalog.set(asset.symbol, { ...current, name: asset.name });
    };
    approvedAssets.forEach((asset) => add(asset, 'catálogo aprovado'));
    holdings.forEach((asset) => add(asset, 'minha carteira'));
    transactions.forEach((asset) => add(asset, 'meu histórico'));
    return [...catalog.values()].sort((a, b) => a.symbol.localeCompare(b.symbol));
  }

  function matchCatalog(catalog, query, limit = 12) {
    const needle = fold(query);
    const matches = (catalog || []).filter((asset) => !needle || fold(`${asset.symbol} ${asset.name}`).includes(needle));
    return matches.slice(0, limit);
  }

  function resolveSymbol(catalog, input) {
    const needle = fold(input);
    if (!needle) return '';
    const exact = (catalog || []).find((asset) => fold(asset.symbol) === needle || (asset.name && fold(asset.name) === needle));
    return exact ? exact.symbol : text(input).toUpperCase();
  }

  async function fetchApprovedAssets() {
    const results = await Promise.all(APPROVED_CATALOG_URLS.map(async (url) => {
      try {
        const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin' });
        if (!response.ok) return [];
        const payload = await response.json();
        return Array.isArray(payload.assets) ? payload.assets : [];
      } catch (_) {
        return [];
      }
    }));
    return results.flat();
  }

  function installBrowserController() {
    if (typeof document === 'undefined') return;
    const list = document.getElementById('asset-catalog');
    const privateApi = window.IAEMLOOPPortfolioAPI;
    if (!list || !privateApi) return;
    let catalog = [];
    let loading = null;
    let sessionGeneration = 0;

    function renderOptions() {
      list.replaceChildren();
      catalog.forEach((asset) => {
        const option = document.createElement('option');
        option.value = asset.symbol;
        option.label = [asset.name, asset.currency, asset.source].filter(Boolean).join(' · ');
        list.appendChild(option);
      });
    }

    async function refresh() {
      if (loading) return loading;
      const generation = sessionGeneration;
      loading = (async () => {
        await window.IAEMLOOPAuth.requireApprovedSession();
        const [approvedAssets, holdings, transactions] = await Promise.all([
          fetchApprovedAssets(), privateApi.listHoldings(), privateApi.listTransactions()
        ]);
        if (generation !== sessionGeneration) return;
        catalog = buildCatalog({ approvedAssets, holdings, transactions });
        renderOptions();
      })().finally(() => { loading = null; });
      return loading;
    }

    function normalizeInput(event) {
      event.target.value = resolveSymbol(catalog, event.target.value);
    }

    document.querySelectorAll('input[list="asset-catalog"]').forEach((input) => {
      input.addEventListener('focus', () => refresh().catch(() => {}), { once: true });
      input.addEventListener('change', normalizeInput);
    });
    document.querySelectorAll('form[data-form="holding"], form[data-form="transaction"]').forEach((form) => {
      form.addEventListener('submit', (event) => {
        const input = event.currentTarget.elements.symbol;
        if (input) input.value = resolveSymbol(catalog, input.value);
      }, true);
    });
    document.addEventListener('iaemloop:portfolio-data-refreshed', () => refresh().catch(() => {}));
    document.addEventListener('iaemloop:session-invalidated', () => { sessionGeneration += 1; catalog = []; list.replaceChildren(); });
  }

  if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', installBrowserController);

  return { buildCatalog, matchCatalog, resolveSymbol };
});
