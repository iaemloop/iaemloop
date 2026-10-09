const assert = require('node:assert/strict');
const importer = require('../js/privado/portfolio-import.js');

{
  const rows = importer.parseDelimitedText('Ticker;Quantidade;Custo médio;Moeda;Classe\nPETR4;10;31,50;BRL;ação\nAAPL;1.25;190.10;USD;stock');
  const normalized = importer.normalizeRows(rows);
  assert.equal(normalized.valid.length, 2);
  assert.deepEqual(normalized.valid[0], { symbol: 'PETR4', quantity: 10, average_cost: 31.5, currency: 'BRL', asset_type: 'equity' });
  assert.equal(normalized.valid[1].symbol, 'AAPL');
  assert.equal(normalized.valid[1].asset_type, 'equity');
}

{
  const rows = importer.parseDelimitedText('symbol,quantity,average_cost,currency\nMSFT,2,410.25,USD\nINVALID,0,10,USD');
  const normalized = importer.normalizeRows(rows);
  assert.equal(normalized.valid.length, 1);
  assert.equal(normalized.invalid.length, 1);
  assert.ok(normalized.invalid[0].reason.includes('quantidade'));
}

{
  const rows = importer.parsePdfText('Relatório de custódia\nPETR4 10 31,50 BRL\nAAPL 1.25 190.10 USD\nConta 123456 999 888');
  assert.equal(rows.length, 2);
  assert.equal(rows[0].ticker, 'PETR4');
  assert.equal(rows[1].ticker, 'AAPL');
}

{
  const mixed = importer.normalizeRows([
    { ticker: 'PETR4', quantidade: '1', custo_medio: '20', moeda: 'BRL' },
    { ticker: 'AAPL', quantidade: '1', custo_medio: '200', moeda: 'USD' }
  ]);
  assert.equal(mixed.valid.length, 2);
  assert.deepEqual([...new Set(mixed.valid.map((row) => row.currency))].sort(), ['BRL', 'USD']);
}

async function fileLike(name, content, type = '') {
  const blob = new Blob([content], { type });
  Object.defineProperty(blob, 'name', { value: name });
  return blob;
}

(async () => {
  const csvFile = await fileLike('custodia.csv', 'ticker;quantidade;custo_medio;moeda\nITUB4;3;25,50;BRL');
  const csvRows = await importer.rowsFromFile(csvFile);
  assert.equal(csvRows[0].ticker, 'ITUB4');

  const fakePdf = await fileLike('extrato.pdf', 'not-a-pdf');
  await assert.rejects(() => importer.rowsFromFile(fakePdf), /assinatura PDF válida/);

  const fakeXlsx = await fileLike('extrato.xlsx', 'not-an-xlsx');
  await assert.rejects(() => importer.rowsFromFile(fakeXlsx), /assinatura XLSX válida/);

  console.log('PORTFOLIO_IMPORT_TESTS_OK');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
