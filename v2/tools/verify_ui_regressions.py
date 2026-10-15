#!/usr/bin/env python3
"""Regression gates for the isolated public V2 presentation."""
from pathlib import Path
import importlib.util
import re
import subprocess
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('v2build', ROOT / 'v2/tools/build.py')
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
expected_nav = [
    ('Início', '/v2/index.html'),
    ('Métodos', '/v2/metodos/index.html'),
    ('Indicadores', '/v2/indicadores/index.html'),
    ('Rankings', '/v2/rankings/index.html'),
    ('Radar', '/v2/radar/index.html'),
    ('Blog', '/v2/blog/index.html'),
]
assert module.NAV == expected_nav
handlers = scripts = 0
history_routes = []
for route in module.ROUTES:
    path = ROOT / 'v2' / route['target']
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    assert len(soup.find_all('h1')) == 1, path
    assert all('event.target' not in str(script) for script in soup.select('script')), path
    if soup.select('button.tab[onclick]'):
        assert sum('function switchTab' in x.get_text() for x in soup.select('script')) == 1, path
    assert not soup.select('.v2-page-intro,.v2-source-ribbon'), path
    assert not soup.select('.v2-imported-content header'), path
    if route['target'].startswith('rankings/historico/'):
        history_routes.append(route['target'])
        tabs = soup.select_one('.v2-history-tabs[role="tablist"]')
        assert tabs, path
        static_buttons = tabs.select('button.tab[onclick]')
        if static_buttons:
            panels = soup.select('.tab-content')
            assert len(static_buttons) == len(panels) >= 2, path
            assert len(soup.select('.tab-content.active')) == 1, path
            assert len(tabs.select('button.tab.active')) == 1, path
        else:
            # Dynamic B3 history keeps its numeric switchTab(idx) handler and data.
            source_script = '\n'.join(x.get_text() for x in soup.select('script:not([src])'))
            assert 'tab.onclick = () => switchTab(idx)' in source_script, path
            assert 'function switchTab(idx)' in source_script, path
    for button in soup.select('button.tab[onclick]'):
        handler = button['onclick']
        assert '\\' not in handler and ', this)' in handler, (path, handler)
        match = re.search(r'switchTab\("([^\"]+)"', handler)
        assert match and soup.find(id=match.group(1)), (path, handler)
        assert button.get('type') == 'button' and button.get('role') == 'tab', (path, button)
        assert button.get('aria-controls') == match.group(1), (path, button)
        subprocess.run(['node', '--check', '-'], input=handler, text=True, check=True, capture_output=True)
        handlers += 1
    for script in soup.select('script:not([src])'):
        if script.get('type') in ('application/json', 'application/ld+json'):
            continue
        subprocess.run(['node', '--check', '-'], input=script.get_text(), text=True, check=True, capture_output=True)
        scripts += 1
assert sorted(history_routes) == sorted([
    'rankings/historico/besst-buffett-b3.html',
    'rankings/historico/besst-buffett-eua.html',
    'rankings/historico/magic-formula-b3.html',
    'rankings/historico/magic-formula-eua.html',
    'rankings/historico/watchlist-buffett-eua.html',
])
legacy = ROOT / 'v2/rankings/watchlist-buffett-eua.html'
soup = BeautifulSoup(legacy.read_text(), 'html.parser')
assert soup.find('meta', attrs={'name': 'robots'})['content'] == 'noindex,nofollow,noarchive'
assert '/v2/rankings/watchlist-buffett-eua.html' not in (ROOT / 'v2/sitemap.xml').read_text()
assert not BeautifulSoup((ROOT / 'v2/rankings/index.html').read_text(), 'html.parser').select('a[href="/v2/radar/watchlist-buffett-eua.html"]')
assert (ROOT / 'v2/radar/watchlist-buffett-eua.html').exists()
for path in (ROOT / 'v2').rglob('*.html'):
    page = BeautifulSoup(path.read_text(), 'html.parser')
    nav = page.select('.v2-main-menu a[data-v2-nav]')
    if nav:
        actual = [(link.get_text(' ', strip=True), link.get('href')) for link in nav]
        assert actual == expected_nav, (path, actual)
print(f'V2_UI_REGRESSIONS_OK source_routes={len(module.ROUTES)} static_handlers={handlers} scripts={scripts}')

indicator = BeautifulSoup((ROOT / 'v2/indicadores/buffett.html').read_text(), 'html.parser')
assert 'valor de mercado das empresas listadas' in indicator.get_text(' ')
assert indicator.select_one('a[href="#graficos"]') and indicator.select_one('a[href="#metodologia"]')
fixture = BeautifulSoup('<article><p>O ranking público apresenta ROIC de 77%. Nas carteiras reais brasileiras, são 2 ações com preço médio de R$ 51,65. A análise pública exige margem de segurança.</p><div><b>Variação vs. PM</b><span>+15%</span></div></article>', 'html.parser')
module.sanitize_public_article(fixture.article)
text = fixture.get_text(' ')
assert '77%' in text and 'margem de segurança' in text
assert '51,65' not in text and '+15%' not in text and '2 ações' not in text
assert not module.public_text('Carteiras brasileiras reais, preço médio R$ 51,65.')
print('V2_DISCLOSURE_AND_RETENTION_REGRESSIONS_OK')

for name in ('besst-buffett-eua', 'magic-formula-eua'):
    page = BeautifulSoup((ROOT / f'v2/rankings/historico/{name}.html').read_text(), 'html.parser')
    assert not page.select('.kpis,.portfolio-v31-title'), name
    assert len(page.select('.v2-history-tabs button')) == 4, name
fgc = BeautifulSoup((ROOT / 'v2/rankings/renda-fixa-fgc.html').read_text(), 'html.parser')
assert fgc.select_one('script[src^="/js/v2/fgc.js?"]')
assert not fgc.select('script[src^="/scripts/fgc-dynamic.js"]')
assert 'function applyFilters()' not in str(fgc)
# Legacy cache-version changes must not reintroduce a relative-fetch loader.
fgc_route = next(r for r in module.ROUTES if r['source'] == 'ranking_fgc.html')
original_extract = module.extract_source
try:
    module.extract_source = lambda _: ('<script src="/scripts/fgc-dynamic.js?v=future"></script>', 'FGC')
    assert '/js/v2/fgc.js?' in module.source_page(fgc_route)
finally:
    module.extract_source = original_extract
print('V2_US_HISTORY_AND_FGC_REGRESSIONS_OK')
