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
    input.addEventListener('input', () => {
      const query = input.value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
      let visible = 0;
      cards.forEach((card) => {
        const haystack = card.textContent.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        const show = !query || haystack.includes(query);
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
    });
  }

  document.querySelectorAll('.v2-imported-content table').forEach((table) => {
    if (table.parentElement && !table.parentElement.classList.contains('v2-table-scroll')) {
      const wrapper = document.createElement('div');
      wrapper.className = 'v2-table-scroll';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });
})();
