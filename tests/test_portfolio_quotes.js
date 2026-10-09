const assert = require('node:assert/strict');
const quotes = require('../js/privado/portfolio-quotes.js');

const sample = `Title:\nMarkdown Content:\n{"spark":{"result":[{"symbol":"BRK-B","response":[{"meta":{"currency":"USD","regularMarketPrice":501.25,"regularMarketTime":1700000000}}]},{"symbol":"GDDY","response":[{"meta":{"currency":"USD","regularMarketPrice":105.11,"regularMarketTime":1700000100}}]}]}}`;
const parsed = quotes.parseYahooSpark(sample);
assert.equal(parsed['BRK.B'].price, 501.25);
assert.equal(parsed.GDDY.currency, 'USD');
assert.equal(parsed.GDDY.source, 'Yahoo Finance via Jina');
assert.equal(quotes.extractJson('sem json'), null);
console.log('PORTFOLIO_QUOTES_TESTS_OK');
