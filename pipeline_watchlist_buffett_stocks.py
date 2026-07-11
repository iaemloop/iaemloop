#!/usr/bin/env python3
"""
Pipeline Watchlist Buffett Permanente EUA.
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime

def main():
    print("🔍 Pipeline Watchlist Buffett Permanente EUA")
    base_csv = 'outputs/stocks_eua_fundamentos_latest.csv'
    if not os.path.exists(base_csv):
        print(f"❌ Arquivo base não encontrado: {base_csv}. Execute o pipeline base primeiro.")
        return
    df = pd.read_csv(base_csv)
    print(f"📊 Lidos {len(df)} registros do base.")

    # Carregar watchlist (simples)
    wl_csv = 'data/watchlist_buffett_permanente_eua.csv'
    if not os.path.exists(wl_csv):
        print(f"❌ Arquivo de watchlist não encontrado: {wl_csv}")
        return
    wl_df = pd.read_csv(wl_csv)
    tickers_wl = set(wl_df['ticker'].str.upper().tolist())
    print(f"📋 Watchlist contém {len(tickers_wl)} tickers.")

    # Filtrar base
    df_wl = df[df['ticker'].str.upper().isin(tickers_wl)].copy()
    if df_wl.empty:
        print("⚠️ Nenhum ticker da watchlist encontrado na base.")
        return
    print(f"🎯 {len(df_wl)} tickers da watchlist encontrados na base.")

    # Garantir colunas necessárias
    for col in ['roe', 'dividend_yield']:
        if col not in df_wl.columns:
            df_wl[col] = np.nan

    # O pipeline base salva roe/dividend_yield ja em pontos percentuais.
    df_wl['roe_pct'] = df_wl['roe']
    df_wl['dividend_yield_pct'] = df_wl['dividend_yield']

    # Preparar CSV de saída
    ts = datetime.now().strftime('%Y-%m')
    out_csv = f'outputs/watchlist_buffett_permanente_eua_{ts}.csv'
    out_cols = ['ticker', 'empresa', 'setor', 'industria', 'roe_pct', 'dividend_yield_pct', 'observacoes']
    for col in out_cols:
        if col not in df_wl.columns:
            if col == 'observacoes':
                df_wl[col] = ''
            else:
                df_wl[col] = np.nan
    out_df = df_wl[out_cols].copy()
    out_csv_latest = 'outputs/watchlist_buffett_permanente_eua_latest.csv'
    out_df.to_csv(out_csv, index=False, encoding='utf-8-sig')
    out_df.to_csv(out_csv_latest, index=False, encoding='utf-8-sig')
    print(f"💾 CSV salvo: {out_csv}")
    print(f"💾 Latest CSV: {out_csv_latest}")

    # Gerar HTML simples
    html_file = 'metodologia_watchlist_eua.html'
    hoje = datetime.now().strftime('%d/%m/%Y')
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Watchlist Buffett Permanente EUA</title>
    <style>
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #19364D; color: white; }}
    </style>
</head>
<body>
    <h1>Watchlist Buffett Permanente EUA</h1>
    <p>📅 <strong>Atualização:</strong> {hoje}</p>
    <p>Atualizado: {hoje}</p>
    <h2>Lista de observação</h2>
    <table>
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Empresa</th>
                <th>Setor</th>
                <th>Indústria</th>
                <th>ROE (%)</th>
                <th>Dividend Yield (%)</th>
                <th>Observações</th>
            </tr>
        </thead>
        <tbody>
'''
    for _, row in df_wl.iterrows():
        ticker = row['ticker']
        empresa = row.get('empresa', '')
        setor = row.get('setor', '')
        industria = row.get('industria', '')
        roe_val = row.get('roe_pct')
        dy_val = row.get('dividend_yield_pct')
        roe_str = f"{roe_val:.2f}" if pd.notnull(roe_val) else '-'
        dy_str = f"{dy_val:.2f}" if pd.notnull(dy_val) else '-'
        obs = row.get('observacoes', '')
        html += f'            <tr>\n                <td>{ticker}</td>\n                <td>{empresa}</td>\n                <td>{setor}</td>\n                <td>{industria}</td>\n                <td>{roe_str}</td>\n                <td>{dy_str}</td>\n                <td>{obs}</td>\n            </tr>\n'
    html += '''        </tbody>
    </table>
</body>
</html>'''
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"📄 HTML gerado: {html_file}")

if __name__ == '__main__':
    main()
