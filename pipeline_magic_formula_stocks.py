#!/usr/bin/env python3
"""
Pipeline Magic Formula EUA (versão simplificada).
Ranking baseado em Earnings Yield e ROE (como proxy para ROIC).
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

def compute_magic_formula(df):
    """
    Espera dataframe com colunas: 'pe', 'roe', 'ticker', 'empresa', etc.
    Retorna df com colunas adicionais: 'ey', 'rank_ey', 'rank_roe', 'rank_sum'.
    """
    df = df.copy()
    # Earnings Yield = 1 / PE (se PE > 0)
    df['ey'] = np.where(df['pe'] > 0, 1 / df['pe'], np.nan)
    # ROE já está em decimal (ex: 0.15 para 15%)
    # Filtrar apenas linhas com ambos os indicadores válidos
    mask = df['ey'].notna() & df['roe'].notna()
    df_filtered = df[mask].copy()
    if df_filtered.empty:
        return df_filtered
    # Ranking: maior EY -> melhor (rank 1), maior ROE -> melhor
    df_filtered['rank_ey'] = df_filtered['ey'].rank(ascending=False, method='min')
    df_filtered['rank_oe'] = df_filtered['roe'].rank(ascending=False, method='min')
    # Fix: column name should be 'rank_roe'
    df_filtered['rank_roe'] = df_filtered['roe'].rank(ascending=False, method='min')
    df_filtered['rank_sum'] = df_filtered['rank_ey'] + df_filtered['rank_roe']
    # Ordenar por soma de ranks (menor é melhor)
    df_sorted = df_filtered.sort_values('rank_sum', ascending=True)
    return df_sorted

def main():
    print("🔍 Pipeline Magic Formula EUA")
    base_csv = 'outputs/stocks_eua_fundamentos_latest.csv'
    if not os.path.exists(base_csv):
        print(f"❌ Arquivo base não encontrado: {base_csv}. Execute o pipeline base primeiro.")
        return
    df = pd.read_csv(base_csv)
    print(f"📊 Lidos {len(df)} registros do base.")
    ranked = compute_magic_formula(df)
    if ranked.empty:
        print("⚠️ Nenhum dado com EY e ROE válidos.")
        return
    top20 = ranked.head(20).copy()
    print(f"🏆 Top 20 Magic Formula EUA (menor soma de ranks = melhor):")
    print(top20[['ticker', 'empresa', 'setor', 'ey', 'roe', 'rank_ey', 'rank_roe', 'rank_sum']].to_string(index=False))
    # Preparar saída conforme especificação do handoff
    ts = datetime.now().strftime('%Y-%m')
    out_csv = f'outputs/magic_formula_eua_top20_{ts}.csv'
    out = pd.DataFrame()
    out['rank'] = range(1, len(top20) + 1)
    out['ticker'] = top20['ticker']
    out['empresa'] = top20['empresa']
    out['setor'] = top20['setor']
    out['industria'] = top20.get('industria', '')
    out['pl'] = top20['pe']
    out['ev_ebitda'] = np.nan  # não temos no cálculo direto
    out['roic_proxy_pct'] = top20['roe'] * 100  # converter para percentual
    out['earnings_yield_pct'] = top20['ey'] * 100
    out['ebitda_yield_pct'] = np.nan
    out['fcf_yield_pct'] = np.nan
    out['rank_qualidade'] = top20['rank_roe']  # qualidade = ROE
    out['rank_preco'] = top20['rank_ey']       # preço = EY (inverso do PE)
    out['rank_fcf'] = np.nan
    out['score_total'] = 1 / (top20['rank_sum'] + 1e-9)  # inverso para score maior = melhor
    out['fonte_dados'] = 'yfinance'
    out['data_base'] = datetime.now().strftime('%Y-%m-%d')
    out['observacoes'] = ''
    out.to_csv(out_csv, index=False, encoding='utf-8-sig')
    out.to_csv('outputs/magic_formula_eua_latest.csv', index=False, encoding='utf-8-sig')
    print(f"💾 CSV salvo: {out_csv}")
    print(f"💾 Latest CSV: outputs/magic_formula_eua_latest.csv")
    # JSON opcional
    import json
    json_data = {
        "meta": {
            "updated_at": datetime.now().isoformat(),
            "total_assets": len(out),
            "methodology": "Magic Formula (EY + ROE)"
        },
        "assets": out.to_dict(orient='records')
    }
    with open('outputs/magic_formula_eua_latest.json', 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("💾 JSON salvo: outputs/magic_formula_eua_latest.json")

if __name__ == '__main__':
    main()