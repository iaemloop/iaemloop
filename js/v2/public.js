(function () {
  'use strict';

  const toggle = document.querySelector('.v2-menu-toggle');
  const menu = document.querySelector('.v2-main-menu');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    menu.addEventListener('click', (event) => {
      if (event.target.closest('a')) {
        menu.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  const currentPath = window.location.pathname.replace(/\/$/, '/index.html');
  document.querySelectorAll('[data-v2-nav]').forEach((link) => {
    const href = new URL(link.href, window.location.origin).pathname;
    const active = href === '/v2/index.html'
      ? currentPath === href
      : currentPath === href || currentPath.startsWith(href.replace('/index.html', '/'));
    if (active) link.setAttribute('aria-current', 'page');
  });

  const input = document.querySelector('.v2-search-input');
  const list = document.querySelector('[data-v2-search-list]');
  const empty = document.querySelector('.v2-empty-state');
  if (input && list) {
    const cards = [...list.children];
    const normalizeSearchText = (value) => value
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
    const filterCards = () => {
      const terms = normalizeSearchText(input.value).trim().split(/\s+/).filter(Boolean);
      let visible = 0;
      cards.forEach((card) => {
        const haystack = normalizeSearchText(card.textContent);
        const show = terms.every((term) => haystack.includes(term));
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
    };
    input.addEventListener('input', filterCards);
    input.addEventListener('search', filterCards);
    input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      filterCards();
    });
    filterCards();
  }

  function wrapTable(table) {
    if (table.parentElement && !table.parentElement.classList.contains('v2-table-scroll')) {
      const wrapper = document.createElement('div');
      wrapper.className = 'v2-table-scroll';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  }

  function rankingColumnAlignment(header) {
    const normalized = header.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
    if (normalized === '#' || /\b(pos(?:icao)?|rank|ticker|codigo|score)\b/.test(normalized)) return 'center';
    if (/\b(empresa|companhia|nome|setor|segmento|industria|produto|emissor|instituicao|rating|indexador|tipo|categoria|observac(?:ao|oes)|ativo)\b/.test(normalized)) return 'left';
    return 'right';
  }

  function annotateRankingTable(table) {
    const headers = [...table.querySelectorAll('thead tr:first-child th')];
    if (!headers.length) return;
    table.classList.add('v2-ranking-table');
    const classes = headers.map((header) => {
      const alignment = `v2-align-${rankingColumnAlignment(header.textContent)}`;
      header.classList.remove('v2-align-center', 'v2-align-left', 'v2-align-right');
      header.classList.add(alignment);
      return alignment;
    });
    table.querySelectorAll('tbody tr').forEach((row) => {
      const cells = [...row.children].filter((cell) => cell.matches('td,th'));
      if (cells.length !== classes.length) return;
      cells.forEach((cell, index) => {
        cell.classList.remove('v2-align-center', 'v2-align-left', 'v2-align-right');
        cell.classList.add(classes[index]);
      });
    });
  }

  function prepareImportedTables(root = document) {
    root.querySelectorAll('.v2-imported-content table').forEach(wrapTable);
    if (document.body.matches('.v2-ranking-page, .v2-tabular-page')) {
      root.querySelectorAll('.v2-imported-content table').forEach(annotateRankingTable);
    }
  }

  prepareImportedTables();
  if (document.body.matches('.v2-ranking-page, .v2-tabular-page')) {
    const rankingRoot = document.querySelector('.v2-imported-content');
    if (rankingRoot) {
      new MutationObserver(() => prepareImportedTables(rankingRoot)).observe(rankingRoot, {
        childList: true,
        subtree: true,
      });
    }
  }
})();
