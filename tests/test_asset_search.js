const assert = require('node:assert/strict');
const search = require('../js/privado/asset-search.js');

const catalog = search.buildCatalog({
  approvedAssets: [
    { ticker: 'PETR4', nome: 'Petrobras PN', sleeve: 'besst-b3' },
    { ticker: 'AAPL', nome: 'Apple Inc.', sleeve: 'besst-usd' },
    { ticker: 'PETR4', nome: 'Petrobras', sleeve: 'magic-b3' }
  ],
  holdings: [
    { symbol: 'ITUB4', asset_type: 'equity', currency: 'BRL' },
    { symbol: 'AAPL', asset_type: 'equity', currency: 'USD' }
  ],
  transactions: [
    { symbol: 'MSFT', currency: 'USD' },
    { symbol: null, currency: 'BRL' }
  ]
});

assert.deepEqual(catalog.map((item) => item.symbol), ['AAPL', 'ITUB4', 'MSFT', 'PETR4']);
assert.equal(catalog.find((item) => item.symbol === 'PETR4').name, 'Petrobras PN');
assert.equal(catalog.find((item) => item.symbol === 'ITUB4').source, 'minha carteira');
assert.equal(catalog.find((item) => item.symbol === 'MSFT').source, 'meu histórico');

assert.deepEqual(search.matchCatalog(catalog, 'petro').map((item) => item.symbol), ['PETR4']);
assert.deepEqual(search.matchCatalog(catalog, 'aa').map((item) => item.symbol), ['AAPL']);
assert.deepEqual(search.matchCatalog(catalog, 'msft').map((item) => item.symbol), ['MSFT']);
assert.equal(search.matchCatalog(catalog, '', 2).length, 2);

const publicOnly = search.buildCatalog({ approvedAssets: [{ ticker: 'NVDA', nome: 'NVIDIA', sleeve: 'besst-usd' }] });
assert.deepEqual(publicOnly, [{ symbol: 'NVDA', name: 'NVIDIA', currency: 'USD', assetType: 'equity', source: 'catálogo aprovado' }]);

console.log('ASSET_SEARCH_TESTS_OK');
