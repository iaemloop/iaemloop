#!/usr/bin/env python3
"""
Pipeline base para coleta e normalização de fundamentais de ações EUA (S&P 500).
Gera CSV mensal com indicadores usados pelos rankings BESST & Buffett e Magic Formula.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import time
import json

warnings.filterwarnings('ignore')

# ==================== CONFIGURAÇÕES ====================
# Universo: tentar buscar S&P 500 da Wikipedia; se falhar, usar lista fallback de grandes caps.
FALLBACK_TICKERS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'META', 'TSLA', 'NVDA', 'BRK.B', 'BRK.A',
    'UNH', 'JNJ', 'V', 'PG', 'HD', 'MA', 'DIS', 'PYPL', 'BAC', 'ADBE', 'CMCSA', 'NFLX',
    'XOM', 'CVX', 'ABT', 'KO', 'PFE', 'TMO', 'COST', 'DHR', 'VZ', 'NEE', 'INTC', 'CSCO',
    'AVGO', 'TXN', 'QCOM', 'HON', 'UNP', 'LOW', 'UPS', 'RTX', 'PM', 'SBUX', 'LMT',
    'AMGN', 'CAT', 'GS', 'AXP', 'BLK', 'T', 'BMY', 'AMT', 'DE', 'ELV', 'MDT', 'ISRG',
    'ZTS', 'ADI', 'MMC', 'SPGI', 'ICE', 'GD', 'LRCX', 'ADP', 'GILD', 'SYK', 'CB',
    'REGN', 'VRTX', 'ISRG', 'MDLZ', 'CI', 'EQIX', 'PGR', 'SO', 'APH', 'MU', 'FTNT',
    'ADSK', 'CSX', 'ORCL', 'IBM', 'INTU', 'SNPS', 'WM', 'CL', 'ECL', 'APD', 'EIX',
    'ED', 'PEG', 'EXC', 'ES', 'AWK', 'CMS', 'ED', 'DTE', 'AEE', 'PEG', 'EIX', 'ETR'
]

# ==================== FUNÇÕES ====================

def get_sp500_tickers():
    """Busca a lista de tickers do S&P 500 da Wikipedia."""
    try:
        # Tabela contendo os componentes do S&P 500
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        df = tables[0]  # primeira tabela
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()  # yfinance usa '-' ao invés de '.' para algumas classes
        return tickers
    except Exception as e:
        print(f"⚠️ Falha ao buscar S&P 500 da Wikipedia: {e}")
        print("Usando lista fallback de tickers.")
        return FALLBACK_TICKERS

def fetch_stock_data(ticker):
    """Busca dados fundamentais via yfinance para um ticker EUA."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or 'regularMarketPrice' not in info:
            return None

        preco = info.get('regularMarketPrice', np.nan)
        market_cap = info.get('marketCap', np.nan)
        enterprise_value = info.get('enterpriseValue', np.nan)
        # Lucro e dividendos
        net_income = info.get('netIncomeToCommon', np.nan)
        eps = info.get('trailingEps', np.nan)
        dividend_rate = info.get('dividendRate', np.nan)
        dividend_yield_raw = info.get('dividendYield', np.nan)
        # Dividend yield calculado
        if pd.notnull(preco) and pd.notnull(dividend_rate) and preco > 0:
            dividend_yield = dividend_rate / preco
        elif pd.notnull(dividend_yield_raw):
            dividend_yield = dividend_yield_raw / 100 if dividend_yield_raw > 1 else dividend_yield_raw
        else:
            dividend_yield = np.nan
        # P/L e P/VP
        pe = info.get('trailingPE', np.nan)
        pe_forward = info.get('forwardPE', np.nan)
        pb = info.get('priceToBook', np.nan)
        # EV/EBITDA e EV/EBIT
        ebitda = info.get('ebitda', np.nan)
        ebit = info.get('ebit', np.nan)  # pode estar ausente
        ev_ebitda = enterprise_value / ebitda if pd.notnull(enterprise_value) and pd.notnull(ebitda) and ebitda != 0 else np.nan
        ev_ebit = enterprise_value / ebit if pd.notnull(enterprise_value) and pd.notnull(ebit) and ebit != 0 else np.nan
        # ROE e ROA
        roe = info.get('returnOnEquity', np.nan)
        roa = info.get('returnOnAssets', np.nan)
        # Debt/Equity
        total_debt = info.get('totalDebt', np.nan)
        total_equity = info.get('totalStockholderEquity', np.nan)
        debt_equity = total_debt / total_equity if pd.notnull(total_debt) and pd.notnull(total_equity) and total_equity != 0 else np.nan
        # Book value
        book_value = info.get('bookValue', np.nan)
        # Setor e industria
        sector = info.get('sector', '')
        industry = info.get('industry', '')

        return {
            'ticker': ticker,
            'empresa': info.get('shortName', ticker),
            'setor': sector,
            'industria': industry,
            'preco': preco,
            'market_cap': market_cap,
            'enterprise_value': enterprise_value,
            'net_income': net_income,
            'eps': eps,
            'dividend_yield': dividend_yield,
            'dividend_rate': dividend_rate,
            'pe': pe,
            'pe_forward': pe_forward,
            'pb': pb,
            'ev_ebitda': ev_ebitda,
            'ev_ebit': ev_ebit,
            'roe': roe,
            'roa': roa,
            'debt_equity': debt_equity,
            'book_value': book_value,
            'fonte_dados': 'yfinance',
            'data_base': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"❌ Erro ao processar {ticker}: {e}")
        return None

def main():
    print("🔍 Pipeline Base: Coleta de Fundamentais EUA (S&P 500)")
    os.makedirs('outputs', exist_ok=True)
    os.makedirs('data', exist_ok=True)

    tickers = get_sp500_tickers()
    print(f"📊 Universo: {len(tickers)} tickers (S&P 500)")

    dados = []
    for i, ticker in enumerate(tickers, 1):
        d = fetch_stock_data(ticker)
        if d:
            dados.append(d)
            # Log a cada 50 para não poluir muito
            if i % 50 == 0 or i == len(tickers):
                print(f"[{i}/{len(tickers)}] Processados {i} tickers, últimos ok: {d['ticker']} (DY={d['dividend_yield']*100 if pd.notnull(d['dividend_yield']) else 0:.1f}%)")
        else:
            if i % 50 == 0:
                print(f"[{i}/{len(tickers)}] {ticker} sem dados")
        time.sleep(0.2)  # rate limit suave

    if not dados:
        print("❌ Nenhum dado obtido!")
        return

    df = pd.DataFrame(dados)
    print(f"✅ Dados coletados: {len(df)} tickers")

    # Salvar CSV mensal (com data-base)
    ts = datetime.now().strftime('%Y-%m')
    csv_path = f'outputs/stocks_eua_fundamentos_{ts}.csv'
    df_out = df.copy()
    # Formatar percentuais
    for col in ['dividend_yield', 'roe', 'roa']:
        if col in df_out.columns:
            df_out[col] = (df_out[col] * 100).round(2)
    df_out.to_csv(csv_path, index=False, encoding='utf-8-sig')
    # Também salvar latest (cópia)
    df_out.to_csv('outputs/stocks_eua_fundamentos_latest.csv', index=False, encoding='utf-8-sig')
    print(f"💾 CSV salvo: {csv_path}")
    print(f"💾 Latest CSV: outputs/stocks_eua_fundamentos_latest.csv")

    # Salvar JSON para possível uso no site (opcional)
    json_data = {
        "meta": {
            "updated_at": datetime.now().isoformat(),
            "total_assets": len(df_out),
            "universe": "S&P 500 (via Wikipedia) ou fallback"
        },
        "assets": df_out.to_dict(orient='records')
    }
    json_path = 'outputs/stocks_eua_fundamentos_latest.json'
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(json_data, jf, ensure_ascii=False, indent=2)
    print(f"💾 JSON: {json_path}")

if __name__ == '__main__':
    main()