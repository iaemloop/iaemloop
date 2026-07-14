#!/usr/bin/env python3
from __future__ import annotations
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = '2026-07-14'

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
]

fund_assets = {r['ticker']: r for r in json.load(open(ROOT/'outputs/stocks_eua_fundamentos_latest.json', encoding='utf-8'))['assets']}

def safe_num(v):
    if v is None: return ''
    try:
        if math.isnan(float(v)): return ''
        return round(float(v), 2)
    except Exception:
        return ''

# Update simple output CSVs used by the page/pipeline lineage.
for rel in ['outputs/watchlist_buffett_permanente_eua_latest.csv', 'outputs/watchlist_buffett_permanente_eua_2026-07.csv']:
    path = ROOT / rel
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    fieldnames = rows[0].keys() if rows else ['ticker','empresa','setor','industria','roe_pct','dividend_yield_pct','observacoes']
    by_ticker = {r['ticker']: r for r in rows}
    for item in MANUAL_SIMPLE:
        f = fund_assets.get(item['ticker'], {})
        by_ticker[item['ticker']] = {
            'ticker': item['ticker'],
            'empresa': item['empresa'],
            'setor': item['setor'],
            'industria': item['industria'],
            'roe_pct': safe_num(f.get('roe')),
            'dividend_yield_pct': safe_num(f.get('dividend_yield')),
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
    row = {k: '' for k in fieldnames}
    row.update({
        'ticker': item['ticker'],
        'empresa': item['empresa'],
        'setor': item['setor'],
        'industria': item['industria'],
        'pl': safe_num(f.get('pe')),
        'fwdPE': safe_num(f.get('pe_forward')),
        'evEbitda': safe_num(f.get('ev_ebitda')),
        'roe': safe_num(f.get('roe')),
        'divYield': safe_num(f.get('dividend_yield')),
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

# Update public HTML with a manual thematic panel.
html_path = ROOT / 'watchlist_buffett_permanente_eua.html'
html = html_path.read_text(encoding='utf-8')
style_add = """
    .manual-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .manual-card { background: rgba(6,8,13,0.55); border: 1px solid rgba(110,228,239,0.22); border-radius: 10px; padding: 16px; }
    .manual-card strong { color: #6EE4EF; font-size: 1.05rem; }
    .manual-card span { color: #E4D17F; font-weight: 800; }
    .manual-card p { color: #94a3b8; line-height: 1.55; margin-top: 8px; font-size: 0.92rem; }
"""
if '.manual-grid' not in html:
    html = html.replace('    .note { color: #94a3b8; font-size: 0.9rem; line-height: 1.7; }\n', '    .note { color: #94a3b8; font-size: 0.9rem; line-height: 1.7; }\n' + style_add)
manual_section = f'''    <section class="panel">
      <h2 style="color:#E4D17F;margin-bottom:14px">Observações temáticas adicionadas em {TODAY}</h2>
      <div class="manual-grid">
        <div class="manual-card"><strong>TSLA</strong> <span>Tesla / Elon Musk</span><p>Empresa pública sob liderança de Elon Musk. Acompanhar autonomia, robótica/Optimus, energia, margens e risco de valuation. Para exposição espacial direta, acompanhar também SPCX; X/xAI, Neuralink e Boring ficam no radar qualitativo.</p></div>
        <div class="manual-card"><strong>SPCX</strong> <span>Space Exploration Technologies</span><p>Exposição direta negociável em bolsa ligada à tese espacial/SpaceX. Monitorar valuation, contratos governamentais e comerciais, ritmo de lançamentos, capex, margens e risco de expectativa alta já precificada.</p></div>
        <div class="manual-card"><strong>NVDA</strong> <span>NVIDIA</span><p>Tese de IA/aceleradores/data centers. Diego quer manter atenção por possível valorização adicional; monitorar demanda por GPUs, margens, múltiplos e risco de concentração.</p></div>
        <div class="manual-card"><strong>TTWO</strong> <span>Take-Two / GTA 6</span><p>Tese de evento/catalisador: possível valorização conforme se aproximarem GTA 6 e GTA 6 Online. Monitorar datas oficiais, risco de atraso, guidance, reservas/bookings e monetização online.</p></div>
      </div>
      <p class="note" style="margin-top:14px">Esses nomes são watchlist/monitoramento, não recomendação automática. Eles podem ficar fora do Top 20 quantitativo mensal e ainda assim merecer acompanhamento qualitativo.</p>
    </section>
'''
html = re.sub(r'    <section class="panel">\n      <h2 style="color:#E4D17F;margin-bottom:14px">Observações temáticas adicionadas em .*?</section>\n', '', html, flags=re.S)
html = html.replace('    <section class="panel table-wrap"><table>\n', manual_section + '    <section class="panel table-wrap"><table>\n')
html = html.replace('Atualizado em 2026-07-11.', f'Atualizado em {TODAY}.')
html_path.write_text(html, encoding='utf-8')
print('updated watchlist manual additions')
