(function () {
  'use strict';

  const api = window.IAEMLOOPPortfolioAPI;
  const render = window.IAEMLOOPRender;
  let state = { portfolios: [], accounts: [], holdings: [], transactions: [] };

  const byId = (id) => document.getElementById(id);
  const value = (form, name) => form.elements[name]?.value?.trim() || '';
  const numeric = (form, name) => Number(form.elements[name]?.value || 0);

  function setAppStatus(message, kind = 'info') {
    const el = byId('app-status');
    if (!el) return;
    el.textContent = message;
    el.dataset.kind = kind;
  }

  function portfolioName(id) {
    return state.portfolios.find((item) => item.id === id)?.name || 'Carteira removida';
  }

  function accountName(id) {
    return state.accounts.find((item) => item.id === id)?.name || 'Conta removida';
  }

  function replaceOptions(select, items, label, placeholder) {
    if (!select) return;
    const current = select.value;
    select.replaceChildren();
    const first = document.createElement('option');
    first.value = '';
    first.textContent = placeholder;
    select.appendChild(first);
    items.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = label(item);
      select.appendChild(option);
    });
    if (items.some((item) => item.id === current)) select.value = current;
  }

  function syncSelects() {
    document.querySelectorAll('[data-portfolio-select]').forEach((select) => {
      replaceOptions(select, state.portfolios, (item) => item.name, 'Selecione a carteira');
    });
    document.querySelectorAll('[data-account-select]').forEach((select) => {
      const portfolioId = select.dataset.portfolioField ? byId(select.dataset.portfolioField)?.value : '';
      const accounts = portfolioId ? state.accounts.filter((item) => item.portfolio_id === portfolioId) : state.accounts;
      replaceOptions(select, accounts, (item) => `${item.name} · ${item.institution || 'Instituição não informada'}`, 'Selecione a conta');
    });
  }

  function renderDashboard() {
    byId('metric-portfolios').textContent = String(state.portfolios.length);
    byId('metric-accounts').textContent = String(state.accounts.length);
    byId('metric-holdings').textContent = String(state.holdings.length);
    byId('metric-transactions').textContent = String(state.transactions.length);
    const totals = state.holdings.reduce((acc, item) => {
      const currency = item.currency || 'BRL';
      acc[currency] = (acc[currency] || 0) + Number(item.quantity) * Number(item.average_cost);
      return acc;
    }, {});
    const totalEl = byId('metric-cost');
    totalEl.replaceChildren();
    const currencies = Object.entries(totals);
    if (!currencies.length) totalEl.textContent = 'Sem posições';
    currencies.forEach(([currency, amount], index) => {
      if (index) totalEl.appendChild(document.createElement('br'));
      totalEl.appendChild(render.text(render.money(amount, currency)));
    });
  }

  function renderPortfolios() {
    const body = byId('portfolios-body');
    body.replaceChildren();
    if (!state.portfolios.length) return body.appendChild(render.emptyRow(4, 'Nenhuma carteira cadastrada.'));
    state.portfolios.forEach((item) => {
      const tr = document.createElement('tr');
      tr.append(render.cell(item.name), render.cell(item.base_currency), render.cell(item.description || '—'));
      const actions = document.createElement('td');
      actions.appendChild(render.button('Excluir', 'delete-portfolio', item.id, true));
      tr.appendChild(actions);
      body.appendChild(tr);
    });
  }

  function renderAccounts() {
    const body = byId('accounts-body');
    body.replaceChildren();
    if (!state.accounts.length) return body.appendChild(render.emptyRow(6, 'Nenhuma conta cadastrada.'));
    state.accounts.forEach((item) => {
      const tr = document.createElement('tr');
      tr.append(render.cell(item.name), render.cell(portfolioName(item.portfolio_id)), render.cell(item.institution || '—'), render.cell(item.account_type), render.cell(render.money(item.cash_balance, item.currency)));
      const actions = document.createElement('td');
      actions.appendChild(render.button('Excluir', 'delete-account', item.id, true));
      tr.appendChild(actions);
      body.appendChild(tr);
    });
  }

  function renderHoldings() {
    const body = byId('holdings-body');
    body.replaceChildren();
    if (!state.holdings.length) return body.appendChild(render.emptyRow(8, 'Nenhuma posição cadastrada.'));
    state.holdings.forEach((item) => {
      const tr = document.createElement('tr');
      const cost = Number(item.quantity) * Number(item.average_cost);
      tr.append(render.cell(item.symbol), render.cell(item.asset_type), render.cell(portfolioName(item.portfolio_id)), render.cell(accountName(item.account_id)), render.cell(render.number(item.quantity)), render.cell(render.money(item.average_cost, item.currency)), render.cell(render.money(cost, item.currency)));
      const actions = document.createElement('td');
      actions.appendChild(render.button('Excluir', 'delete-holding', item.id, true));
      tr.appendChild(actions);
      body.appendChild(tr);
    });
  }

  function renderTransactions() {
    const body = byId('transactions-body');
    body.replaceChildren();
    if (!state.transactions.length) return body.appendChild(render.emptyRow(8, 'Nenhuma movimentação cadastrada.'));
    state.transactions.forEach((item) => {
      const tr = document.createElement('tr');
      const date = item.occurred_at ? new Date(item.occurred_at).toLocaleDateString('pt-BR') : '—';
      tr.append(render.cell(date), render.cell(item.transaction_type), render.cell(item.symbol || '—'), render.cell(portfolioName(item.portfolio_id)), render.cell(accountName(item.account_id)), render.cell(item.quantity ? render.number(item.quantity) : '—'), render.cell(render.money(item.amount, item.currency)));
      const actions = document.createElement('td');
      actions.appendChild(render.button('Excluir', 'delete-transaction', item.id, true));
      tr.appendChild(actions);
      body.appendChild(tr);
    });
  }

  function renderAll() {
    renderDashboard();
    renderPortfolios();
    renderAccounts();
    renderHoldings();
    renderTransactions();
    syncSelects();
  }

  function clearPrivateState() {
    state = { portfolios: [], accounts: [], holdings: [], transactions: [] };
    const app = byId('private-app');
    if (!app) return;
    app.querySelectorAll('input, select, button').forEach((element) => { element.disabled = true; });
    app.querySelectorAll('tbody').forEach((body) => body.replaceChildren());
    app.querySelectorAll('[id^="metric-"]').forEach((metric) => { metric.textContent = '—'; });
    byId('current-user').textContent = 'sessão encerrada';
    setAppStatus('Sessão encerrada. Os dados privados foram removidos desta tela.', 'warn');
  }

  async function currentContext() {
    return window.IAEMLOOPAuth.requireApprovedSession();
  }

  async function refresh() {
    await currentContext();
    setAppStatus('Atualizando seus dados...', 'info');
    const [portfolios, accounts, holdings, transactions] = await Promise.all([
      api.listPortfolios(), api.listAccounts(), api.listHoldings(), api.listTransactions()
    ]);
    state = { portfolios, accounts, holdings, transactions };
    renderAll();
    setAppStatus('Dados privados atualizados.', 'ok');
  }

  function syncTransactionRequirements() {
    const form = document.querySelector('[data-form="transaction"]');
    if (!form) return;
    const isTrade = ['buy', 'sell'].includes(value(form, 'transaction_type'));
    ['symbol', 'quantity', 'unit_price'].forEach((name) => {
      const input = form.elements[name];
      input.required = isTrade;
      if (name !== 'symbol') input.min = isTrade ? '0.0000000001' : '0';
      input.setAttribute('aria-required', String(isTrade));
      if (!isTrade) {
        input.value = '';
        input.setCustomValidity('');
      }
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const kind = form.dataset.form;
    try {
      await currentContext();
      setAppStatus('Salvando...', 'info');
      if (kind === 'portfolio') {
        await api.createPortfolio({ name: value(form, 'name'), base_currency: value(form, 'base_currency'), description: value(form, 'description') || null });
      } else if (kind === 'account') {
        await api.createAccount({ portfolio_id: value(form, 'portfolio_id'), name: value(form, 'name'), institution: value(form, 'institution') || null, account_type: value(form, 'account_type'), currency: value(form, 'currency'), cash_balance: numeric(form, 'cash_balance') });
      } else if (kind === 'holding') {
        await api.createHolding({ portfolio_id: value(form, 'portfolio_id'), account_id: value(form, 'account_id'), symbol: value(form, 'symbol').toUpperCase(), asset_type: value(form, 'asset_type'), quantity: numeric(form, 'quantity'), average_cost: numeric(form, 'average_cost'), currency: value(form, 'currency'), acquired_at: value(form, 'acquired_at') || null });
      } else if (kind === 'transaction') {
        const type = value(form, 'transaction_type');
        const isTrade = type === 'buy' || type === 'sell';
        const symbol = value(form, 'symbol').toUpperCase();
        const quantity = numeric(form, 'quantity');
        const unitPrice = numeric(form, 'unit_price');
        if (isTrade && !symbol) throw new Error('Compras e vendas exigem um ticker.');
        if (isTrade && (!(quantity > 0) || !(unitPrice > 0))) throw new Error('Compras e vendas exigem quantidade e preço unitário maiores que zero.');
        await api.createTransaction({ portfolio_id: value(form, 'portfolio_id'), account_id: value(form, 'account_id'), transaction_type: type, symbol: symbol || null, quantity: isTrade ? quantity : null, unit_price: isTrade ? unitPrice : null, amount: numeric(form, 'amount'), fees: numeric(form, 'fees'), currency: value(form, 'currency'), occurred_at: new Date(value(form, 'occurred_at')).toISOString(), notes: value(form, 'notes') || null });
      }
      form.reset();
      syncTransactionRequirements();
      await refresh();
    } catch (error) {
      setAppStatus(`Não foi possível salvar: ${error.message}`, 'error');
    }
  }

  async function handleDelete(event) {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const map = {
      'delete-portfolio': ['deletePortfolio', 'a carteira e todos os dados vinculados'],
      'delete-account': ['deleteAccount', 'a conta e seus dados vinculados'],
      'delete-holding': ['deleteHolding', 'a posição'],
      'delete-transaction': ['deleteTransaction', 'a movimentação']
    };
    const selected = map[button.dataset.action];
    if (!selected || !window.confirm(`Excluir ${selected[1]}? Esta ação não pode ser desfeita.`)) return;
    try {
      await currentContext();
      await api[selected[0]](button.dataset.id);
      await refresh();
    } catch (error) {
      setAppStatus(`Não foi possível excluir: ${error.message}`, 'error');
    }
  }

  function installEvents() {
    document.querySelectorAll('form[data-form]').forEach((form) => form.addEventListener('submit', handleSubmit));
    byId('private-app').addEventListener('click', handleDelete);
    document.querySelectorAll('[data-portfolio-select]').forEach((select) => select.addEventListener('change', syncSelects));
    byId('refresh-data').addEventListener('click', () => refresh().catch((error) => setAppStatus(error.message, 'error')));
    document.querySelector('[data-form="transaction"] [name="transaction_type"]').addEventListener('change', syncTransactionRequirements);
    syncTransactionRequirements();
  }

  async function start() {
    try {
      const context = await currentContext();
      byId('current-user').textContent = context.profile.full_name || context.user.email || 'Usuário';
      installEvents();
      await refresh();
    } catch (error) {
      clearPrivateState();
      setAppStatus(`Falha ao carregar o painel: ${error.message}`, 'error');
    }
  }

  document.addEventListener('iaemloop:session-invalidated', clearPrivateState);
  document.addEventListener('DOMContentLoaded', start);
})();
