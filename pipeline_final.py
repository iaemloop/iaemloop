#!/usr/bin/env python3
"""
Pipeline Barsi Screener - Versão funcional com yfinance
Filtra ações da B3 baseando-se em dividendos e valuation.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import time

warnings.filterwarnings('ignore')

# ==================== CONFIGURAÇÕES ====================
MIN_DIVIDEND_YIELD = 0.03      # 3% ao ano
MAX_PVPA = 2.0                # P/VPA máximo
MIN_HISTORY_YEARS = 5         # Tempo mínimo listed
MIN_MARKET_CAP = 1e9          # R$ 1 bilhão
MIN_DIVIDEND_HISTORY = 3      # Mínimo 3 anos de dividendos

# Setores PERENES (lista de tickers)
PERENEN_SETORES = {
    'BANCOS': ['BBAS3', 'ITUB4', 'BBDC4', 'SANB11', 'BPAC11'],
    'PAPEL_CELULOSE': ['KLBN3', 'KLBN4', 'SUZB3'],
    'ENERGIA': ['ELET3', 'ELET5', 'ELET6', 'EQTL3', 'ENGI3', 'ENGI11', 'CPFE3', 'ENBR3'],
    'SANEAMENTO': ['SBSP3', 'CSMG3'],
    'TELECOM': ['VIVT3', 'TIMB3', 'TOTS3'],
    'MINERACAO': ['VALE3', 'GGBR4', 'CSNA3', 'USIM5'],
    'QUIMICA_PETROLEO': ['PETR3', 'PETR4', 'UNIP3', 'UNIP6', 'PRIO3'],
    'SEGUROS': ['PSSA3', 'SULA11', 'IRBR3']
}

# Setores a evitar
EVITAR_SETORES = {
    'VAREJO': ['MGLU3', 'VIIA3', 'LREN3'],
    'AEREAS': ['GOLL4', 'AZUL4'],
    'TURISMO': ['LOGG3'],
    'SAUDE': ['HAPV3', 'QUAL3', 'RADL3'],
    'TRANSPORTES': ['RAIL3', 'LOGN3'],
    'CONSTRUCAO': ['MRVE3', 'TEND3', 'CYRE3']
}

def get_tickers_perenes():
    """Retorna lista de tickers apenas dos setores perenes."""
    tickers = []
    for setor, lista in PERENEN_SETORES.items():
        tickers.extend(lista)
    # Remover duplicados
    return sorted(set(tickers))

def add_suffix(ticker):
    if not ticker.endswith('.SA'):
        return f'{ticker}.SA'
    return ticker

def buscar_dados_yfinance(ticker):
    """Busca dados via yfinance."""
    try:
        stock = yf.Ticker(add_suffix(ticker))
        info = stock.info

        if not info or 'regularMarketPrice' not in info:
            return None

        preco = info.get('regularMarketPrice', np.nan)
        dividend_rate = info.get('dividendRate', np.nan)
        dividend_yield_raw = info.get('dividendYield', np.nan)

        # Calcular dividend yield de forma confiável
        if pd.notnull(preco) and pd.notnull(dividend_rate) and preco > 0:
            dividend_yield = dividend_rate / preco
        elif pd.notnull(dividend_yield_raw):
            dividend_yield = dividend_yield_raw / 100 if dividend_yield_raw > 1 else dividend_yield_raw
        else:
            dividend_yield = np.nan

        # Histórico de dividendos (anos)
        dividends = stock.dividends
        anos_com_dividendos = 0
        if isinstance(dividends, pd.Series) and len(dividends) > 0:
            try:
                anos_com_dividendos = len(dividends.index.to_period('Y').unique())
            except:
                try:
                    anos_com_dividendos = len(dividends.resample('YE').sum())
                except:
                    anos_com_dividendos = 0

        # Data de listamento (aproximada se não houver)
        data_inicio = info.get('firstTradeDateEpochUtils')
        if data_inicio:
            data_inicio = datetime.fromtimestamp(data_inicio)

        return {
            'ticker': ticker,
            'nome': info.get('shortName', ticker),
            'setor': info.get('sector', ''),
            'segmento': info.get('industry', ''),
            'preco': preco,
            'market_cap': info.get('marketCap', np.nan),
            'volume_medio': info.get('averageVolume', np.nan) * preco if pd.notnull(info.get('averageVolume')) else np.nan,
            'dividend_yield': dividend_yield,
            'dividend_rate': dividend_rate,
            'p_vpa': info.get('priceToBook', np.nan),
            'p_l': info.get('trailingPE', np.nan),
            'lucro_liquido': info.get('netIncomeToCommon', np.nan),
            'patrimonio_liquido': info.get('bookValue', np.nan),
            'data_inicio': data_inicio,
            'anos_com_dividendos': anos_com_dividendos
        }

    except Exception as e:
        print(f"❌ Erro {ticker}: {e}")
        return None

def classificar_setor(setor, segmento, ticker):
    """Classifica se o ticker é perene ou a evitar."""
    t_upper = ticker.upper().replace('.SA', '')

    # Verifica se está na lista de tickers perenes
    for lista in PERENEN_SETORES.values():
        if t_upper in [x.upper() for x in lista]:
            return 'PERENE'

    # Verifica setores a evitar
    for lista in EVITAR_SETORES.values():
        if t_upper in [x.upper() for x in lista]:
            return 'EVITAR'

    # Heurística por palavras-chave no setor/segmento
    setor_upper = str(setor).upper() + ' ' + str(segmento).upper()
    perene_kws = ['ENERG', 'ELETRIC', 'PAPEL', 'CELULOSE', 'BANCO', 'FINANCIAL',
                  'SANEAMENT', 'ÁGUA', 'TELECOM', 'MINERAÇÃO', 'PETRÓLEO', 'QUÍMICA',
                  'SEGURO', 'RESSEGURO']
    evitar_kws = ['VAREJO', 'RETAIL', 'AÉREA', 'AIRLINE', 'TURISMO', 'HOSPITAL',
                  'SAÚDE', 'HEALTH', 'TRANSPORT', 'LOGÍSTICA', 'CONSTRUÇÃO',
                  'TECNOLOGIA', 'TECHNOLOGY']

    for kw in perene_kws:
        if kw in setor_upper:
            return 'PERENE'
    for kw in evitar_kws:
        if kw in setor_upper:
            return 'EVITAR'

    return 'NEUTRO'

def filtrar_dataframe(df):
    """Aplica todos os filtros."""
    # 1. Setor PERENE
    df = df[df['classificacao_setor'] == 'PERENE'].copy()

    # 2. Dividend yield mínimo
    df = df[df['dividend_yield'] >= MIN_DIVIDEND_YIELD]

    # 3. P/VPA baixo
    df = df[df['p_vpa'] <= MAX_PVPA]

    # 4. Anos listados
    now = datetime.now()
    def anos_listed_calc(row):
        if pd.notnull(row['data_inicio']):
            return (now - row['data_inicio']).days / 365.25
        else:
            return 20.0  # empresa grande, assumir 20 anos
    df['anos_listed'] = df.apply(anos_listed_calc, axis=1)
    df = df[df['anos_listed'] >= MIN_HISTORY_YEARS]

    # 5. Market cap mínimo
    df = df[df['market_cap'] >= MIN_MARKET_CAP]

    # 6. Consistência de dividendos
    df = df[df['anos_com_dividendos'] >= MIN_DIVIDEND_HISTORY]

    return df

def calcular_score(row):
    """Score de atratividade."""
    score = 0.0
    # Dividend yield
    score += row['dividend_yield'] * 100
    # P/VPA
    pvpa = row['p_vpa']
    if pd.notnull(pvpa):
        if pvpa < 1.0:
            score += 30
        elif pvpa < 1.2:
            score += 20
        elif pvpa < 1.5:
            score += 10
        else:
            score += 5
    # Market cap (prefere maiores)
    if pd.notnull(row['market_cap']):
        score += min(np.log10(row['market_cap'] / 1e9) * 5, 20)
    # Anos com dividendos
    score += min(row['anos_com_dividendos'] * 2, 15)
    # P/L (se válido)
    pl = row['p_l']
    if pd.notnull(pl) and pl > 0 and pl < 30:
        score += (30 - pl) / 2
    return score

def main():
    print("🔍 Barsi Screener - pipeline funcional\n")
    os.makedirs('outputs', exist_ok=True)

    tickers = get_tickers_perenes()
    print(f"📊 Analisando {len(tickers)} tickers de setores perenes...")

    dados = []
    for i, ticker in enumerate(tickers, 1):
        d = buscar_dados_yfinance(ticker)
        if d:
            dados.append(d)
            print(f"[{i}/{len(tickers)}] {ticker} ok (DY={d['dividend_yield']*100:.1f}%)")
        else:
            print(f"[{i}/{len(tickers)}] {ticker} sem dados")
        time.sleep(0.3)  # rate limit

    if not dados:
        print("❌ Nenhum dado obtido!")
        return

    df = pd.DataFrame(dados)
    print(f"\n✅ Dados coletados: {len(df)} tickers")

    # Classificação
    df['classificacao_setor'] = df.apply(lambda x: classificar_setor(x['setor'], x['segmento'], x['ticker']), axis=1)
    print("🏷️ Classificação por setor:")
    print(df['classificacao_setor'].value_counts())

    # Filtros
    df_filtrado = filtrar_dataframe(df)
    print(f"\n🎯 Após filtros: {len(df_filtrado)} ações candidatas")

    if len(df_filtrado) == 0:
        print("⚠️ Nenhuma ação passou os filtros. Confira os thresholds.")
        # Exportar todos para debug
        df_output = df.copy()
    else:
        df_filtrado['score'] = df_filtrado.apply(calcular_score, axis=1)
        df_filtrado = df_filtrado.sort_values('score', ascending=False)
        df_output = df_filtrado

    # Colunas de saída
    cols = ['ticker', 'nome', 'setor', 'segmento', 'classificacao_setor',
            'preco', 'market_cap', 'dividend_yield', 'dividend_rate',
            'p_vpa', 'p_l', 'anos_listed', 'anos_com_dividendos', 'score']
    df_out = df_output[cols].copy()

    # Formatar
    df_out['dividend_yield'] = (df_out['dividend_yield'] * 100).round(2)
    df_out['p_vpa'] = df_out['p_vpa'].round(2)
    df_out['p_l'] = df_out['p_l'].round(2)
    df_out['score'] = df_out['score'].round(1)
    df_out['market_cap'] = df_out['market_cap'].round(0).astype('Int64')
    df_out['anos_listed'] = df_out['anos_listed'].round(1)

    # Salvar
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'outputs/barsi_screener_{ts}.csv'
    df_out.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df_out.to_csv('outputs/barsi_screener_latest.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 CSV salvo: {csv_path}")

    # Relatório markdown
    md_path = f'outputs/relatorio_{ts}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Barsi Screener - Relatório\n\n')
        f.write(f'**Data:** {datetime.now().strftime("%d/%m/%Y %H:%M")}\n')
        f.write(f'**Fonte:** yfinance\n')
        f.write(f'**Tickers perenes:** {len(tickers)}\n')
        f.write(f'**Dados obtidos:** {len(df)}\n')
        f.write(f'**Após filtros:** {len(df_filtrado) if len(df_filtrado)>0 else 0}\n\n')
        if len(df_filtrado) > 0:
            f.write('## Top 10 oportunidades\n\n')
            f.write(df_out.head(10).to_markdown(index=False))
        else:
            f.write('## Nenhuma ação atendeu aos critérios\n')
        f.write('\n## Critérios\n')
        f.write('- Dividend Yield >= 3%\n')
        f.write('- P/VPA <= 2.0\n')
        f.write('- Market cap >= R$ 1 bi\n')
        f.write('- Anos listed >= 5\n')
        f.write('- Dividendos >= 3 anos\n')
    print(f"📝 Relatório: {md_path}")

    if len(df_filtrado) > 0:
        print("\n📈 Resultado:")
        print(df_out.head(10).to_string(index=False))
    print("\n✅ Concluído!")

if __name__ == '__main__':
    main()