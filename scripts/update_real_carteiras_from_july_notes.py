#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY_BR = "14/07/2026"
TODAY_ISO = "2026-07-14"
COLORS = ["var(--gold)","#e74c3c","#1abc9c","#3498db","#9b59b6","#f39c12","#2ecc71","#95a5a6","#e91e63","#00bcd4","#8e44ad","#16a085","#c0392b","#27ae60","#d35400","#7f8c8d"]

CSS_END = '</style></head><body><div class="bg-img"></div><a href="javascript:history.back()" class="back">← Voltar</a><div class="container">'

def brl(v):
    s = f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return s

def pct(v):
    return f"{v:.1f}%".replace('.', ',')

def chart_url(t):
    return f"https://www.tradingview.com/chart/?symbol=BMFBOVESPA%3A{t}"

def ticker_link(t, style=True):
    st = ' style="color:inherit;text-decoration:none"' if style else ''
    return f'<a href="{chart_url(t)}" target="_blank" rel="noopener noreferrer"{st}>{t}</a>'

def conic(items):
    start = 0.0
    parts = []
    for i, it in enumerate(items):
        end = start + 360.0 * it['valor'] / sum(x['valor'] for x in items)
        parts.append(f"{COLORS[i % len(COLORS)]} {start:.0f}deg {end:.0f}deg")
        start = end
    return 'conic-gradient(' + ','.join(parts) + ')'

def donut_center(total):
    return f'<div class="donut-center"><div class="donut-val">{brl(total).replace(" ","")}</div></div>'

def kpis(total, proventos, positions):
    return f'''<div class="kpis"><div class="kpi"><div class="kpi-val">{brl(total)}</div><div class="kpi-lab">Valor comprado</div></div><div class="kpi"><div class="kpi-val" style="color:var(--green)">{brl(proventos)}</div><div class="kpi-lab">Proventos recebidos</div></div><div class="kpi"><div class="kpi-val">{brl(total/len(positions))}</div><div class="kpi-lab">Ticket médio por posição</div></div><div class="kpi"><div class="kpi-val">{len(positions)}</div><div class="kpi-lab">Posições</div></div></div>'''

def asset_chart(positions):
    total = sum(p['valor'] for p in positions)
    items = sorted(positions, key=lambda p: p['valor'], reverse=True)
    rows = []
    for i, p in enumerate(items):
        rows.append(f'''<div class="legend-row"><div class="legend-info"><div class="legend-dot" style="background:{COLORS[i % len(COLORS)]}"></div><span class="legend-tick">{ticker_link(p['ticker'])}</span><span class="legend-sec">{p['setor']}</span></div><span class="legend-pct">{pct(100*p['valor']/total)}</span></div>''')
    return f'''<div class="chart-box"><div class="chart-title">📊 Distribuição por Ativo</div><div class="chart-flex"><div class="donut" style="background:{conic(items)}">{donut_center(total)}</div><div class="legend">{''.join(rows)}</div></div></div>'''

def sector_chart(positions):
    total = sum(p['valor'] for p in positions)
    sums = defaultdict(float)
    for p in positions:
        sums[p['setor']] += p['valor']
    items = [{'ticker':k,'setor':k,'valor':v} for k,v in sorted(sums.items(), key=lambda kv: kv[1], reverse=True)]
    maxv = max(x['valor'] for x in items)
    rows = []
    for i, it in enumerate(items):
        rows.append(f'''<div class="sec-row"><div class="sec-info"><div class="legend-dot" style="background:{COLORS[i % len(COLORS)]}"></div><span class="legend-tick">{it['setor']}</span></div><div class="sec-bar"><div style="width:{100*it['valor']/maxv:.0f}%;height:100%;background:{COLORS[i % len(COLORS)]};border-radius:3px"></div></div><span class="sec-pct">{pct(100*it['valor']/total)}</span></div>''')
    return f'''<div class="chart-box"><div class="chart-title">🏭 Alocação por Setor</div><div class="chart-flex" style="flex-direction:column"><div class="donut" style="background:{conic(items)}"><div class="donut-center"><div class="donut-val">{len(items)}</div></div></div><div style="width:100%">{''.join(rows)}</div></div></div>'''

def custody(positions):
    items = sorted(positions, key=lambda p: p['valor'], reverse=True)
    cards=[]
    for i,p in enumerate(items):
        unit = 'unidade' if p['qtd'] == 1 else 'unidades'
        avg = p['valor']/p['qtd']
        cards.append(f'''<div class="custodia-item" style="border-left-color:{COLORS[i % len(COLORS)]}"><div class="custodia-tick" style="color:{COLORS[i % len(COLORS)]}">{ticker_link(p['ticker'])}</div><div class="custodia-info">{p['empresa']} • {p['setor']}</div><div class="custodia-info">{p['qtd']} {unit} × {brl(avg)} preço médio</div><div class="custodia-valor">{brl(p['valor'])}</div></div>''')
    return f'''<div class="custodia-wrap"><div class="custodia-title">📊 Ações em Custódia</div><div class="custodia-grid">{''.join(cards)}</div></div>'''

def y_from_price(price, mn, mx):
    if mx == mn:
        return 44.0
    return 72 - (price-mn)/(mx-mn)*56

def price_history(positions):
    cards=[]
    for p in sorted(positions, key=lambda x: x['valor'], reverse=True):
        pts = p.get('precos', []) or [('Jul/26', p['valor']/p['qtd'])]
        prices=[v for _,v in pts]
        mn,mx=min(prices),max(prices)
        coords=[]
        for idx,(_,v) in enumerate(pts):
            x=16 if len(pts)==1 else 16 + idx*(228/(len(pts)-1))
            y=y_from_price(v,mn,mx)
            coords.append((x,y))
        d='M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x,y in coords)
        dots=''.join(f'<circle class="price-dot" cx="{x:.1f}" cy="{y:.1f}" r="4" />' for x,y in coords)
        labels=''.join(f'<span>{lab}</span>' for lab,_ in pts)
        values=''.join(f'<span><strong>{brl(v)}</strong></span>' for _,v in pts)
        var = 0 if prices[0] == 0 else (prices[-1]/prices[0]-1)*100
        cards.append(f'''<div class="price-card"><div class="price-head"><a class="price-ticker" href="{chart_url(p['ticker'])}" target="_blank" rel="noopener noreferrer">{p['ticker']}</a><div class="price-meta">{p['setor']}<br>var. desde início: {pct(var)}</div></div><svg class="price-svg" viewBox="0 0 260 88" role="img" aria-label="Evolução de preço"><line class="price-axis" x1="16" y1="72" x2="244" y2="72"/><path class="price-line" d="{d}"/>{dots}</svg><div class="price-labels">{labels}</div><div class="price-values">{values}</div><div class="price-note">Pontos atualizados a cada nova compra/inclusão enviada por nota de corretagem. Clique no ticker para abrir gráfico em tempo real.</div></div>''')
    return f'''<div class="price-history-wrap"><div class="price-history-title">📈 Evolução do preço por ação</div><div class="price-history-sub">Preço inicial de compra e evolução nos meses em que houve nova compra ou inclusão na carteira. Os nomes dos ativos abrem um gráfico em tempo real no TradingView.</div><div class="price-chart-grid">{''.join(cards)}</div></div>'''

def extract_proventos(html):
    m = re.search(r'(<div class="proventos-grid">.*?</div></div>)\s*<footer>', html, flags=re.S)
    return m.group(1) if m else ''

def extract_proventos_total(html):
    m = re.search(r'<div class="proventos-total">R\$\s*([0-9.,]+)</div>', html)
    if not m: return 0.0
    return float(m.group(1).replace('.','').replace(',','.'))

def render_page(path, title, subtitle, positions, emoji):
    old = path.read_text(encoding='utf-8')
    prefix = old.split(CSS_END)[0] + CSS_END
    prov = extract_proventos(old)
    prov_total = extract_proventos_total(old)
    total=sum(p['valor'] for p in positions)
    body = []
    body.append(f'<header style="text-align:center"><div style="display:inline-block"><h1>{emoji} {title}</h1><p class="sub">{subtitle}</p></div></header>')
    body.append(kpis(total, prov_total, positions))
    body.append(f'<div class="charts-grid">{asset_chart(positions)}{sector_chart(positions)}</div>')
    body.append(custody(positions))
    body.append(price_history(positions))
    body.append(prov)
    body.append(f'<footer>🦞 {title} | iaemloop.com.br | Atualizado em {TODAY_BR}</footer></div></body></html>')
    path.write_text(prefix + '\n'.join(body), encoding='utf-8')

besst = [
 {'ticker':'PETR4','empresa':'Petrobras','setor':'Petróleo','qtd':4,'valor':154.00,'precos':[('Jun/26',38.50)]},
 {'ticker':'KLBN4','empresa':'Klabin','setor':'Papel e Celulose','qtd':41,'valor':139.51,'precos':[('Mai/26',3.36),('Jun/26',3.43)]},
 {'ticker':'VIVT3','empresa':'Telefônica Brasil','setor':'Telecomunicações','qtd':4,'valor':133.28,'precos':[('Jun/26',33.32)]},
 {'ticker':'TAEE11','empresa':'Taesa','setor':'Energia','qtd':3,'valor':129.69,'precos':[('Mai/26',43.23)]},
 {'ticker':'CSMG3','empresa':'Copasa','setor':'Saneamento','qtd':2,'valor':107.66,'precos':[('Mai/26',53.83)]},
 {'ticker':'PSSA3','empresa':'Porto Seguro','setor':'Seguros','qtd':2,'valor':103.30,'precos':[('Mai/26',51.65)]},
 {'ticker':'ENGI3','empresa':'Energisa','setor':'Energia','qtd':18,'valor':219.30,'precos':[('Mai/26',12.35),('Jun/26',11.83),('Jul/26',12.21)]},
 {'ticker':'SAPR11','empresa':'Sanepar','setor':'Saneamento','qtd':2,'valor':88.66,'precos':[('Mai/26',44.33)]},
 {'ticker':'SANB11','empresa':'Santander Brasil','setor':'Bancos','qtd':9,'valor':245.55,'precos':[('Mai/26',27.47),('Jul/26',27.19)]},
 {'ticker':'VALE3','empresa':'Vale','setor':'Mineração','qtd':2,'valor':153.49,'precos':[('Jun/26',80.83),('Jul/26',72.66)]},
 {'ticker':'BRSR6','empresa':'Banrisul','setor':'Bancos','qtd':3,'valor':55.23,'precos':[('Mai/26',18.41)]},
 {'ticker':'BMGB4','empresa':'Banco BMG','setor':'Bancos','qtd':10,'valor':49.50,'precos':[('Mai/26',4.95)]},
 {'ticker':'CPLE3','empresa':'Copel','setor':'Energia','qtd':3,'valor':43.20,'precos':[('Mai/26',14.40)]},
 {'ticker':'EQTL3','empresa':'Equatorial Energia','setor':'Energia','qtd':2,'valor':80.26,'precos':[('Jul/26',40.13)]},
]
magic = [
 {'ticker':'PSSA3','empresa':'Porto Seguro','setor':'Seguros','qtd':3,'valor':151.72,'precos':[('Mai/26',48.50),('Jun/26',51.61)]},
 {'ticker':'CSED3','empresa':'Cruzeiro do Sul Educacional','setor':'Educação','qtd':34,'valor':145.97,'precos':[('Mai/26',6.33),('Jun/26',3.56)]},
 {'ticker':'QUAL3','empresa':'Qualicorp','setor':'Saúde','qtd':85,'valor':140.85,'precos':[('Mai/26',1.89),('Jun/26',1.56)]},
 {'ticker':'CSUD3','empresa':'CSU Digital','setor':'Tecnologia/Serviços','qtd':8,'valor':136.36,'precos':[('Mai/26',19.14),('Jun/26',15.79)]},
 {'ticker':'VTRU3','empresa':'Vitru Educação','setor':'Educação','qtd':9,'valor':123.96,'precos':[('Mai/26',14.18),('Jun/26',13.57)]},
 {'ticker':'TGMA3','empresa':'Tegma','setor':'Logística','qtd':3,'valor':110.29,'precos':[('Mai/26',39.40),('Jun/26',31.49)]},
 {'ticker':'WIZC3','empresa':'Wiz Co','setor':'Seguros/Corretagem','qtd':24,'valor':201.32,'precos':[('Mai/26',8.55),('Jun/26',7.53),('Jul/26',8.48)]},
 {'ticker':'PLPL3','empresa':'Plano & Plano','setor':'Construção civil','qtd':21,'valor':204.06,'precos':[('Mai/26',11.81),('Jul/26',8.15)]},
 {'ticker':'CMIN3','empresa':'CSN Mineração','setor':'Mineração','qtd':32,'valor':167.62,'precos':[('Mai/26',5.05),('Jul/26',5.55)]},
 {'ticker':'PETR4','empresa':'Petrobras','setor':'Petróleo','qtd':2,'valor':83.56,'precos':[('Mai/26',41.78)]},
 {'ticker':'BEEF3','empresa':'Minerva','setor':'Alimentos','qtd':10,'valor':49.40,'precos':[('Mai/26',4.94)]},
 {'ticker':'POMO3','empresa':'Marcopolo','setor':'Industrial/Autopeças','qtd':21,'valor':110.88,'precos':[('Jul/26',5.28)]},
 {'ticker':'LEVE3','empresa':'Metal Leve','setor':'Autopeças','qtd':4,'valor':128.56,'precos':[('Jul/26',32.14)]},
]

render_page(ROOT/'carteira_besst_real.html', 'Carteira BESST', 'Método Barsi + Buffett', besst, '💎')
render_page(ROOT/'carteira_magic_formula_real.html', 'Carteira Magic Formula', 'Método Joel Greenblatt', magic, '🎯')

ledger_script = ROOT / 'scripts' / 'update_investment_cost_ledger_from_known_notes.py'
if ledger_script.exists():
    import subprocess
    subprocess.run(['python3', str(ledger_script)], check=True)
    print('updated pages and refreshed data/investment_costs_2026.json via ledger v2')
else:
    print('updated pages; cost ledger script not found, leaving existing data/investment_costs_2026.json unchanged')
print('besst_total',sum(p['valor'] for p in besst),'positions',len(besst))
print('magic_total',sum(p['valor'] for p in magic),'positions',len(magic))
