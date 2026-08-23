#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, math, re
from collections import defaultdict
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
TODAY_BR = '21/08/2026'
TODAY_ISO = '2026-08-21'
COLORS = ['var(--gold)','#e74c3c','#1abc9c','#3498db','#9b59b6','#f39c12','#2ecc71','#95a5a6','#e91e63','#00bcd4','#8e44ad','#16a085','#c0392b','#27ae60','#d35400','#7f8c8d']
MONTH_ORDER = {'Jan':1,'Fev':2,'Mar':3,'Abr':4,'Mai':5,'Jun':6,'Jul':7,'Ago':8,'Set':9,'Out':10,'Nov':11,'Dez':12}
MONTH_LABEL = {'2026-03':'Mar/26','2026-05':'Mai/26','2026-06':'Jun/26','2026-07':'Jul/26','2026-08':'Ago/26'}

COMPANY = {
 'TAEE11':('Taesa','Energia'),'CSMG3':('Copasa','Saneamento'),'PSSA3':('Porto Seguro','Seguros'),'SAPR11':('Sanepar','Saneamento'),
 'BRSR6':('Banrisul','Bancos'),'BMGB4':('Banco BMG','Bancos'),'CPLE3':('Copel','Energia'),'ENGI3':('Energisa','Energia'),
 'KLBN4':('Klabin','Papel e Celulose'),'SANB11':('Santander Brasil','Bancos'),'PETR4':('Petrobras','Petróleo'),'VIVT3':('Telefônica Brasil','Telecomunicações'),
 'VALE3':('Vale','Mineração'),'EQTL3':('Equatorial Energia','Energia'),'CSED3':('Cruzeiro do Sul Educacional','Educação'),'CMIN3':('CSN Mineração','Mineração'),
 'CSUD3':('CSU Digital','Tecnologia/Serviços'),'BEEF3':('Minerva','Alimentos'),'PLPL3':('Plano & Plano','Construção civil'),'QUAL3':('Qualicorp','Saúde'),
 'TGMA3':('Tegma','Logística'),'VTRU3':('Vitru Educação','Educação'),'WIZC3':('Wiz Co','Seguros/Corretagem'),'POMO3':('Marcopolo','Industrial/Autopeças'),
 'LEVE3':('Metal Leve','Autopeças'),
 'ZTS':('Zoetis Inc.','Saúde animal / Healthcare'),'AAPL':('Apple Inc.','Tecnologia / Ecossistema'),'MA':('Mastercard Incorporated','Pagamentos'),
 'ADBE':('Adobe Inc.','Software'),'PGR':('Progressive Corporation','Seguros'),'BMY':('Bristol-Myers Squibb Company','Saúde / Pharma'),
 'CME':('CME Group Inc.','Mercados financeiros'),'TSM':('Taiwan Semiconductor Manufacturing','Semicondutores'),'ALL':('Allstate Corp.','Seguros'),
}

def brl(v: float) -> str:
    return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def usd(v: float) -> str:
    return f'US$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def pct(v: float) -> str:
    return f'{v:.1f}%'.replace('.', ',')

def fmt_num(v, nd=8):
    if isinstance(v, int) or abs(v-round(v)) < 1e-10:
        return str(int(round(v)))
    return f'{v:.{nd}f}'.rstrip('0').rstrip('.')

def parse_month(date_s: str) -> str:
    if not date_s: return 'N/D'
    m = re.match(r'(\d{4}-\d{2})', date_s)
    return MONTH_LABEL.get(m.group(1), m.group(1) if m else date_s)

def label_sort_key(label):
    try:
        mon, yy = label.split('/')
        return (2000+int(yy), MONTH_ORDER.get(mon,99))
    except Exception:
        return (9999,99)

def chart_url(t, currency='BRL'):
    if currency == 'USD':
        # Most current positions are US/Nasdaq/NYSE names; TradingView resolves many via search query.
        return f'https://www.tradingview.com/chart/?symbol={html.escape(t)}'
    return f'https://www.tradingview.com/chart/?symbol=BMFBOVESPA%3A{html.escape(t)}'

def ticker_link(t, currency='BRL'):
    return f'<a href="{chart_url(t,currency)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none">{html.escape(t)}</a>'

def load_ledger():
    return json.loads((DATA/'investment_costs_2026.json').read_text(encoding='utf-8'))

def build_b3_positions(portfolio):
    ledger = load_ledger()
    buckets = defaultdict(lambda: {'ticker':'','empresa':'','setor':'','qtd':0.0,'valor':0.0,'precos':[], 'months':defaultdict(lambda:{'qtd':0.0,'valor':0.0})})
    for e in ledger.get('entries',[]):
        if e.get('portfolio') != portfolio or e.get('currency') != 'BRL':
            continue
        lab = parse_month(e.get('date') or '')
        for tr in e.get('trades') or []:
            t = tr['ticker']
            q = float(tr.get('quantity') or 0)
            val = float(tr.get('gross_value_brl') or (q * float(tr.get('average_price_brl') or 0)))
            if not q or not val: continue
            emp,setor = COMPANY.get(t,(t,'Outros'))
            b = buckets[t]
            b.update({'ticker':t,'empresa':emp,'setor':setor})
            b['qtd'] += q; b['valor'] += val
            b['months'][lab]['qtd'] += q; b['months'][lab]['valor'] += val
    positions=[]
    for t,b in buckets.items():
        precos=[]
        for lab, mv in sorted(b['months'].items(), key=lambda kv: label_sort_key(kv[0])):
            if mv['qtd']:
                precos.append((lab, mv['valor']/mv['qtd']))
        positions.append({k:b[k] for k in ['ticker','empresa','setor']} | {'qtd':b['qtd'],'valor':round(b['valor'],2),'precos':precos})
    return sorted(positions, key=lambda p:p['valor'], reverse=True)

def portfolio_costs(portfolio, currency='BRL'):
    ledger=load_ledger(); rows=[]; by_broker=defaultdict(lambda:{'gross_brl':0,'gross_usd':0,'known_cost_brl':0,'known_cost_usd':0,'unknown':0,'entries':0,'brokerage_brl':0,'spread_brl':0,'iof_brl':0})
    for e in ledger.get('entries',[]):
        if e.get('portfolio') != portfolio and not (portfolio == 'Dolarizadas / Stocks EUA' and e.get('portfolio') in ('Dolarizadas / Stocks EUA','BESST & Buffett Dolarizado','Magic Formula Dolarizada')):
            continue
        b=by_broker[e.get('broker') or 'N/D']; b['entries'] += 1
        if e.get('currency') == 'BRL': b['gross_brl'] += float(e.get('gross_operations_brl') or 0)
        elif e.get('currency') == 'USD': b['gross_usd'] += float(e.get('gross_operations_usd') or 0)
        else:
            b['gross_brl'] += float(e.get('gross_operations_brl') or 0); b['gross_usd'] += float(e.get('gross_operations_usd') or 0)
        if e.get('cost_total_brl') is None and e.get('cost_total_usd') is None:
            b['unknown'] += 1
        else:
            b['known_cost_brl'] += float(e.get('cost_total_brl') or 0)
            b['known_cost_usd'] += float(e.get('cost_total_usd') or 0)
        c=e.get('costs') or {}
        b['brokerage_brl'] += float(c.get('brokerage_brl') or 0)
        b['spread_brl'] += float(c.get('fx_spread_brl') or 0)
        b['iof_brl'] += float(c.get('iof_brl') or 0)
    return by_broker

def global_costs():
    ledger=load_ledger(); by=defaultdict(lambda:{'gross_brl':0,'gross_usd':0,'known_cost_brl':0,'known_cost_usd':0,'unknown':0,'entries':0,'brokerage_brl':0,'spread_brl':0,'iof_brl':0,'portfolios':set()})
    for e in ledger.get('entries',[]):
        b=by[e.get('broker') or 'N/D']; b['entries']+=1; b['portfolios'].add(e.get('portfolio') or '')
        if e.get('currency') == 'USD': b['gross_usd'] += float(e.get('gross_operations_usd') or 0)
        else: b['gross_brl'] += float(e.get('gross_operations_brl') or 0)
        if e.get('cost_total_brl') is None and e.get('cost_total_usd') is None: b['unknown']+=1
        b['known_cost_brl'] += float(e.get('cost_total_brl') or 0)
        b['known_cost_usd'] += float(e.get('cost_total_usd') or 0)
        c=e.get('costs') or {}; b['brokerage_brl'] += float(c.get('brokerage_brl') or 0); b['spread_brl'] += float(c.get('fx_spread_brl') or 0); b['iof_brl'] += float(c.get('iof_brl') or 0)
    return by

def conic(items, valkey='valor'):
    total=sum(x[valkey] for x in items) or 1
    start=0; parts=[]
    for i,it in enumerate(items):
        end=start+360*it[valkey]/total
        parts.append(f'{COLORS[i%len(COLORS)]} {start:.0f}deg {end:.0f}deg'); start=end
    return 'conic-gradient('+','.join(parts)+')'

def page_shell(title, meta_desc, body):
    css = r'''
:root{--bg:#0c1016;--card:#141820;--gold:#d4af37;--green:#22c55e;--red:#ef4444;--text:#fff;--text2:#8b92a8;--border:#1e2330}.bg-img{position:fixed;inset:0;z-index:-1;opacity:.08;background:url('assets/bg-carteiras.jpg') center/cover no-repeat;pointer-events:none}body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);padding:24px;margin:0}.container{max-width:1400px;margin:0 auto}.back{position:fixed;top:20px;left:20px;background:var(--card);color:var(--gold);padding:10px 16px;border-radius:8px;text-decoration:none;z-index:1000}h1{color:var(--gold);font-size:32px;margin:0}p.sub{color:var(--text2);margin-top:6px}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}.kpi{background:var(--card);padding:20px;border-radius:12px;transition:all .3s}.kpi:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(212,175,55,.2)}.kpi-val{font-size:28px;font-weight:600;color:var(--gold)}.kpi-lab{color:var(--text2);font-size:14px;margin-top:6px}.charts-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:32px}.chart-box,.panel{background:var(--card);border-radius:16px;padding:32px;margin-bottom:32px}.chart-title,.panel-title{color:var(--gold);font-size:20px;margin-bottom:16px}.chart-flex{display:flex;align-items:center;gap:32px}.donut{position:relative;width:180px;height:180px;border-radius:50%;flex-shrink:0}.donut::after{content:"";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:120px;height:120px;background:var(--card);border-radius:50%}.donut-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;z-index:1}.donut-val{font-size:22px;font-weight:700;color:var(--gold)}.legend{flex:1}.legend-row,.cost-row,.proventos-row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)}.legend-info{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.legend-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}.legend-tick{font-weight:700}.legend-sec,.note,small{color:var(--text2)}.legend-pct,.cost-val,.proventos-valor{font-weight:800;color:var(--gold);white-space:nowrap}.sec-row{display:flex;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}.sec-info{display:flex;align-items:center;gap:10px;min-width:170px}.sec-bar{flex:1;height:6px;background:var(--bg);border-radius:3px;margin:0 12px}.sec-pct{font-weight:800;color:var(--gold);min-width:54px;text-align:right}.portfolio-v31{background:var(--card);border-radius:16px;padding:32px;margin-bottom:32px;border-left:4px solid var(--gold)}.portfolio-v31-title{color:var(--gold);font-size:20px;margin-bottom:8px}.portfolio-v31-sub{color:var(--text2);font-size:14px;line-height:1.55;margin-bottom:20px}.portfolio-v31-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.55fr);gap:20px;align-items:start}.area-chart{width:100%;height:auto;background:#080b11;border:1px solid var(--border);border-radius:16px;box-shadow:inset 0 0 0 1px rgba(212,175,55,.04),0 18px 45px rgba(0,0,0,.22)}.area-note{color:var(--text2);font-size:13px;line-height:1.5;margin-top:10px}.v31-side{display:flex;flex-direction:column;gap:8px;max-height:480px;overflow:auto;padding-right:4px}.v31-row{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;background:#10151d;border:1px solid var(--border);border-radius:10px;padding:10px 11px}.v31-dot{width:11px;height:11px;border-radius:50%;display:inline-block}.v31-row b{font-size:15px}.v31-row small{display:block;line-height:1.4;margin-top:3px}.v31-weight{color:var(--gold);font-size:12px;font-weight:800}.proventos-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:32px 0}.proventos-wrap{background:var(--card);border-radius:16px;padding:32px;border-left:4px solid #9b59b6}.proventos-wrap.future{border-left-color:#3498db}.proventos-title{color:#9b59b6;font-size:20px;margin-bottom:12px}.future .proventos-title{color:#3498db}.proventos-total{font-size:32px;font-weight:700;color:var(--gold);margin-bottom:16px}.cost-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.cost-card{background:#10151d;border:1px solid var(--border);border-radius:12px;padding:16px}.cost-card h3{margin:0 0 8px;color:var(--gold)}.warn{color:#f59e0b}.ok{color:var(--green)}footer{text-align:center;padding:40px;color:var(--text2);border-top:1px solid var(--border);margin-top:40px}@media(max-width:1000px){.charts-grid,.proventos-grid{grid-template-columns:1fr}}@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.chart-flex{flex-direction:column}body{padding:16px}.back{position:static;display:inline-block;margin-bottom:16px}.portfolio-v31-grid{grid-template-columns:1fr}.v31-side{max-height:none}}
'''
    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(meta_desc)}"><style>{css}</style></head><body><div class="bg-img"></div><a href="javascript:history.back()" class="back">← Voltar</a><div class="container">{body}</div></body></html>'''

def kpis(total, proventos, positions, currency='BRL', extra_label='Valor comprado'):
    money = brl if currency=='BRL' else usd
    ticket = total / len(positions) if positions else 0
    proventos_txt = brl(proventos) if currency == 'BRL' else usd(proventos)
    return f'<div class="kpis"><div class="kpi"><div class="kpi-val">{money(total)}</div><div class="kpi-lab">{extra_label}</div></div><div class="kpi"><div class="kpi-val" style="color:var(--green)">{proventos_txt}</div><div class="kpi-lab">Proventos recebidos</div></div><div class="kpi"><div class="kpi-val">{money(ticket)}</div><div class="kpi-lab">Ticket médio por posição</div></div><div class="kpi"><div class="kpi-val">{len(positions)}</div><div class="kpi-lab">Posições</div></div></div>'

def charts(positions, valkey='valor', currency='BRL'):
    total=sum(p[valkey] for p in positions) or 1; money=brl if currency=='BRL' else usd
    items=sorted(positions,key=lambda p:p[valkey],reverse=True)
    leg=''.join(f'<div class="legend-row"><div class="legend-info"><div class="legend-dot" style="background:{COLORS[i%len(COLORS)]}"></div><span class="legend-tick">{ticker_link(p["ticker"],currency)}</span><span class="legend-sec">{html.escape(p["setor"])}</span></div><span class="legend-pct">{pct(100*p[valkey]/total)}</span></div>' for i,p in enumerate(items))
    asset=f'<div class="chart-box"><div class="chart-title">📊 Distribuição por Ativo</div><div class="chart-flex"><div class="donut" style="background:{conic(items,valkey)}"><div class="donut-center"><div class="donut-val">{money(total).replace(" ","")}</div></div></div><div class="legend">{leg}</div></div></div>'
    sums=defaultdict(float)
    for p in positions: sums[p['setor']] += p[valkey]
    maxv=max(sums.values() or [1]); sector_rows=[]
    for i,(sec,val) in enumerate(sorted(sums.items(),key=lambda kv:kv[1],reverse=True)):
        sector_rows.append(f'<div class="sec-row"><div class="sec-info"><span class="legend-dot" style="background:{COLORS[i%len(COLORS)]}"></span><span>{html.escape(sec)}</span></div><div class="sec-bar"><div style="height:100%;width:{100*val/maxv:.1f}%;background:{COLORS[i%len(COLORS)]};border-radius:3px"></div></div><span class="sec-pct">{pct(100*val/total)}</span></div>')
    sector=f'<div class="chart-box"><div class="chart-title">🏭 Alocação por Setor</div>{"".join(sector_rows)}</div>'
    return f'<div class="charts-grid">{asset}{sector}</div>'

def area_chart(positions, currency='BRL', value_is_price=True, height=390, width=980):
    labels=[]
    for p in positions:
        for lab,_ in p.get('precos',[]):
            if lab not in labels: labels.append(lab)
    labels.sort(key=label_sort_key)
    if not labels: labels=['Atual']
    allvals=[v for p in positions for _,v in (p.get('precos') or [('Atual',p.get('avg_price_usd') or p.get('valor',0)/max(p.get('qtd',1),1))])]
    mn,mx=min(allvals or [0]),max(allvals or [1]); padl,padr,padt,padb=64,34,24,58; baseline=height-padb; chartw=width-padl-padr; charth=height-padt-padb
    def x_for(l): return padl if len(labels)==1 else padl+labels.index(l)*(chartw/(len(labels)-1))
    def y_for(v): return padt+(mx-v)/(mx-mn)*charth if mx!=mn else (baseline+padt)/2
    money=brl if currency=='BRL' else usd
    defs=['<defs>']; shapes=[]
    for i,p in enumerate(sorted(positions,key=lambda x:x.get('valor',x.get('usd',0)),reverse=True)):
        c=COLORS[i%len(COLORS)]; defs.append(f'<linearGradient id="areaGrad{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{c}" stop-opacity="0.34"/><stop offset="65%" stop-color="{c}" stop-opacity="0.12"/><stop offset="100%" stop-color="{c}" stop-opacity="0.02"/></linearGradient>')
        pts=[(x_for(lab),y_for(v),lab,v) for lab,v in (p.get('precos') or [('Atual',p.get('avg_price_usd') or 0)])]
        line_pts=pts if len(pts)>1 else [(max(padl,pts[0][0]-26),pts[0][1],pts[0][2],pts[0][3]),(min(width-padr,pts[0][0]+26),pts[0][1],pts[0][2],pts[0][3])]
        line_d='M '+' L '.join(f'{x:.1f} {y:.1f}' for x,y,_,_ in line_pts); area_d=line_d+f' L {line_pts[-1][0]:.1f} {baseline:.1f} L {line_pts[0][0]:.1f} {baseline:.1f} Z'
        dots=''.join(f'<a href="{chart_url(p["ticker"],currency)}" target="_blank" rel="noopener noreferrer"><g><circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#f8fafc" fill-opacity=".92"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{c}"/><title>{html.escape(p["ticker"])} compra {html.escape(lab)}: {money(v)}</title></g></a>' for x,y,lab,v in pts)
        lastx,lasty,_,_=pts[-1]
        shapes.append(f'<path d="{area_d}" fill="url(#areaGrad{i})" opacity=".74"/><path d="{line_d}" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" opacity=".95"/>{dots}<a href="{chart_url(p["ticker"],currency)}" target="_blank" rel="noopener noreferrer"><text x="{min(width-padr-8,lastx+9):.1f}" y="{max(padt+12,lasty-9):.1f}" fill="{c}" font-size="11" font-weight="800">{html.escape(p["ticker"])}</text></a>')
    defs.append('</defs>')
    grid=''.join(f'<line x1="{padl+j*(chartw/5):.1f}" y1="{padt}" x2="{padl+j*(chartw/5):.1f}" y2="{baseline}" stroke="#17202d"/>' for j in range(6))
    grid+=''.join(f'<line x1="{padl}" y1="{padt+j*(charth/4):.1f}" x2="{width-padr}" y2="{padt+j*(charth/4):.1f}" stroke="#17202d"/>' for j in range(5))
    xlabels=''.join(f'<text x="{x_for(l):.1f}" y="{height-24}" text-anchor="middle" fill="#718096" font-size="12">{html.escape(l)}</text>' for l in labels)
    return f'<svg class="area-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Evolução de preço com marcações de compra">{"".join(defs)}<rect width="{width}" height="{height}" fill="#080b11"/>{grid}{xlabels}<line x1="{padl}" y1="{baseline}" x2="{width-padr}" y2="{baseline}" stroke="#344255"/>{"".join(shapes)}</svg>'

def custody_panel(positions, currency='BRL'):
    total=sum(p.get('valor',p.get('usd',0)) for p in positions) or 1; money=brl if currency=='BRL' else usd
    rows=[]
    for i,p in enumerate(sorted(positions,key=lambda x:x.get('valor',x.get('usd',0)),reverse=True)):
        val=p.get('valor',p.get('usd',0)); q=p.get('qtd',p.get('quantity',0)); avg=val/q if q else p.get('avg_price_usd',0)
        first=(p.get('precos') or [('Atual',avg)])[0][1]; last=(p.get('precos') or [('Atual',avg)])[-1][1]; var=0 if not first else (last/first-1)*100
        rows.append(f'<div class="v31-row"><span class="v31-dot" style="background:{COLORS[i%len(COLORS)]}"></span><div><b>{ticker_link(p["ticker"],currency)}</b><small>{html.escape(p.get("empresa") or p.get("company") or "")} • {html.escape(p["setor"])}<br>{fmt_num(q)} un. • PM {money(avg)} • {money(val)} • compras {len(p.get("precos",[])) or 1} • var. {pct(var)}</small></div><span class="v31-weight">{pct(100*val/total)}</span></div>')
    return f'<div class="portfolio-v31"><div class="portfolio-v31-title">📈 Custódia + evolução por ação</div><div class="portfolio-v31-sub">Quantidade, preço médio, valor comprado, peso e evolução das compras por nota de corretagem. Os pontos do gráfico marcam cada mês de compra/inclusão.</div><div class="portfolio-v31-grid"><div>{area_chart(positions,currency)}<div class="area-note">Clique nos tickers ou pontos para abrir gráfico em tempo real.</div></div><div class="v31-side">{"".join(rows)}</div></div></div>'

def extract_proventos(html_text):
    m=re.search(r'(<div class="proventos-grid">.*?</div></div>)\s*<footer>', html_text, flags=re.S)
    return m.group(1) if m else ''

def extract_proventos_total(html_text):
    m=re.search(r'<div class="proventos-total">R\$\s*([0-9.,]+)</div>', html_text)
    return float(m.group(1).replace('.','').replace(',','.')) if m else 0.0

def costs_panel(portfolio, global_panel=False):
    by = global_costs() if global_panel else portfolio_costs(portfolio)
    cards=[]
    for broker,b in sorted(by.items(), key=lambda kv:(-(kv[1]['gross_brl']+kv[1]['gross_usd']),kv[0])):
        gross=[]
        if b['gross_brl'] and b['gross_usd']:
            # For BRL/USD conversion entries these are the same capital shown in
            # two currencies, not two separate purchases. Do not render as
            # "R$ X + US$ Y" because that overstates the amount invested.
            gross.append(f'{brl(b["gross_brl"])} → {usd(b["gross_usd"])} após conversão')
        elif b['gross_brl']:
            gross.append(brl(b['gross_brl']))
        elif b['gross_usd']:
            gross.append(usd(b['gross_usd']))
        costs=[]
        if b['known_cost_brl']: costs.append(brl(b['known_cost_brl']))
        if b['known_cost_usd']: costs.append(usd(b['known_cost_usd']))
        detail=[]
        if b['brokerage_brl']: detail.append(f'corretagem {brl(b["brokerage_brl"])}')
        if b['iof_brl']: detail.append(f'IOF {brl(b["iof_brl"])}')
        if b['spread_brl']: detail.append(f'spread {brl(b["spread_brl"])}')
        unk = f'<div class="note warn">{b["unknown"]} nota(s) antiga(s) com custo detalhado não disponível.</div>' if b['unknown'] else '<div class="note ok">Custos conhecidos nas notas conciliadas.</div>'
        ports = ''
        if global_panel and b.get('portfolios'):
            ports=f'<div class="note">Carteiras: {html.escape(", ".join(sorted(x for x in b["portfolios"] if x)))}</div>'
        cards.append(f'<div class="cost-card"><h3>{html.escape(broker)}</h3><div class="cost-row"><span>Compras desde início</span><span class="cost-val">{" + ".join(gross) if gross else "—"}</span></div><div class="cost-row"><span>Custos conhecidos</span><span class="cost-val">{" + ".join(costs) if costs else "R$ 0,00"}</span></div><div class="note">{html.escape("; ".join(detail) if detail else "sem corretagem/spread/IOF conhecido nesta corretora")}</div>{ports}{unk}</div>')
    title = '🧾 Gastos desde o início por corretora' if global_panel else '🧾 Gastos desde o início por corretora nesta carteira'
    sub = 'Inclui compras em custódia, corretagem, emolumentos/taxas conhecidos, spread e IOF quando documentados. Notas antigas sem PDF detalhado ficam marcadas como lacuna, não como custo zero.'
    return f'<div class="panel"><div class="panel-title">{title}</div><div class="note" style="margin-bottom:16px">{sub}</div><div class="cost-grid">{"".join(cards)}</div></div>'

def proventos_panel(portfolio):
    if portfolio == 'BESST & Buffett B3':
        received=9.60; label='B&B B3 / Ágora'; old_future=6.35
    elif portfolio == 'Magic Formula B3':
        received=5.04; label='Magic Formula B3 / XP-Rico'; old_future=7.43
    else:
        received=0.0; label=portfolio; old_future=0.0
    return received, f'''<div class="proventos-grid"><div class="proventos-wrap"><div class="proventos-title">💰 Proventos recebidos</div><div class="proventos-total">{brl(received)}</div><div class="proventos-row"><span>{html.escape(label)} — total recebido no PDF B3 14/08/2025 a 14/08/2026</span><span class="proventos-valor">{brl(received)}</span></div><div class="note">Fonte validada em 17/08/2026: `proventos_recebidos_b3_2025-08-14_a_2026-08-14.csv`. O relatório de movimentação anterior somava R$ 15,89 por incluir outros créditos/reembolsos; este bloco usa apenas proventos recebidos.</div></div><div class="proventos-wrap future"><div class="proventos-title">📅 Proventos futuros / a receber</div><div class="proventos-total">{brl(old_future)}</div><div class="proventos-row"><span>Agenda futura previamente registrada na B3</span><span class="proventos-valor">{brl(old_future)}</span></div><div class="note">Valor futuro preservado da página anterior até novo PDF de eventos a receber; deve ser revisado no próximo pacote mensal.</div></div></div>'''


def render_b3(path, title, subtitle, portfolio, emoji):
    prov_total, prov=proventos_panel(portfolio)
    positions=build_b3_positions(portfolio); total=sum(p['valor'] for p in positions)
    body=f'<header style="text-align:center"><h1>{emoji} {html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p></header>'
    body+=kpis(total,prov_total,positions,'BRL')
    body+=charts(positions,'valor','BRL')
    body+=custody_panel(positions,'BRL')
    body+=costs_panel(portfolio)
    body+=prov
    body+=costs_panel('', global_panel=True)
    body+=f'<footer>🦞 {html.escape(title)} | iaemloop.com.br | Atualizado em {TODAY_BR}</footer>'
    path.write_text(page_shell(title, f'{title}: carteira real IA em Loop atualizada com notas de corretagem, custos e proventos.', body), encoding='utf-8')
    return total, len(positions)

def load_dollar_positions(portfolio_id):
    d=json.loads((DATA/'dollarized_portfolios_2026.json').read_text(encoding='utf-8'))
    p=next(x for x in d['portfolios'] if x['id']==portfolio_id)
    lots_by_ticker=defaultdict(list)
    csv_path=DATA/'compras_stocks_inter_drivewealth_2026.csv'
    if csv_path.exists():
        with csv_path.open(encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('portfolio_id') == portfolio_id:
                    lab=r.get('month','').replace('2026-07','Jul/26').replace('2026-08','Ago/26')
                    lots_by_ticker[r['ticker']].append((lab, float(r['avg_price_usd'])))
    positions=[]
    for pos in p['positions']:
        t=pos['ticker']
        precos=lots_by_ticker.get(t) or [('Atual',float(pos['avg_price_usd']))]
        positions.append({'ticker':t,'empresa':pos.get('company') or COMPANY.get(t,(t,''))[0],'setor':pos.get('sector') or COMPANY.get(t,('', 'Outros'))[1],'qtd':float(pos['quantity']),'valor':float(pos['usd']),'avg_price_usd':float(pos['avg_price_usd']),'precos':precos})
    return p, positions

def monthly_panel_dollar(portfolio_id):
    rows=[]
    with (DATA/'compras_stocks_inter_drivewealth_2026.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['portfolio_id']==portfolio_id:
                rows.append(r)
    by=defaultdict(float)
    for r in rows: by[r['month']] += float(r['executed_value_usd'])
    items=''.join(f'<div class="cost-row"><span>{html.escape(m)}</span><span class="cost-val">{usd(v)}</span></div>' for m,v in sorted(by.items()))
    return f'<div class="panel"><div class="panel-title">📊 Aportes mensais executados</div>{items}<div class="note">Valores em USD das confirmações oficiais Inter/DriveWealth. Agosto ainda sem VET/BRL oficial de remessa no site.</div></div>'

def render_dollar(path, portfolio_id, emoji):
    p,positions=load_dollar_positions(portfolio_id); total=sum(x['valor'] for x in positions)
    dividends_usd=float(p.get('dividends_usd') or 0)
    body=f'<header style="text-align:center"><h1>{emoji} Carteira real {html.escape(p["name"])}</h1><p class="sub">{html.escape(p.get("method") or "Carteira dolarizada")}</p></header>'
    body+=kpis(total,dividends_usd,positions,'USD','Valor comprado em USD')
    body+=charts(positions,'valor','USD')
    body+=custody_panel(positions,'USD')
    body+=monthly_panel_dollar(portfolio_id)
    body+=costs_panel('Dolarizadas / Stocks EUA')
    body+=f'<footer>🦞 Carteira real {html.escape(p["name"])} | iaemloop.com.br | Atualizado em {TODAY_BR}</footer>'
    path.write_text(page_shell(f'Carteira real {p["name"]} | IA em Loop', f'Carteira real dolarizada IA em Loop: {p["name"]}, compras Inter/DriveWealth conciliadas.', body), encoding='utf-8')
    return total,len(positions)

def write_site_summary():
    ledger=load_ledger(); glob=global_costs()
    payload={'schema':'iaemloop-real-portfolio-site-summary-v1','updated_at':TODAY_ISO,'source_files':['data/investment_costs_2026.json','data/dollarized_portfolios_2026.json','data/compras_b3_agosto_2026.csv','data/compras_stocks_inter_drivewealth_2026.csv'],'summary_by_broker':{k:{kk:(sorted(vv) if isinstance(vv,set) else round(vv,2) if isinstance(vv,float) else vv) for kk,vv in v.items()} for k,v in glob.items()},'notes':['Custos antigos sem PDF detalhado aparecem como lacuna, não como custo zero.','MFR$ teve primeira compra em XP com corretagem oficial alta registrada; compras seguintes foram para Rico.','Dolarizadas têm compras em USD e remessas Inter reconciliadas; diferença de US$0.02 em agosto foi fechada como dividendo AAPL confirmado por Diêgo.']}
    (DATA/'real_portfolio_site_summary_2026.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__ == '__main__':
    res={}
    res['besst_b3']=render_b3(ROOT/'carteira_besst_real.html','Carteira BESST','Método Barsi + Buffett','BESST & Buffett B3','💎')
    res['magic_b3']=render_b3(ROOT/'carteira_magic_formula_real.html','Carteira Magic Formula','Método Joel Greenblatt','Magic Formula B3','🎯')
    res['besst_usd']=render_dollar(ROOT/'carteira_besst_buffett_dolarizada_real.html','besst-buffett-stocks','💵')
    res['magic_usd']=render_dollar(ROOT/'carteira_magic_formula_dolarizada_real.html','magic-formula-stocks','🌎')
    write_site_summary()
    print(json.dumps(res,ensure_ascii=False,indent=2))
