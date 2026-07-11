#!/usr/bin/env python3
"""
Teste rápido do pipeline base EUA com poucos tickers.
"""
import sys
sys.path.insert(0, '.')
from pipeline_stocks_eua_base import fetch_stock_data, main

# Sobrepor a função get_sp500_tickers para retornar lista pequena
import pipeline_stocks_eua_base as mod
original_get = mod.get_sp500_tickers
mod.get_sp500_tickers = lambda: ['AAPL', 'MSFT', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

if __name__ == '__main__':
    print("🧪 Teste rápido do pipeline base EUA (5 tickers)")
    mod.main()
    # Restaurar
    mod.get_sp500_tickers = original_get