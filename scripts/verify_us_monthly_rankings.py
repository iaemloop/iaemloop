#!/usr/bin/env python3
"""Verify local or deployed monthly US rankings against dated source snapshots."""
import argparse
import csv
import io
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path
from publish_us_monthly_rankings import ROOT, TABS, load_snapshot, signature, table_rows


def verify(month, base_url=None):
    def read(name):
        if base_url:
            url = base_url.rstrip('/') + '/' + name + '?verify=' + month
            # Homebrew Python may not have a CA bundle configured on macOS.
            cafile = '/etc/ssl/cert.pem' if sys.platform == 'darwin' and Path('/etc/ssl/cert.pem').is_file() else None
            with urllib.request.urlopen(url, timeout=30, context=ssl.create_default_context(cafile=cafile)) as response:
                return response.read().decode('utf-8-sig')
        return (ROOT / name).read_text(encoding='utf-8-sig')

    tab = TABS[int(month[5:7]) - 1]
    for kind, current, history in [
        ('besst_buffett_eua', 'ranking_besst_buffett_dolarizado.html', 'historico_rankings_dolarizados.html'),
        ('magic_formula_eua', 'ranking_magic_formula_dolarizada.html', 'historico_rankings_magic_formula_dolarizada.html')]:
        expected = signature(table_rows(load_snapshot(kind, month), kind.startswith('magic')))
        landing = re.search(r'<tbody>(.*?)</tbody>', read(current), re.S)
        assert landing and signature(landing[1]) == expected, f'{current}: divergência com snapshot'
        blocks = {m[1]: m[2] for m in re.finditer(r'<div id="([^"]+)" class="tab-content[^\"]*".*?<tbody>(.*?)</tbody>', read(history), re.S)}
        assert tab in blocks and signature(blocks[tab]) == expected, f'{history}: mês ausente/divergente'
        assert all(signature(body) != expected for key, body in blocks.items() if key != tab), f'{history}: mês duplicado'
        tickers = [row[0] for row in expected]
        latest = list(csv.DictReader(io.StringIO(read(f'outputs/{kind}_latest.csv'))))
        data = json.loads(read(f'outputs/{kind}_latest.json'))
        assert [r['ticker'] for r in latest] == tickers == [r['ticker'] for r in data['assets']]
        assert all(row['data_base'].startswith(month) for row in latest)
        assert data['meta']['total_assets'] == len(tickers)
        print(f'OK {kind}: {len(tickers)} empresas, mês {month}, histórico e latest coerentes')
    print('US_MONTHLY_RANKINGS_OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--month', required=True)
    parser.add_argument('--base-url')
    args = parser.parse_args()
    verify(args.month, args.base_url)
