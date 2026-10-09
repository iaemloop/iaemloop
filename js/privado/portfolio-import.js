(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IAEMLOOPPortfolioImport = Object.freeze(api);
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';

  const MAX_FILE_BYTES = 10 * 1024 * 1024;
  const HEADER_ALIASES = Object.freeze({
    symbol: ['ticker', 'symbol', 'simbolo', 'ativo', 'codigo', 'papel'],
    quantity: ['quantidade', 'quantity', 'qtd', 'qtde'],
    average_cost: ['custo_medio', 'customedio', 'average_cost', 'averageprice', 'preco_medio', 'precomedio', 'pm'],
    currency: ['moeda', 'currency'],
    asset_type: ['classe', 'tipo', 'asset_type', 'assettype']
  });

  function normalizeHeader(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  }

  function parseLocalizedNumber(value) {
    let text = String(value == null ? '' : value).trim().replace(/\s/g, '');
    if (!text) return null;
    if (text.includes(',') && text.includes('.')) {
      if (text.lastIndexOf(',') > text.lastIndexOf('.')) text = text.replace(/\./g, '').replace(',', '.');
      else text = text.replace(/,/g, '');
    } else if (text.includes(',')) text = text.replace(',', '.');
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function detectDelimiter(line) {
    const candidates = [';', '\t', ','];
    return candidates.sort((a, b) => line.split(b).length - line.split(a).length)[0];
  }

  function splitDelimitedLine(line, delimiter) {
    const cells = [];
    let current = '';
    let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      if (char === '"') {
        if (quoted && line[index + 1] === '"') { current += '"'; index += 1; }
        else quoted = !quoted;
      } else if (char === delimiter && !quoted) {
        cells.push(current.trim());
        current = '';
      } else current += char;
    }
    cells.push(current.trim());
    return cells;
  }

  function parseDelimitedText(text) {
    const lines = String(text || '').replace(/^\uFEFF/, '').split(/\r?\n/).filter((line) => line.trim());
    if (lines.length < 2) return [];
    const delimiter = detectDelimiter(lines[0]);
    const headers = splitDelimitedLine(lines[0], delimiter).map(normalizeHeader);
    return lines.slice(1).map((line) => {
      const values = splitDelimitedLine(line, delimiter);
      return headers.reduce((row, header, index) => { row[header] = values[index] == null ? '' : values[index]; return row; }, {});
    });
  }

  function pick(row, logicalName) {
    const normalized = {};
    Object.entries(row || {}).forEach(([key, value]) => { normalized[normalizeHeader(key)] = value; });
    const alias = HEADER_ALIASES[logicalName].find((name) => Object.prototype.hasOwnProperty.call(normalized, name));
    return alias ? normalized[alias] : '';
  }

  function normalizeAssetType(value) {
    const type = normalizeHeader(value);
    if (!type || ['acao', 'acoes', 'stock', 'stocks', 'equity'].includes(type)) return 'equity';
    if (['fundo', 'fund', 'etf', 'fii'].includes(type)) return 'fund';
    if (['renda_fixa', 'fixed_income'].includes(type)) return 'fixed_income';
    if (['cripto', 'crypto'].includes(type)) return 'crypto';
    if (['caixa', 'cash'].includes(type)) return 'cash';
    return 'other';
  }

  function normalizeRows(rows) {
    const valid = [];
    const invalid = [];
    (rows || []).forEach((row, index) => {
      const symbol = String(pick(row, 'symbol') || '').trim().toUpperCase();
      const quantity = parseLocalizedNumber(pick(row, 'quantity'));
      const averageCost = parseLocalizedNumber(pick(row, 'average_cost'));
      const currency = String(pick(row, 'currency') || '').trim().toUpperCase();
      const reasons = [];
      if (!/^[A-Z0-9.\-]{1,32}$/.test(symbol)) reasons.push('ticker inválido');
      if (!(quantity > 0)) reasons.push('quantidade deve ser maior que zero');
      if (!(averageCost >= 0)) reasons.push('custo médio inválido');
      if (!/^[A-Z]{3}$/.test(currency)) reasons.push('moeda deve usar três letras, como BRL ou USD');
      if (reasons.length) invalid.push({ row: index + 2, symbol: symbol || '—', reason: reasons.join('; ') });
      else valid.push({ symbol, quantity, average_cost: averageCost, currency, asset_type: normalizeAssetType(pick(row, 'asset_type')) });
    });
    return { valid, invalid };
  }

  function parsePdfText(text) {
    const rows = [];
    String(text || '').split(/\r?\n/).forEach((line) => {
      const match = line.trim().match(/^((?:[A-Z]{4}\d{1,2})|(?:[A-Z]{1,5}(?:\.[A-Z])?))\s+([\d.,]+)\s+([\d.,]+)(?:\s+(BRL|USD))?(?:\s+(.*))?$/);
      if (!match) return;
      rows.push({ ticker: match[1], quantidade: match[2], custo_medio: match[3], moeda: match[4] || '', classe: match[5] || 'equity' });
    });
    return rows;
  }

  async function rowsFromFile(file) {
    const extension = String(file.name || '').split('.').pop().toLowerCase();
    if (file.size > MAX_FILE_BYTES) throw new Error('O arquivo excede o limite de 10 MB.');
    if (extension === 'csv' || extension === 'txt') return parseDelimitedText(await file.text());
    if (extension === 'xlsx') {
      const signature = new Uint8Array(await file.slice(0, 4).arrayBuffer());
      if (signature[0] !== 0x50 || signature[1] !== 0x4B) throw new Error('A planilha não possui uma assinatura XLSX válida.');
      if (!root.ExcelJS) throw new Error('Leitor de planilhas indisponível. Recarregue a página.');
      const workbook = new root.ExcelJS.Workbook();
      await workbook.xlsx.load(await file.arrayBuffer());
      const sheet = workbook.worksheets[0];
      if (!sheet) return [];
      if (sheet.actualRowCount > 1001) throw new Error('A planilha excede o limite de 1.000 linhas de dados.');
      const headers = [];
      sheet.getRow(1).eachCell({ includeEmpty: true }, (cell, column) => { headers[column - 1] = normalizeHeader(cell.text); });
      const rows = [];
      sheet.eachRow({ includeEmpty: false }, (excelRow, rowNumber) => {
        if (rowNumber === 1) return;
        const row = {};
        headers.forEach((header, index) => { if (header) row[header] = excelRow.getCell(index + 1).text; });
        rows.push(row);
      });
      return rows;
    }
    if (extension === 'pdf') {
      const signature = new TextDecoder('ascii').decode(await file.slice(0, 5).arrayBuffer());
      if (signature !== '%PDF-') throw new Error('O arquivo não possui uma assinatura PDF válida.');
      const pdfjsLib = await import('https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.mjs');
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs';
      const document = await pdfjsLib.getDocument({ data: await file.arrayBuffer(), isEvalSupported: false }).promise;
      if (document.numPages > 50) throw new Error('O PDF excede o limite de 50 páginas.');
      const lines = [];
      for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
        const page = await document.getPage(pageNumber);
        const content = await page.getTextContent();
        const byY = new Map();
        content.items.forEach((item) => {
          const y = Math.round(item.transform[5]);
          const existing = byY.get(y) || [];
          existing.push({ x: item.transform[4], text: item.str });
          byY.set(y, existing);
        });
        [...byY.keys()].sort((a, b) => b - a).forEach((y) => lines.push(byY.get(y).sort((a, b) => a.x - b.x).map((item) => item.text).join(' ')));
      }
      return parsePdfText(lines.join('\n'));
    }
    throw new Error('Formato não suportado. Use CSV, XLSX, XLS ou PDF.');
  }

  function browserController() {
    if (!root.document || !root.IAEMLOOPPortfolioAPI) return;
    const byId = (id) => root.document.getElementById(id);
    const status = (message, kind = 'info') => { const el = byId('import-status'); if (el) { el.textContent = message; el.dataset.kind = kind; } };
    let preview = [];
    let invalid = [];

    function renderPreview() {
      const body = byId('import-preview-body');
      if (!body) return;
      body.replaceChildren();
      preview.forEach((row) => {
        const tr = root.document.createElement('tr');
        [row.symbol, row.quantity, row.average_cost, row.currency, row.asset_type].forEach((value) => { const td = root.document.createElement('td'); td.textContent = String(value); tr.appendChild(td); });
        body.appendChild(tr);
      });
      invalid.forEach((row) => {
        const tr = root.document.createElement('tr');
        const td = root.document.createElement('td');
        td.colSpan = 5;
        td.textContent = `Linha ${row.row} · ${row.symbol}: ${row.reason}`;
        td.className = 'import-invalid';
        tr.appendChild(td);
        body.appendChild(tr);
      });
      byId('import-confirm').disabled = preview.length === 0;
      byId('import-confirm').checked = false;
      byId('import-submit').disabled = true;
    }

    async function syncAccounts() {
      const portfolioId = byId('import-portfolio').value;
      const accounts = (await root.IAEMLOOPPortfolioAPI.listAccounts()).filter((item) => item.portfolio_id === portfolioId);
      const select = byId('import-account');
      select.replaceChildren();
      const placeholder = root.document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Selecione a conta';
      select.appendChild(placeholder);
      accounts.forEach((account) => {
        const option = root.document.createElement('option');
        option.value = account.id;
        option.dataset.currency = account.currency;
        option.textContent = `${account.name} · ${account.currency}`;
        select.appendChild(option);
      });
    }

    async function preparePreview() {
      await root.IAEMLOOPAuth.requireApprovedSession();
      const portfolioId = byId('import-portfolio').value;
      const accountId = byId('import-account').value;
      const file = byId('import-file').files[0];
      if (!portfolioId || !accountId || !file) throw new Error('Selecione carteira, conta e arquivo.');
      status('Lendo o arquivo localmente...', 'info');
      const accountCurrency = byId('import-account').selectedOptions[0]?.dataset.currency;
      const rawRows = await rowsFromFile(file);
      const normalized = normalizeRows(rawRows.map((row) => pick(row, 'currency') ? row : { ...row, moeda: accountCurrency }));
      const existing = await root.IAEMLOOPPortfolioAPI.listHoldings();
      const existingSymbols = new Set(existing.filter((item) => item.account_id === accountId).map((item) => String(item.symbol).toUpperCase()));
      preview = [];
      invalid = [...normalized.invalid];
      normalized.valid.forEach((row, index) => {
        if (row.currency !== accountCurrency) invalid.push({ row: index + 2, symbol: row.symbol, reason: `moeda ${row.currency} difere da conta ${accountCurrency}` });
        else if (existingSymbols.has(row.symbol)) invalid.push({ row: index + 2, symbol: row.symbol, reason: 'já existe nesta conta; edite a posição existente em vez de duplicar' });
        else if (preview.some((item) => item.symbol === row.symbol)) invalid.push({ row: index + 2, symbol: row.symbol, reason: 'ticker duplicado no arquivo' });
        else if (preview.length >= 200) invalid.push({ row: index + 2, symbol: row.symbol, reason: 'limite de 200 posições por importação' });
        else preview.push(row);
      });
      renderPreview();
      status(preview.length ? `${preview.length} posição(ões) pronta(s) para revisão. ${invalid.length} linha(s) rejeitada(s).` : `Nenhuma posição válida. ${invalid.length} linha(s) rejeitada(s).`, preview.length ? 'warn' : 'error');
    }

    async function importRows() {
      await root.IAEMLOOPAuth.requireApprovedSession();
      if (!byId('import-confirm').checked || !preview.length) throw new Error('Revise a prévia e marque a confirmação antes de importar.');
      const portfolioId = byId('import-portfolio').value;
      const accountId = byId('import-account').value;
      status('Salvando posições na sua área privada...', 'info');
      await root.IAEMLOOPPortfolioAPI.createHoldings(preview.map((row) => ({ ...row, portfolio_id: portfolioId, account_id: accountId, acquired_at: null })));
      await root.IAEMLOOPAuth.requireApprovedSession();
      status(`${preview.length} posição(ões) importada(s) com sucesso.`, 'ok');
      preview = [];
      invalid = [];
      byId('import-file').value = '';
      renderPreview();
      root.document.dispatchEvent(new Event('iaemloop:portfolio-data-refreshed'));
      byId('refresh-data')?.click();
    }

    byId('import-portfolio')?.addEventListener('change', () => syncAccounts().catch((error) => status(error.message, 'error')));
    byId('import-preview')?.addEventListener('click', () => preparePreview().catch((error) => status(error.message, 'error')));
    byId('import-confirm')?.addEventListener('change', (event) => { byId('import-submit').disabled = !(event.target.checked && preview.length); });
    byId('import-submit')?.addEventListener('click', () => importRows().catch((error) => status(error.message, 'error')));
    root.document.addEventListener('iaemloop:session-invalidated', () => { preview = []; invalid = []; renderPreview(); status('Sessão encerrada; a prévia foi removida da tela.', 'warn'); });
  }

  if (root.document) root.document.addEventListener('DOMContentLoaded', browserController);
  return { parseDelimitedText, normalizeRows, parsePdfText, parseLocalizedNumber, rowsFromFile };
});
