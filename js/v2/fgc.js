(function () {
  'use strict';

  function safe(value) {
    return String(value ?? '').replace(/[&<>"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));
  }

  function badge(text, background, color) {
    return `<span style="background:${background};color:${color};padding:2px 8px;border-radius:99px;font-size:.75rem;font-weight:700">${safe(text)}</span>`;
  }

  function setupFilters() {
    const indexadorFilter = document.getElementById('indexador-filter');
    const prazoFilter = document.getElementById('prazo-filter');
    if (!indexadorFilter || !prazoFilter) return;
    const apply = () => {
      const indexador = indexadorFilter.value.toLowerCase();
      const prazo = prazoFilter.value;
      document.querySelectorAll('#ranking-body tr').forEach((row) => {
        const rowIndexador = (row.dataset.indexador || '').toLowerCase();
        const indexadorOk = indexador === 'all' || (indexador === 'pós-fixado' ? rowIndexador !== 'pré-fixado' : rowIndexador === indexador);
        const prazoOk = prazo === 'all' || row.dataset.prazo === prazo;
        row.hidden = !(indexadorOk && prazoOk);
      });
    };
    indexadorFilter.addEventListener('change', apply);
    prazoFilter.addEventListener('change', apply);
  }

  async function load() {
    const tbody = document.getElementById('ranking-body');
    if (!tbody) return;
    try {
      const response = await fetch('/data/fgc_products.json');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const products = await response.json();
      tbody.replaceChildren();
      products.forEach((product) => {
        const row = document.createElement('tr');
        row.dataset.indexador = String(product.indexador || '').replace(/\s/g, '').toLowerCase();
        row.dataset.prazo = String(product.prazo_tipo || '').toLowerCase();
        const fgc = product.tem_fgc ? badge('FGC', '#16a34a', '#fff') : '';
        const rating = badge(product.rating || 'N/A', product.rating === 'N/A' ? '#d9e0ea' : '#fff1a8', '#1b2430');
        const indexador = badge(String(product.indexador || '').replace(/\s/g, ''), '#d8f7ff', '#19364d');
        row.innerHTML = `<td><strong>#${safe(product.rank)}</strong></td><td><strong>${safe(product.produto)} ${fgc}</strong><br><small>${safe(product.emissor)}</small></td><td>${rating}</td><td>${indexador}</td><td>${safe(product.tipo)}</td><td>${safe(product.rent_bruta)}</td><td>${safe(product.rent_liquida)}</td><td>${safe(product.minimo)}</td><td>${safe(product.prazo)}<br><small>${safe(product.prazo_tipo)}</small></td>`;
        tbody.appendChild(row);
      });
      setupFilters();
      try {
        const stamp = await fetch('/data/last_updated.txt').then((res) => res.text());
        const [year, month, day] = stamp.trim().split('-').map(Number);
        const target = document.getElementById('last-updated');
        if (target) target.textContent = `Última atualização: ${new Date(year, month - 1, day).toLocaleDateString('pt-BR')}`;
      } catch (_) {}
    } catch (error) {
      console.error('Erro ao carregar dados FGC V2:', error);
      tbody.innerHTML = '<tr><td colspan="9">Erro ao carregar dados. Tente novamente mais tarde.</td></tr>';
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load);
  else load();
})();
