(function () {
  'use strict';

  const PAGE_SIZE = 50;
  const byId = (id) => document.getElementById(id);
  let context = null;
  let page = 0;
  let refreshGeneration = 0;
  let state = { items: [], filteredCount: 0, counts: { pending: 0, approved: 0, rejected: 0, total: 0 } };

  function setStatus(message, kind = 'info') {
    const element = byId('admin-status');
    if (!element) return;
    element.textContent = message;
    element.dataset.kind = kind;
  }

  function setCount(name, value) {
    const element = byId(`admin-count-${name}`);
    if (element) element.textContent = String(Number(value) || 0);
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('pt-BR');
  }

  function badge(label, type) {
    const element = document.createElement('span');
    element.className = `admin-badge admin-badge-${type}`;
    element.textContent = label;
    return element;
  }

  function cell(value) {
    const element = document.createElement('td');
    element.textContent = value == null || value === '' ? '—' : String(value);
    return element;
  }

  function actionButton(label, action, item, danger = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = danger ? 'table-action danger' : 'table-action';
    button.dataset.action = action;
    button.dataset.userId = item.user_id;
    button.dataset.expectedStatus = item.status;
    button.textContent = label;
    return button;
  }

  function renderRows(items) {
    const body = byId('admin-access-body');
    body.replaceChildren();
    if (!items.length) {
      const row = document.createElement('tr');
      const empty = cell('Nenhuma solicitação encontrada.');
      empty.className = 'empty-row';
      empty.colSpan = 6;
      row.appendChild(empty);
      body.appendChild(row);
      return;
    }

    items.forEach((item) => {
      const row = document.createElement('tr');
      row.dataset.userId = item.user_id;

      const identity = document.createElement('td');
      const name = document.createElement('strong');
      name.textContent = item.full_name || 'Nome não informado';
      const email = document.createElement('small');
      email.textContent = item.email || 'E-mail indisponível';
      identity.append(name, email);

      const statusCell = document.createElement('td');
      const statusLabels = { pending: 'Pendente', approved: 'Aprovado', rejected: 'Rejeitado' };
      statusCell.appendChild(badge(statusLabels[item.status] || item.status, item.status));

      const roleCell = document.createElement('td');
      roleCell.appendChild(badge(item.role === 'admin' ? 'Administrador' : 'Usuário', item.role));

      const actions = document.createElement('td');
      actions.className = 'table-actions';
      if (item.role !== 'admin') {
        if (item.status === 'pending') {
          actions.append(actionButton('Aprovar', 'approve', item), actionButton('Rejeitar', 'reject', item, true));
        } else if (item.status === 'approved') {
          actions.appendChild(actionButton('Revogar', 'revoke', item, true));
        } else if (item.status === 'rejected') {
          actions.appendChild(actionButton('Reabrir', 'reopen', item));
        }
      }
      if (!actions.childElementCount) actions.textContent = 'Protegido';

      row.append(identity, statusCell, roleCell, cell(formatDate(item.created_at)), cell(formatDate(item.last_sign_in_at)), actions);
      body.appendChild(row);
    });
  }

  function renderCounts(counts) {
    setCount('pending', counts.pending);
    setCount('approved', counts.approved);
    setCount('rejected', counts.rejected);
    setCount('total', counts.total);
  }

  function renderPagination() {
    const first = state.filteredCount === 0 ? 0 : page * PAGE_SIZE + 1;
    const last = Math.min((page + 1) * PAGE_SIZE, state.filteredCount);
    byId('admin-page-range').textContent = state.filteredCount === 0
      ? 'Nenhum resultado filtrado.'
      : `Exibindo ${first}–${last} de ${state.filteredCount} resultado(s) filtrado(s).`;
    byId('admin-page-previous').disabled = page === 0;
    byId('admin-page-next').disabled = last >= state.filteredCount;
  }

  function renderState() {
    renderCounts(state.counts);
    renderRows(state.items);
    renderPagination();
  }

  function normalizePayload(data) {
    const payload = data && typeof data === 'object' ? data : {};
    const counts = payload.counts && typeof payload.counts === 'object' ? payload.counts : {};
    return {
      items: Array.isArray(payload.items) ? payload.items : [],
      filteredCount: Math.max(0, Number(payload.filtered_count) || 0),
      counts: {
        pending: Math.max(0, Number(counts.pending) || 0),
        approved: Math.max(0, Number(counts.approved) || 0),
        rejected: Math.max(0, Number(counts.rejected) || 0),
        total: Math.max(0, Number(counts.total) || 0)
      }
    };
  }

  async function listRequests(status, search, requestedPage) {
    const { data, error } = await context.client.rpc('admin_list_access_requests', {
      p_status: status,
      p_search: search,
      p_limit: PAGE_SIZE,
      p_offset: requestedPage * PAGE_SIZE
    });
    if (error) throw error;
    return normalizePayload(data);
  }

  async function refresh(options = {}) {
    if (!context) return false;
    const generation = ++refreshGeneration;
    const requestedPage = page;
    const refreshButton = byId('admin-refresh');
    refreshButton.disabled = true;
    if (!options.quiet) setStatus('Atualizando solicitações...', 'info');

    try {
      const status = byId('admin-status-filter').value;
      const search = byId('admin-search').value.trim();
      const nextState = await listRequests(status, search, requestedPage);
      if (generation !== refreshGeneration || !context) return false;

      if (requestedPage > 0 && nextState.filteredCount > 0 && requestedPage * PAGE_SIZE >= nextState.filteredCount) {
        page = Math.max(0, Math.ceil(nextState.filteredCount / PAGE_SIZE) - 1);
        return refresh(options);
      }

      state = nextState;
      renderState();
      if (!options.quiet) {
        const first = state.filteredCount === 0 ? 0 : page * PAGE_SIZE + 1;
        const last = Math.min((page + 1) * PAGE_SIZE, state.filteredCount);
        setStatus(
          state.filteredCount === 0
            ? 'Nenhuma solicitação corresponde aos filtros.'
            : `Solicitações atualizadas. Exibindo ${first}–${last} de ${state.filteredCount}.`,
          'ok'
        );
      }
      return true;
    } finally {
      if (generation === refreshGeneration) refreshButton.disabled = false;
    }
  }

  function mutationFor(action) {
    if (action === 'approve') return { status: 'approved', reason: 'Aprovado pelo painel administrativo' };
    if (action === 'reject') return { status: 'rejected', reason: 'Rejeitado pelo painel administrativo' };
    if (action === 'revoke') return { status: 'rejected', reason: 'Acesso revogado pelo painel administrativo' };
    if (action === 'reopen') return { status: 'pending', reason: 'Solicitação reaberta pelo painel administrativo' };
    return null;
  }

  function reconcileMutation(item, previousStatus) {
    if (!item || !item.user_id) return;
    const index = state.items.findIndex((candidate) => candidate.user_id === item.user_id);
    const status = byId('admin-status-filter').value;
    const stillVisible = status === 'all' || status === item.status;
    if (previousStatus !== item.status) {
      state.counts[previousStatus] = Math.max(0, Number(state.counts[previousStatus]) - 1);
      state.counts[item.status] = Math.max(0, Number(state.counts[item.status]) + 1);
      if (status === previousStatus) state.filteredCount = Math.max(0, state.filteredCount - 1);
    }
    if (index >= 0 && stillVisible) state.items[index] = item;
    if (index >= 0 && !stillVisible) state.items.splice(index, 1);
    renderState();
  }

  async function decide(button) {
    const mutation = mutationFor(button.dataset.action);
    if (!mutation) return;
    if (['reject', 'revoke'].includes(button.dataset.action)) {
      const verb = button.dataset.action === 'revoke' ? 'revogar este acesso' : 'rejeitar esta solicitação';
      if (!window.confirm(`Confirma ${verb}?`)) return;
    }

    const row = button.closest('tr');
    row.querySelectorAll('button').forEach((element) => { element.disabled = true; });
    setStatus('Registrando decisão...', 'info');

    let updatedItem;
    try {
      const { data, error } = await context.client.rpc('admin_set_access_status', {
        p_target_user_id: button.dataset.userId,
        p_expected_status: button.dataset.expectedStatus,
        p_new_status: mutation.status,
        p_reason: mutation.reason
      });
      if (error) throw error;
      updatedItem = Array.isArray(data) ? data[0] : data;
      reconcileMutation(updatedItem, button.dataset.expectedStatus);
      setStatus('Decisão registrada e auditada. Atualizando a lista...', 'ok');
    } catch (error) {
      row.querySelectorAll('button').forEach((element) => { element.disabled = false; });
      setStatus(`Não foi possível registrar a decisão: ${error.message}`, 'error');
      return;
    }

    try {
      await refresh({ quiet: true });
      setStatus('Decisão registrada e auditada. Lista reconciliada.', 'ok');
    } catch (refreshError) {
      row.querySelectorAll('button').forEach((element) => { element.disabled = false; });
      setStatus(`Decisão registrada e auditada, mas a atualização da lista falhou: ${refreshError.message}. Use Atualizar para tentar novamente.`, 'warn');
    }
  }

  function resetPageAndRefresh() {
    page = 0;
    refresh().catch((error) => setStatus(`Não foi possível atualizar a lista: ${error.message}`, 'error'));
  }

  function denyAdmin() {
    byId('admin-app').hidden = true;
    byId('admin-denied').hidden = false;
    window.setTimeout(() => window.location.replace('index.html'), 2500);
  }

  async function start() {
    try {
      context = await window.IAEMLOOPAuth.requireApprovedSession();
      const { data: isAdmin, error } = await context.client.rpc('admin_is_current_user');
      if (error) throw error;
      if (isAdmin !== true) return denyAdmin();

      byId('admin-app').hidden = false;
      byId('admin-denied').hidden = true;
      byId('admin-filters').addEventListener('submit', (event) => {
        event.preventDefault();
        resetPageAndRefresh();
      });
      byId('admin-status-filter').addEventListener('change', resetPageAndRefresh);
      byId('admin-refresh').addEventListener('click', () => {
        refresh().catch((error) => setStatus(`Não foi possível atualizar a lista: ${error.message}`, 'error'));
      });
      byId('admin-page-previous').addEventListener('click', () => {
        if (page === 0) return;
        page -= 1;
        refresh().catch((error) => setStatus(`Não foi possível abrir a página anterior: ${error.message}`, 'error'));
      });
      byId('admin-page-next').addEventListener('click', () => {
        if ((page + 1) * PAGE_SIZE >= state.filteredCount) return;
        page += 1;
        refresh().catch((error) => setStatus(`Não foi possível abrir a próxima página: ${error.message}`, 'error'));
      });
      byId('admin-logout').addEventListener('click', () => window.IAEMLOOPAuth.logout());
      byId('admin-access-body').addEventListener('click', (event) => {
        const button = event.target.closest('button[data-action]');
        if (button) decide(button);
      });
      document.addEventListener('iaemloop:session-invalidated', () => {
        context = null;
        refreshGeneration += 1;
        byId('admin-app').hidden = true;
      });
      try {
        await refresh();
      } catch (refreshError) {
        setStatus(`Acesso administrativo confirmado, mas não foi possível carregar a lista: ${refreshError.message}. Use Atualizar para tentar novamente.`, 'warn');
      }
    } catch (error) {
      context = null;
      byId('admin-app').hidden = true;
      if (document.documentElement.dataset.auth === 'approved') {
        setStatus(`Não foi possível validar o acesso administrativo: ${error.message}`, 'error');
        denyAdmin();
      }
    }
  }

  document.addEventListener('DOMContentLoaded', start);
})();
