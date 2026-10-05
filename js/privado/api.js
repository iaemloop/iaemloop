(function () {
  'use strict';

  async function freshContext() {
    if (!window.IAEMLOOPAuth?.requireApprovedSession) throw new Error('Validador de sessão indisponível.');
    return window.IAEMLOOPAuth.requireApprovedSession();
  }

  async function query(table, select, order = 'created_at') {
    const context = await freshContext();
    const { data, error } = await context.client
      .from(table)
      .select(select)
      .eq('user_id', context.user.id)
      .order(order, { ascending: false });
    if (error) throw error;
    return data || [];
  }

  async function insert(table, payload, select = '*') {
    const context = await freshContext();
    const { data, error } = await context.client
      .from(table)
      .insert({ ...payload, user_id: context.user.id })
      .select(select)
      .single();
    if (error) throw error;
    return data;
  }

  async function remove(table, id) {
    const context = await freshContext();
    const { error } = await context.client
      .from(table)
      .delete()
      .eq('id', id)
      .eq('user_id', context.user.id);
    if (error) throw error;
  }

  const api = {
    listPortfolios: () => query('portfolios', 'id,user_id,name,base_currency,description,created_at,updated_at'),
    createPortfolio: (values) => insert('portfolios', values),
    deletePortfolio: (id) => remove('portfolios', id),

    listAccounts: () => query('portfolio_accounts', 'id,user_id,portfolio_id,name,institution,account_type,currency,cash_balance,created_at,updated_at'),
    createAccount: (values) => insert('portfolio_accounts', values),
    deleteAccount: (id) => remove('portfolio_accounts', id),

    listHoldings: () => query('holdings', 'id,user_id,portfolio_id,account_id,symbol,asset_type,quantity,average_cost,currency,acquired_at,created_at,updated_at'),
    createHolding: (values) => insert('holdings', values),
    deleteHolding: (id) => remove('holdings', id),

    listTransactions: () => query('portfolio_transactions', 'id,user_id,portfolio_id,account_id,transaction_type,symbol,quantity,unit_price,amount,fees,currency,occurred_at,notes,created_at,updated_at', 'occurred_at'),
    createTransaction: (values) => insert('portfolio_transactions', values),
    deleteTransaction: (id) => remove('portfolio_transactions', id)
  };

  window.IAEMLOOPPortfolioAPI = Object.freeze(api);
})();
