#!/usr/bin/env python3
"""
Pipeline BESST & Buffett EUA: calcula score baseado em qualidade, dividendos,
payout e alavancagem, selecionando top 20.
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
import time

def compute_besst_score(row):
    """
    Calcula score composto (0-100) baseado em:
    - ROE (peso 0.4)
    - Dividend Yield (peso 0.3)
    - Payout ratio (peso 0.2) - inverso (quanto menor, melhor)
    - Debt/Equity (peso 0.1) - inverso
    Valores ausentes recebem 0 para aquele componente.
    """
    score = 0.0
    # ROE (em %)
    roe = row.get('roe')
    if pd.notnull(roe):
        # Normalizar: assume ROE típico 0-50%; clip 0-50, then /50*40
        roe_clipped = min(max(roe, 0), 50)
        score += (roe_clipped / 50) * 40
    # Dividend Yield (em %)
    dy = row.get('dividend_yield')
    if pd.notnull(dy):
        # Normalizar: DY típico 0-10%; clip 0-10, then /10*30
        dy_clipped = min(max(dy, 0), 10)
        score += (dy_clipped / 10) * 30
    # Payout ratio: dividend_rate / eps
    eps = row.get('eps')
    div_rate = row.get('dividend_rate')
    payout = None
    if pd.notnull(eps) and eps != 0 and pd.notnull(div_rate):
        payout = div_rate / eps
    if payout is not None:
        # Queremos payout baixo (0-1 ideal). Mapear: payout>1 -> 0, payout<0 ->0 (não deveria acontecer)
        payout_clipped = min(max(payout, 0), 1)  # 0 a 1
        score += (1 - payout_clipped) * 20  # invertido
    # Debt/Equity
    de = row.get('debt_equity')
    if pd.notnull(de) and de >= 0:
        # Mapear: de=0 -> 1, de->inf -> 0; usar 1/(1+de)
        de_score = 1 / (1 + de)
        score += de_score * 10
    return score

def main():
    print("🔍 Pipeline BESST & Buffett EUA")
    base_csv = 'outputs/stocks_eua_fundamentos_latest.csv'
    if not os.path.exists(base_csv):
        print(f"❌ Arquivo base não encontrado: {base_csv}. Execute o pipeline base primeiro.")
        return
    df = pd.read_csv(base_csv)
    print(f"📊 Lidos {len(df)} registros do base.")
    # Calcular score
    df['score_besst'] = df.apply(compute_besst_score, axis=1)
    # Ordenar por score desc
    df_sorted = df.sort_values('score_besst', ascending=False)
    top20 = df_sorted.head(20).copy().reset_index(drop=True)
    print(f"🏆 Top 20 BESST & Buffett EUA:")
    print(top20[['ticker', 'empresa', 'setor', 'roe', 'dividend_yield', 'score_besst']].to_string(index=False))
    # Preparar saída
    ts = datetime.now().strftime('%Y-%m')
    out_csv = f'outputs/besst_buffett_eua_top20_{ts}.csv'
    # Selecionar e renomear colunas conforme especificação do handoff
    out = pd.DataFrame()
    out['rank'] = range(1, len(top20) + 1)
    out['ticker'] = top20['ticker']
    out['empresa'] = top20['empresa']
    out['setor'] = top20['setor']
    out['industria'] = top20['industria']
    out['pl'] = top20['pe']
    out['ev_ebitda'] = top20['ev_ebitda']
    out['roe_pct'] = top20['roe']
    out['margem_operacional_pct'] = np.nan  # não temos no base; colocar vazio
    out['fcf_yield_pct'] = np.nan
    out['dividend_yield_pct'] = top20['dividend_yield']
    out['score_qualidade'] = np.nan  # placeholder
    out['score_perenidade'] = np.nan
    out['score_seguranca'] = np.nan
    out['score_valuation'] = np.nan
    out['score_total'] = top20['score_besst']
    out['fonte_dados'] = 'yfinance'
    out['data_base'] = top20['data_base']
    out['observacoes'] = ''
    # Salvar CSV
    out.to_csv(out_csv, index=False, encoding='utf-8-sig')
    out.to_csv('outputs/besst_buffett_eua_latest.csv', index=False, encoding='utf-8-sig')
    print(f"💾 CSV salvo: {out_csv}")
    print(f"💾 Latest CSV: outputs/besst_buffett_eua_latest.csv")
    # Opcional: gerar JSON similar ao base
    import json
    json_data = {
        "meta": {
            "updated_at": datetime.now().isoformat(),
            "total_assets": len(out),
            "methodology": "BESST & Buffett composite score"
        },
        "assets": out.to_dict(orient='records')
    }
    with open('outputs/besst_buffett_eua_latest.json', 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("💾 JSON salvo: outputs/besst_buffett_eua_latest.json")

if __name__ == '__main__':
    main()
