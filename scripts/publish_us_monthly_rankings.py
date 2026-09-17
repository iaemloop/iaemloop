#!/usr/bin/env python3
"""Update US ranking tables from dated snapshots, preserving layout and history."""
import argparse
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
TABS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
SECTORS = {'Healthcare': 'Saúde', 'Financial Services': 'Serviços financeiros',
           'Real Estate': 'Imóveis/REITs', 'Technology': 'Tecnologia',
           'Industrials': 'Industriais', 'Consumer Cyclical': 'Consumo cíclico',
           'Consumer Defensive': 'Consumo defensivo', 'Energy': 'Energia',
           'Utilities': 'Serviços públicos', 'Basic Materials': 'Materiais básicos',
           'Communication Services': 'Comunicação'}

INDUSTRIES = {'Agricultural Inputs': 'Insumos agrícolas',
 'Apparel Retail': 'Varejo de vestuário',
 'Asset Management': 'Gestão de ativos',
 'Building Products & Equipment': 'Produtos e equipamentos para construção',
 'Computer Hardware': 'Hardware de computadores',
 'Conglomerates': 'Conglomerados',
 'Consumer Electronics': 'Eletrônicos de consumo',
 'Drug Manufacturers - General': 'Farmacêuticas — geral',
 'Drug Manufacturers - Specialty & Generic': 'Farmacêuticas — especialidades e genéricos',
 'Electronic Components': 'Componentes eletrônicos',
 'Engineering & Construction': 'Engenharia e construção',
 'Footwear & Accessories': 'Calçados e acessórios',
 'Information Technology Services': 'Serviços de tecnologia da informação',
 'Insurance - Property & Casualty': 'Seguros patrimoniais e acidentes',
 'Internet Content & Information': 'Conteúdo e informação na internet',
 'Leisure': 'Lazer',
 'Medical Distribution': 'Distribuição médica',
 'Medical Instruments & Supplies': 'Instrumentos e suprimentos médicos',
 'REIT - Retail': 'REITs de varejo',
 'Resorts & Casinos': 'Resorts e cassinos',
 'Semiconductors': 'Semicondutores',
 'Software - Application': 'Software de aplicação',
 'Software - Infrastructure': 'Software de infraestrutura',
 'Specialty Industrial Machinery': 'Máquinas industriais especializadas',
 'Telecom Services': 'Serviços de telecomunicações',
 'Travel Services': 'Serviços de viagem'}

def load_snapshot(kind, month):
    path = ROOT / 'outputs' / f'{kind}_top20_{month}.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        raw = list(csv.DictReader(stream))
    if not raw or any(not row.get('data_base', '').startswith(month) for row in raw):
        raise ValueError(f'Snapshot sem data-base válida para {month}: {path}')
    rows, seen = [], set()
    for row in raw:
        # The two Alphabet share classes represent the same company.
        company = 'Alphabet' if row['ticker'] in {'GOOG', 'GOOGL'} else row['empresa']
        if company in seen:
            continue
        seen.add(company)
        row = dict(row, rank=str(len(rows) + 1))
        rows.append(row)
    if not 1 <= len(rows) <= 20:
        raise ValueError('O ranking deve conter até 20 empresas distintas.')
    return rows


def table_rows(rows, magic):
    metrics = [('pl', ''), ('ev_ebitda', '')]
    metrics += ([('roic_proxy_pct', '%'), ('earnings_yield_pct', '%'),
                 ('fcf_yield_pct', '%'), ('score_total', '')] if magic else
                [('roe_pct', '%'), ('dividend_yield_pct', '%'), ('score_total', '')])
    body = []
    for i, row in enumerate(rows, 1):
        cells = []
        for key, suffix in metrics:
            try:
                number = float(row[key])
                value = f'{number:.3f}' if magic and key == 'score_total' else f'{number:.1f}'
                cells.append(value + suffix)
            except (ValueError, KeyError):
                cells.append('-')
        sector = INDUSTRIES.get(row.get('industria'), SECTORS.get(row.get('setor'), row.get('setor', '-')))
        body.append(f"<tr><td class='rank'>{i}</td><td class='ticker'>{html.escape(row['ticker'])}</td>"
                    f"<td>{html.escape(row['empresa'])}</td><td>{html.escape(sector)}</td>" +
                    ''.join(f'<td>{value}</td>' for value in cells) + '</tr>')
    return '\n'.join(body)


def signature(body):
    """Compare tickers and metrics independently of sector translations/layout."""
    result = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', body, re.S):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(cells) >= 5:
            result.append(tuple(re.sub(r'<[^>]+>|\s+', '', cell) for cell in [cells[1], *cells[4:]]))
    return result


def publish(month):
    year, mm = month.split('-')
    index = int(mm) - 1
    tab, label = TABS[index], f'{MONTHS[index]}/{year}'
    pending = {}
    for kind, current, history in [
        ('besst_buffett_eua', 'ranking_besst_buffett_dolarizado.html', 'historico_rankings_dolarizados.html'),
        ('magic_formula_eua', 'ranking_magic_formula_dolarizada.html', 'historico_rankings_magic_formula_dolarizada.html')]:
        rows = load_snapshot(kind, month)
        body = table_rows(rows, kind.startswith('magic'))
        source = (ROOT / current).read_text()
        head = re.search(r'<thead>.*?</thead>', source, re.S).group()
        source, count = re.subn(r'<tbody>.*?</tbody>', '<tbody>\n' + body + '\n</tbody>', source, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f'Tabela ausente: {current}')
        source = re.sub(r'data-mes="[^"]+"', f'data-mes="{label}"', source)
        dated = max(row['data_base'] for row in rows)
        date_br = '/'.join(reversed(dated.split('-')))
        source = re.sub(r'(Atualização:</strong> )[^<]+', r'\g<1>' + date_br + ' — ' + label, source)
        history_source = (ROOT / history).read_text()
        current_signature = signature(body)
        for previous in re.finditer(r'<div id="([^"]+)" class="tab-content[^\"]*".*?<tbody>(.*?)</tbody>', history_source, re.S):
            if previous[1] != tab and signature(previous[2]) == current_signature:
                raise ValueError(f'{history}: tabela idêntica a {previous[1]}; conferir a origem.')
        pattern = rf'(<div id="{tab}" class="tab-content[^\"]*"[^>]*>.*?<tbody>).*?(</tbody>)'
        history_source, count = re.subn(pattern, lambda match: match[1] + '\n' + body + '\n' + match[2], history_source, count=1, flags=re.S)
        if count != 1:
            history_source = history_source.replace('class="tab active"', 'class="tab"').replace('class="tab-content active"', 'class="tab-content"')
            history_source = history_source.replace('<div class="tabs">', f'<div class="tabs"><button class="tab active" onclick="switchTab(\'{tab}\')">{label}</button>', 1)
            anchor = re.search(r'<div id="[^"]+" class="tab-content', history_source)
            if not anchor:
                raise ValueError(f'Histórico ausente: {history}')
            entry = f'<div id="{tab}" class="tab-content active"><div class="table-wrap"><table>{head}<tbody>{body}</tbody></table></div></div>'
            history_source = history_source[:anchor.start()] + entry + history_source[anchor.start():]
        pending[current] = source
        pending[history] = history_source
        assets = []
        for row in rows:
            asset = dict(row)
            for key in ['rank', 'pl', 'ev_ebitda', 'roe_pct', 'dividend_yield_pct',
                        'roic_proxy_pct', 'earnings_yield_pct', 'fcf_yield_pct', 'score_total']:
                if key in asset:
                    asset[key] = float(asset[key]) if asset[key] else None
            assets.append(asset)
        pending[f'outputs/{kind}_latest.json'] = json.dumps({'meta': {'month': month, 'data_base': dated, 'updated_at': dated, 'total_assets': len(rows)}, 'assets': assets}, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        import io
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        pending[f'outputs/{kind}_latest.csv'] = stream.getvalue()
        print(f'{kind}: {len(rows)} empresas; data-base {dated}')
    for name, content in pending.items():
        (ROOT / name).write_text(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--month', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', args.month):
        parser.error('--month deve ter formato YYYY-MM')
    publish(args.month)
