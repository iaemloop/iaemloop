#!/usr/bin/env python3
from __future__ import annotations
import csv
import html as html_lib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = '2026-08-23'

MANUAL_SIMPLE = [
    {
        'ticker': 'TSLA',
        'empresa': 'Tesla, Inc.',
        'setor': 'Consumer Cyclical',
        'industria': 'Auto Manufacturers',
        'observacoes': 'Observação temática: empresa pública sob liderança de Elon Musk; acompanhar execução em veículos elétricos, autonomia, robótica/Optimus e energia. Para exposição espacial direta, acompanhar também SPCX. X/xAI, Neuralink e Boring permanecem no radar qualitativo por não serem negociáveis diretamente em bolsa.'
    },
    {
        'ticker': 'SPCX',
        'empresa': 'Space Exploration Technologies Corp.',
        'setor': 'Industrials',
        'industria': 'Aerospace & Defense',
        'observacoes': 'Observação temática: exposição direta negociável em bolsa ligada à tese espacial/SpaceX. Monitorar valuation, ritmo de crescimento, contratos governamentais/comerciais, lançamentos, margem, capex e risco de alta expectativa já precificada.'
    },
    {
        'ticker': 'NVDA',
        'empresa': 'NVIDIA Corporation',
        'setor': 'Technology',
        'industria': 'Semiconductors',
        'observacoes': 'Observação temática: IA/aceleradores/data centers; Diego tem feeling de valorização adicional. Monitorar valuation, margens, demanda por GPUs e risco de concentração.'
    },
    {
        'ticker': 'TTWO',
        'empresa': 'Take-Two Interactive Software, Inc.',
        'setor': 'Communication Services',
        'industria': 'Electronic Gaming & Multimedia',
        'observacoes': 'Observação temática: possível reprecificação conforme aproximação do lançamento de GTA 6 e, depois, GTA 6 Online. Monitorar janela de lançamento, guidance, reservas/bookings e risco de atraso.'
    },
    {
        'ticker': 'MELI',
        'empresa': 'MercadoLibre, Inc.',
        'setor': 'Consumer Cyclical',
        'industria': 'Internet Retail',
        'observacoes': 'Observação satélite: plataforma dominante de comércio eletrônico, pagamentos e crédito na América Latina. Acompanhar crescimento, margem, risco de crédito/fintech, competição e valuation; não é compra automática pelo ranking principal por múltiplo elevado.'
    },
]

# Public ranking display overrides for thematic names, grounded in yfinance/Yahoo data checked on 2026-07-14.
# Dividend Yield also states whether the company distributes recurring dividends/proventos.
MANUAL_METRICS = {
    'TSLA': {
        'pl': '370,2', 'evEbitda': '131,1', 'roe': '4,9%',
        'divYield': '0,0% — não distribui dividendos/proventos recorrentes'
    },
    'SPCX': {
        'pl': 'n/d — sem P/L divulgado', 'evEbitda': '207,8', 'roe': 'n/d',
        'divYield': '0,0% — não distribui dividendos/proventos recorrentes'
    },
    'NVDA': {
        'pl': '33,1', 'evEbitda': '29,5', 'roe': '114,3%',
        'divYield': '0,47% — distribui dividendos/proventos'
    },
    'TTWO': {
        'pl': 'n/d — sem lucro recorrente/P/L', 'evEbitda': '58,7', 'roe': '-10,6%',
        'divYield': '0,0% — sem dividendo recorrente; registro residual em 2008'
    },
    'MELI': {
        'pl': '52,4', 'evEbitda': '27,0', 'roe': '27,5%',
        'divYield': '0,0% — não distribui dividendos/proventos recorrentes'
    },
}

MANUAL_NUMERIC = {
    # yfinance snapshot checked 2026-08-23. Used only while the broad
    # fundamentals latest has not been regenerated from the 521-name universe.
    'MELI': {
        'pl': 52.36,
        'fwdPE': 33.90,
        'evEbitda': 26.96,
        'roe': 27.50,
        'opMargin': 6.72,
        'fcfYield': 0.36,
        'ebitdaYield': 3.71,
        'divYield': 0.00,
    },
}

fund_assets = {r['ticker']: r for r in json.load(open(ROOT/'outputs/stocks_eua_fundamentos_latest.json', encoding='utf-8'))['assets']}

def safe_num(v):
    if v is None: return ''
    try:
        if math.isnan(float(v)): return ''
        return round(float(v), 2)
    except Exception:
        return ''

# Update simple output CSVs used by the page/pipeline lineage.
for rel in ['outputs/watchlist_buffett_permanente_eua_latest.csv', 'outputs/watchlist_buffett_permanente_eua_2026-08.csv']:
    path = ROOT / rel
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    # Guard against a stale/short latest: use the monthly August file as the base
    # when it contains more rows, then write both monthly and latest consistently.
    monthly_path = ROOT / 'outputs/watchlist_buffett_permanente_eua_2026-08.csv'
    if path.name == 'watchlist_buffett_permanente_eua_latest.csv' and monthly_path.exists():
        monthly_rows = list(csv.DictReader(open(monthly_path, encoding='utf-8-sig')))
        if len(monthly_rows) > len(rows):
            rows = monthly_rows
    fieldnames = rows[0].keys() if rows else ['ticker','empresa','setor','industria','roe_pct','dividend_yield_pct','observacoes']
    by_ticker = {r['ticker']: r for r in rows}
    for item in MANUAL_SIMPLE:
        f = fund_assets.get(item['ticker'], {})
        mn = MANUAL_NUMERIC.get(item['ticker'], {})
        by_ticker[item['ticker']] = {
            'ticker': item['ticker'],
            'empresa': item['empresa'],
            'setor': item['setor'],
            'industria': item['industria'],
            'roe_pct': safe_num(f.get('roe')) or mn.get('roe', ''),
            'dividend_yield_pct': safe_num(f.get('dividend_yield')) if safe_num(f.get('dividend_yield')) != '' else mn.get('divYield', ''),
            'observacoes': item['observacoes'],
        }
    out = list(rows)
    existing = {r['ticker'] for r in rows}
    for item in MANUAL_SIMPLE:
        if item['ticker'] not in existing:
            out.append(by_ticker[item['ticker']])
        else:
            for i,r in enumerate(out):
                if r['ticker'] == item['ticker']:
                    out[i] = by_ticker[item['ticker']]
    with open(path, 'w', encoding='utf-8', newline='') as fp:
        w=csv.DictWriter(fp, fieldnames=fieldnames, lineterminator='\n')
        w.writeheader(); w.writerows(out)

# Update rich data CSV so future readers see manual additions.
path = ROOT / 'data/watchlist_buffett_permanente_eua.csv'
rows = list(csv.DictReader(open(path, encoding='utf-8')))
fieldnames = list(rows[0].keys())
existing = {r['ticker'] for r in rows}
for item in MANUAL_SIMPLE:
    f = fund_assets.get(item['ticker'], {})
    mn = MANUAL_NUMERIC.get(item['ticker'], {})
    row = {k: '' for k in fieldnames}
    row.update({
        'ticker': item['ticker'],
        'empresa': item['empresa'],
        'setor': item['setor'],
        'industria': item['industria'],
        'pl': safe_num(f.get('pe')) or mn.get('pl', ''),
        'fwdPE': safe_num(f.get('pe_forward')) or mn.get('fwdPE', ''),
        'evEbitda': safe_num(f.get('ev_ebitda')) or mn.get('evEbitda', ''),
        'roe': safe_num(f.get('roe')) or mn.get('roe', ''),
        'opMargin': safe_num(f.get('operatingMargins')) or mn.get('opMargin', ''),
        'fcfYield': safe_num(f.get('fcfYield')) or mn.get('fcfYield', ''),
        'ebitdaYield': safe_num(f.get('ebitdaYield')) or mn.get('ebitdaYield', ''),
        'divYield': safe_num(f.get('dividend_yield')) if safe_num(f.get('dividend_yield')) != '' else mn.get('divYield', ''),
        'moat': '',
        'qualityScore': '',
        'watchlistScore': '',
    })
    if item['ticker'] in existing:
        rows = [row if r['ticker']==item['ticker'] else r for r in rows]
    else:
        rows.append(row)
with open(path, 'w', encoding='utf-8', newline='') as fp:
    w=csv.DictWriter(fp, fieldnames=fieldnames, lineterminator='\n')
    w.writeheader(); w.writerows(rows)

# Update public HTML: do NOT publish the internal thematic notes as cards.
# Public page should only include these tickers as final watchlist rows.
html_path = ROOT / 'watchlist_buffett_permanente_eua.html'
html = html_path.read_text(encoding='utf-8')

# Remove legacy card styles/section if they were previously published.
html = re.sub(r'\n    \.manual-grid \{.*?\.manual-card p \{[^\n]*\}\n', '\n', html, flags=re.S)
html = re.sub(r'    <section class="panel">\n      <h2 style="color:#E4D17F;margin-bottom:14px">Observações temáticas adicionadas em .*?</section>\n', '', html, flags=re.S)

def pct_fmt(v):
    n = safe_num(v)
    return '' if n == '' else f'{n:.1f}%'.replace('.', ',')

def row_html(rank, item):
    f = fund_assets.get(item['ticker'], {})
    metrics = MANUAL_METRICS.get(item['ticker'])
    if metrics:
        pe = metrics['pl']
        ev = metrics['evEbitda']
        roe = metrics['roe']
        dy = metrics['divYield']
    else:
        pe_num = safe_num(f.get('pe'))
        ev_num = safe_num(f.get('ev_ebitda'))
        pe = '-' if pe_num == '' else str(pe_num).replace('.', ',')
        ev = '-' if ev_num == '' else str(ev_num).replace('.', ',')
        roe = pct_fmt(f.get('roe'))
        dy = pct_fmt(f.get('dividend_yield'))
    return (
        f"<tr><td class='rank'>{rank}</td><td class='ticker'>{html_lib.escape(item['ticker'])}</td>"
        f"<td>{html_lib.escape(item['empresa'])}</td><td>{html_lib.escape(item['setor'])}</td>"
        f"<td>{html_lib.escape(pe)}</td>"
        f"<td>{html_lib.escape(ev)}</td>"
        f"<td>{html_lib.escape(roe)}</td><td>{html_lib.escape(dy)}</td></tr>"
    )

tbody_match = re.search(r'<tbody>(.*?)</tbody>', html, flags=re.S)
if tbody_match:
    tbody = tbody_match.group(1)
    manual_tickers = {item['ticker'] for item in MANUAL_SIMPLE}
    # Drop old manual rows before appending them at the end in fixed order.
    for ticker in manual_tickers:
        tbody = re.sub(rf"\n?<tr><td class='rank'>\d+</td><td class='ticker'>{re.escape(ticker)}</td>.*?</tr>", '', tbody, flags=re.S)
    ranks = [int(x) for x in re.findall(r"<td class='rank'>(\d+)</td>", tbody)]
    next_rank = (max(ranks) if ranks else 0) + 1
    manual_rows = []
    for i, item in enumerate(MANUAL_SIMPLE):
        manual_rows.append(row_html(next_rank + i, item))
    tbody = tbody.rstrip() + '\n' + '\n'.join(manual_rows)
    html = html[:tbody_match.start(1)] + tbody + html[tbody_match.end(1):]
html = re.sub(r'Atualizado em (?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\.', f'Atualizado em {TODAY}.', html)
html_path.write_text(html, encoding='utf-8')
print('updated watchlist manual additions')
