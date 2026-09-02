#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np

tickers = ['BBAS3', 'KLBN3', 'VALE3']
print("Testando pipeline mínima...")

dados = []
for t in tickers:
    try:
        stock = yf.Ticker(f'{t}.SA')
        info = stock.info
        if not info or 'regularMarketPrice' not in info:
            print(f"⚠️ {t}: sem dados")
            continue
        dividend_yield = info.get('dividendYield', 0) or 0
        p_vpa = info.get('priceToBook', np.nan) or np.nan
        print(f"✅ {t}: preço={info.get('regularMarketPrice')}, DY={dividend_yield*100:.2f}%, P/VPA={p_vpa:.2f}")
        dados.append({
            'ticker': t,
            'preco': info.get('regularMarketPrice'),
            'dividend_yield': dividend_yield,
            'p_vpa': p_vpa
        })
    except Exception as e:
        print(f"❌ {t}: erro {e}")

df = pd.DataFrame(dados)
print("\nResultado:")
print(df.to_string(index=False))