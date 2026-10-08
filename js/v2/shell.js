(function () {
  'use strict';

  const path = window.location.pathname;
  const items = [
    { href: '/privado/v2/index.html', label: 'Visão geral', icon: '◉', match: /\/privado\/v2\/index\.html$/ },
    { href: '/privado/v2/graficos-custodia.html', label: 'Ativos', icon: '↗', match: /graficos-custodia\.html$/ },
    { href: '/privado/v2/minha-carteira.html', label: 'Carteira', icon: '＋', match: /minha-carteira\.html$/ },
    { href: '/v2/area-privada.html', label: 'Conta', icon: '◎', match: /area-privada\.html$/ }
  ];

  if (document.body.classList.contains('v2-page') && path.includes('/privado/v2/')) {
    const nav = document.createElement('nav');
    nav.className = 'v2-dock';
    nav.setAttribute('aria-label', 'Navegação da área privada V2');
    nav.innerHTML = items.map((item) => {
      const active = item.match.test(path);
      return `<a href="${item.href}"${active ? ' class="active" aria-current="page"' : ''}><span aria-hidden="true">${item.icon}</span><b>${item.label}</b></a>`;
    }).join('');
    document.body.appendChild(nav);
  }

  document.querySelectorAll('.panel, .card, .future-card, .metric, .asset-card, .orbit-card').forEach((element, index) => {
    element.style.setProperty('--reveal-delay', `${Math.min(index, 10) * 35}ms`);
    element.classList.add('v2-reveal');
  });

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll('.v2-reveal').forEach((element) => observer.observe(element));
  } else {
    document.querySelectorAll('.v2-reveal').forEach((element) => element.classList.add('is-visible'));
  }
})();
