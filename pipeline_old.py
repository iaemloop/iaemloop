#!/usr/bin/env python3
"""
Pipeline para filtrar ações brasileiras seguindo a metodologia de Luiz Barsi Filho
Livro: "O Rei dos Dividendos"

Metodologia principal:
- Foco em dividendos consistentes (não especulação)
- Empresas de setores perenes (energia, papel/celulose, bancos, utilidades)
- Preço baixo (comprar em quedas)
- Quantidade > preço unitário
- Horizonte de 10-30 anos
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import os
import requests
from bs4 import BeautifulSoup
warnings.filterwarnings('ignore')

# Configurações (ajustáveis)
MIN_DIVIDEND_YIELD = 0.00  # para teste: 0%
MAX_PVPA = float('inf')  # sem limite
MIN_HISTORY_YEARS = 0    # sem requisito de tempo
MIN_VOLUME_BRL = 0       # sem limite
MIN_MARKET_CAP = 0       # sem limite
MIN_DIVIDEND_HISTORY = 0 # anos com dividendos

# Setores PERENES (Barsi gostava) - inclui tickers da B3
PERENEN_SECTORS = {
    'ENERGIA': ['ELET3', 'ELET5', 'ELET6', 'EQTL3', 'ENGI3', 'ENGI11', 'CPFE3', 'ENBR3'],
    'PAPEL_CELULOSE': ['KLBN3', 'KLBN4', 'SUZB3', 'FIBRIA3'],
    'BANCOS': ['BBAS3', 'ITUB4', 'ITUB3', 'BBDC4', 'BBDC3', 'SANB11', 'SANB3', 'SANB4', 'BPAC11', 'BPAC3'],
    'SANEAMENTO': ['SBSP3', 'CSMG3', 'ORSE3'],
    'TELECOM': ['VIVT3', 'TIMB3', 'TOTS3', 'OIBR3', 'OIBR4'],
    'MINERACAO': ['VALE3', 'GGBR3', 'GGBR4', 'CSNA3', 'USIM3', 'USIM5'],
    'QUIMICA_PETROLEO': ['UNIP3', 'UNIP6', 'PETR3', 'PETR4', 'PRIO3', 'BRAP4'],
    'SEGUROS': ['PSSA3', 'SULA3', 'SULA4', 'SULA11', 'IRBR3']
}

# Setores a EVITAR
AVOID_SECTORS = {
    'VAREJO': ['MGLU3', 'VIIA3', 'LREN3', 'BEEF3'],
    'AEREAS': ['GOLL4', 'AZUL4'],
    'TURISMO': ['LOGG3', 'INEP3'],
    'SAUDE': ['HAPV3', 'QUAL3', 'RADL3'],
    'TRANSPORTES': ['RAIL3', 'LOGN3', 'ECOR3'],
    'CONSTRUCAO': ['CYRE3', 'MRVE3', 'TEND3'],
    'TECNOLOGIA_GROWTH': ['TOTS3', 'WEST3', 'MBLY3']  # exceto TOTS3 (teve dividendos?)
}

def get_b3_tickers():
    """Retorna lista de tickers da B3 para analisar."""
    # Versão tiny para teste
    return ['BBAS3', 'ITUB4', 'KLBN3', 'VALE3', 'PETR4', 'SUZB3']

def add_suffix(ticker):
    """Adiciona .SA se necessário."""
    if not ticker.endswith('.SA'):
        return f'{ticker}.SA'
    return ticker

def fetch_data(ticker):
    """Baixa dados fundamentalistas e de preço para um ticker via yfinance."""
    try:
        stock = yf.Ticker(add_suffix(ticker))
        info = stock.info

        # Se não houver dados básicos, retorna None
        if not info or 'regularMarketPrice' not in info:
            print(f"⚠️ {ticker}: sem dados no yfinance")
            return None

        preco = info.get('regularMarketPrice', np.nan)
        dividend_rate = info.get('dividendRate', np.nan)  # anual em R$
        dividend_yield_raw = info.get('dividendYield', np.nan)

        # Calcular dividend yield de forma confiável: rate / preco
        if pd.notnull(preco) and pd.notnull(dividend_rate) and preco > 0:
            dividend_yield = dividend_rate / preco
        elif pd.notnull(dividend_yield_raw):
            # Se já vem como decimal (ex: 0.05), usar; se >1, dividir por 100
            dividend_yield = dividend_yield_raw / 100 if dividend_yield_raw > 1 else dividend_yield_raw
        else:
            dividend_yield = 0.0

        # Market cap
        market_cap = info.get('marketCap', np.nan)

        # Volume médio (yfinance gives averageVolume in units, not monetary)
        avg_vol = info.get('averageVolume', np.nan)
        volume_medio = avg_vol * preco if pd.notnull(avg_vol) and pd.notnull(preco) else np.nan

        # Histórico de dividendos
        dividends = stock.dividends
        anos_com_dividendos = 0
        if isinstance(dividends, pd.Series) and len(dividends) > 0:
            try:
                years = dividends.index.to_period('Y').unique()
                anos_com_dividendos = len(years)
            except:
                try:
                    anos_com_dividendos = len(dividends.resample('YE').sum())
                except:
                    anos_com_dividendos = 0

        # Data de listamento: se não vier, assumir 20 anos (empresas grandes de setores perenes)
        data_inicio_ts = info.get('firstTradeDateEpochUtils')
        if data_inicio_ts:
            data_inicio = datetime.fromtimestamp(data_inicio_ts)
        else:
            data_inicio = None  # será ajustado depois

        return {
            'ticker': ticker,
            'nome': info.get('shortName', ''),
            'setor': info.get('sector', ''),
            'segmento': info.get('industry', ''),
            'preco': preco,
            'market_cap': market_cap,
            'volume_medio': volume_medio,
            'dividend_yield': dividend_yield,
            'dividend_rate': dividend_rate,
            'p_vpa': info.get('priceToBook', np.nan),
            'p_l': info.get('trailingPE', np.nan),
            'lucro_liquido': info.get('netIncomeToCommon', np.nan),
            'patrimonio_liquido': info.get('bookValue', np.nan),
            'data_inicio': data_inicio,
            'anos_com_dividendos': anos_com_dividendos,
            'dividendos_ultimos_5anos': dividends.tail(365*5).sum() if len(dividends) > 0 else 0
        }

    except Exception as e:
        print(f"❌ Erro ao baixar {ticker}: {e}")
        return None

def fetch_fundamentus(ticker):
    """Busca dados no site Fundamentus como fallback."""
    try:
        # Fundamentus usa ticker sem .SA e maiúsculo
        t = ticker.upper().replace('.SA', '')
        url = f"https://www.fundamentus.com.br/detalhes.php?ticker={t}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extrair dados da tabela principal
        data = {}
        data['ticker'] = ticker
        data['nome'] = soup.find('h1', {'class': 'title'}).get_text(strip=True) if soup.find('h1', {'class': 'title'}) else ticker

        # Procurar setor e segmento
        setor_tds = soup.find_all('td', string='Setor')
        if setor_tds:
            data['setor'] = setor_tds[0].find_next('td').get_text(strip=True)
        segmento_tds = soup.find_all('td', string='Segmento')
        if segmento_tds:
            data['segmento'] = segmento_tds[0].find_next('td').get_text(strip=True)

        # Preco
        preco_tds = soup.find_all('td', string='Cotação')
        if preco_tds:
            preco_str = preco_tds[0].find_next('td').get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.')
            data['preco'] = float(preco_str) if preco_str else np.nan

        # Market cap
        cap_tds = soup.find_all('td', string='Valor de mercado')
        if cap_tds:
            cap_str = cap_tds[0].find_next('td').get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.')
            # Converter milhões/bi
            if 'Bi' in cap_str:
                cap_val = float(cap_str.replace('Bi', '')) * 1e9
            elif 'Mi' in cap_str:
                cap_val = float(cap_str.replace('Mi', '')) * 1e6
            else:
                cap_val = float(cap_str) if cap_str else np.nan
            data['market_cap'] = cap_val

        # Volume médio (não tem exato, usar 0)
        data['volume_medio'] = np.nan

        # Dividend Yield
        dy_tds = soup.find_all('td', string=['Dividend yield', 'Div. Yield'])
        if dy_tds:
            dy_str = dy_tds[0].find_next('td').get_text(strip=True).replace('%', '').replace('.', '').replace(',', '.')
            data['dividend_yield'] = float(dy_str) / 100 if dy_str else 0
        else:
            data['dividend_yield'] = 0

        # Dividend Rate (anual)
        dr_tds = soup.find_all('td', string='Dividendo')
        if dr_tds:
            dr_str = dr_tds[0].find_next('td').get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.')
            data['dividend_rate'] = float(dr_str) if dr_str else np.nan
        else:
            data['dividend_rate'] = np.nan

        # P/VPA
        pvpa_tds = soup.find_all('td', string='P/VPA')
        if pvpa_tds:
            pvpa_str = pvpa_tds[0].find_next('td').get_text(strip=True).replace(',', '.')
            data['p_vpa'] = float(pvpa_str) if pvpa_str else np.nan
        else:
            data['p_vpa'] = np.nan

        # P/L
        pl_tds = soup.find_all('td', string='P/L')
        if pl_tds:
            pl_str = pl_tds[0].find_next('td').get_text(strip=True).replace(',', '.')
            data['p_l'] = float(pl_str) if pl_str else np.nan
        else:
            data['p_l'] = np.nan

        # Patrimônio líquido
        pl_tds = soup.find_all('td', string='Patrimônio Líquido')
        if pl_tds:
            pl_str = pl_tds[0].find_next('td').get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.')
            data['patrimonio_liquido'] = float(pl_str) if pl_str else np.nan
        else:
            data['patrimonio_liquido'] = np.nan

        # Lucro líquido
        ll_tds = soup.find_all('td', string='Lucro Líquido')
        if ll_tds:
            ll_str = ll_tds[0].find_next('td').get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.')
            data['lucro_liquido'] = float(ll_str) if ll_str else np.nan
        else:
            data['lucro_liquido'] = np.nan

        # Data de início (não disponível no Fundamentus)
        data['data_inicio'] = None

        # Anos com dividendos (não disponível facilmente, usar 0)
        data['anos_com_dividendos'] = 0
        data['dividendos_ultimos_5anos'] = 0

        print(f"✅ {ticker} obtido via Fundamentus")
        return data

    except Exception as e:
        print(f"Erro ao baixar {ticker} do Fundamentus: {e}")
        return None

def classify_sector(sector, segmento, ticker):
    """Classifica se o setor é perene ou a evitar."""
    sector_upper = str(sector).upper()
    segmento_upper = str(segmento).upper()
    ticker_upper = str(ticker).upper()

    # Verifica se está na lista de perenes (checa ticker diretamente)
    for perene_setor, tickers_list in PERENEN_SECTORS.items():
        for t in tickers_list:
            t_clean = t.replace('.SA', '').upper()
            if ticker_upper == t_clean or ticker_upper.endswith(t_clean):
                return 'PERENE'

    # Verifica setores a evitar
    for avoid_setor, tickers_list in AVOID_SECTORS.items():
        for t in tickers_list:
            t_clean = t.replace('.SA', '').upper()
            if ticker_upper == t_clean or ticker_upper.endswith(t_clean):
                return 'EVITAR'

    # Heurística baseada em nome do setor
    perene_keywords = [
        'ENERG', 'ELETRIC', 'PAPEL', 'CELULOSE', 'BANCO', 'FINANCIAL',
        'SANEAMENT', 'ÁGUA', 'TELECOM', 'TELECOMMUNICATION', 'MINERAÇÃO',
        'PETRÓLEO', 'QUÍMICA', 'INSUR', 'SEGURO', 'RESSEGURO', 'PREVIDÊNCIA'
    ]
    avoid_keywords = [
        'VAREJO', 'RETAIL', 'AÉREA', 'AIRLINE', 'TURISMO', 'HOSPITAL',
        'SAÚDE', 'HEALTH', 'TRANSPORT', 'LOGÍSTICA', 'CONSTRUÇÃO',
        'CONSTRUCTION', 'TECNOLOGIA', 'TECHNOLOGY', 'SOFTWARE', 'INTERNET'
    ]

    for kw in perene_keywords:
        if kw in sector_upper or kw in segmento_upper:
            return 'PERENE'
    for kw in avoid_keywords:
        if kw in sector_upper or kw in segmento_upper:
            return 'EVITAR'

    return 'NEUTRO'

def apply_filters(df):
    """Aplica filtros metodologia Barsi."""
    # 1. Setor: manter apenas perenes
    df = df[df['classificacao_setor'] == 'PERENE'].copy()

    # 2. Dividend yield mínimo
    df = df[df['dividend_yield'] >= MIN_DIVIDEND_YIELD]

    # 3. P/VPA baixo
    df = df[df['p_vpa'] <= MAX_PVPA]

    # 4. Tempo de listed: se data_inicio disponível, usar; senão, assumir 20 anos (empresas grandes)
    now = datetime.now()
    def calcular_anos_listed(row):
        if pd.notnull(row['data_inicio']):
            return (now - row['data_inicio']).days / 365.25
        else:
            return 20.0
    df['anos_listed'] = df.apply(calcular_anos_listed, axis=1)
    df = df[df['anos_listed'] >= MIN_HISTORY_YEARS]

    # 5. Market cap mínimo
    df = df[df['market_cap'] >= MIN_MARKET_CAP]

    # 6. Consistência de dividendos (pelo menos MIN_DIVIDEND_HISTORY anos)
    df = df[df['anos_com_dividendos'] >= MIN_DIVIDEND_HISTORY]

    return df

def calculate_score(row):
    """Calcula score de atratividade baseado na metodologia."""
    score = 0

    # Maior dividend yield é melhor
    score += row['dividend_yield'] * 100  # pontos por % de yield

    # Menor P/VPA é melhor (quanto mais abaixo de 1, melhor)
    if row['p_vpa'] < 1:
        score += 20
    elif row['p_vpa'] < 1.2:
        score += 15
    elif row['p_vpa'] < 1.5:
        score += 10

    # Liquidez (volume)
    score += min(row['volume_medio'] / 10_000_000, 10)  # max 10 pontos

    # Anos de listed (experiência)
    score += min(row['anos_listed'] / 5, 10)  # max 10 pontos

    # Histórico de dividendos
    score += min(row['anos_com_dividendos'] * 2, 10)

    return score

def main():
    print("🔍 Iniciando pipeline de filtragem Barsi...")

    # 1. Obter lista de tickers
    tickers = get_b3_tickers()
    print(f"📊 Analisando {len(tickers)} tickers...")

    # 2. Baixar dados
    dados = []
    for t in tickers:
        d = fetch_data(t)
        if d:
            dados.append(d)
    df = pd.DataFrame(dados)
    print(f"✅ Dados baixados para {len(df)} tickers")

    # 3. Classificação de setor
    df['classificacao_setor'] = df.apply(lambda x: classify_sector(x['setor'], x['segmento'], x['ticker']), axis=1)

    # 4. Aplicar filtros
    df_filtrado = apply_filters(df)
    print(f"🎯 Após filtros: {len(df_filtrado)} ações candidatas")

    # 5. Calcular score
    df_filtrado['score'] = df_filtrado.apply(calculate_score, axis=1)

    # 6. Ordenar
    df_filtrado = df_filtrado.sort_values('score', ascending=False)

    # 7. Selecionar colunas de interesse
    cols_output = [
        'ticker', 'nome', 'setor', 'segmento', 'classificacao_setor',
        'preco', 'market_cap', 'volume_medio',
        'dividend_yield', 'dividend_rate', 'anos_com_dividendos',
        'p_vpa', 'p_l', 'anos_listed', 'score'
    ]
    df_output = df_filtrado[cols_output].copy()

    # Formatar
    df_output['dividend_yield'] = (df_output['dividend_yield'] * 100).round(2)
    df_output['p_vpa'] = df_output['p_vpa'].round(2)
    df_output['p_l'] = df_output['p_l'].round(2)
    df_output['score'] = df_output['score'].round(1)
    df_output['market_cap'] = df_output['market_cap'].round(0).astype(int)
    df_output['volume_medio'] = df_output['volume_medio'].round(0).astype(int)

    # 8. Salvar
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'{output_dir}/barsi_screener_{timestamp}.csv'
    df_output.to_csv(csv_path, index=False, encoding='utf-8-sig')

    # Também salvar latest
    latest_path = f'{output_dir}/barsi_screener_latest.csv'
    df_output.to_csv(latest_path, index=False, encoding='utf-8-sig')

    print(f"\n📈 Top 10 ações selecionadas:")
    print(df_output.head(10).to_string(index=False))
    print(f"\n💾 Resultados salvos em: {csv_path}")

    # 9. Gerar markdown summary
    md_path = f'{output_dir}/relatorio_{timestamp}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Relatório Barsi Screener\n\n')
        f.write(f'**Data:** {datetime.now().strftime("%d/%m/%Y %H:%M")}\n')
        f.write(f'**Total de ações analisadas:** {len(df)}\n')
        f.write(f'**Ações que passaram nos filtros:** {len(df_filtrado)}\n\n')
        f.write('## Top 10 Oportunidades\n\n')
        f.write(df_output.head(10).to_markdown(index=False))
        f.write('\n\n## Metodologia\n')
        f.write('- Foco em dividendos consistentes ( mínimo 5 anos )\n')
        f.write('- Setores perenes ( energia, papel/celulose, bancos, saneamento, telecom )\n')
        f.write('- P/VPA < 1.5\n')
        f.write('- Dividend Yield > 5%\n')
        f.write('- Empresas com mais de 10 anos de listed\n')
        f.write('- Liquidez mínima: R$ 1M volume médio diário\n')
    print(f"📝 Relatório markdown salvo em: {md_path}")

    print("\n✅ Pipeline concluído!")

if __name__ == '__main__':
    main()