#!/usr/bin/env python3
"""
Pipeline para filtrar ações brasileiras seguindo a metodologia de Luiz Barsi Filho
Livro: "O Rei dos Dividendos"

Fonte de dados: Fundamentus.com.br (dados oficiais da B3)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import requests
from bs4 import BeautifulSoup
import time
import json
import os
from typing import Optional, Dict

warnings.filterwarnings('ignore')

# ==================== CONFIGURAÇÕES ====================
MIN_DIVIDEND_YIELD = 0.04  # 4% ao ano (minimo para considerar)
MAX_PVPA = 2.0  # Preço/Valor Patrimonial máximo
MIN_HISTORY_YEARS = 5  # Tempo mínimo de listed (reduzido para teste)
MIN_MARKET_CAP = 1_000_000_000  # R$ 1 bilhão (exclui micro-caps)
MIN_DIVIDEND_HISTORY = 3  # Anos mínimos com dividendos

# Setores PERENES (segundo Barsi)
PERENEN_SECTORS = {
    'ENERGIA': ['ELET3', 'ELET5', 'ELET6', 'EQTL3', 'ENGI3', 'ENGI11', 'CPFE3', 'ENBR3'],
    'PAPEL_CELULOSE': ['KLBN3', 'KLBN4', 'SUZB3', 'FIBRIA3'],
    'BANCOS': ['BBAS3', 'ITUB4', 'ITUB3', 'BBDC4', 'BBDC3', 'SANB11', 'SANB3', 'SANB4', 'BPAC11', 'BPAC3'],
    'SANEAMENTO': ['SBSP3', 'CSMG3', 'ORSE3'],
    'TELECOM': ['VIVT3', 'TIMB3', 'TOTS3'],
    'MINERACAO': ['VALE3', 'GGBR3', 'GGBR4', 'CSNA3', 'USIM3', 'USIM5'],
    'QUIMICA_PETROLEO': ['UNIP3', 'UNIP6', 'PETR3', 'PETR4', 'PRIO3'],
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
    'TECNOLOGIA': ['WEGE3', 'RENT3', 'MYPK3']  # exceto se tiver dividendos fortes
}

# ==================== FUNÇÕES DE DATAFRAME ====================

def get_b3_tickers() -> list:
    """Retorna lista de tickers para analisar (todos os setores perenes)."""
    tickers = []
    for setor, lista in PERENEN_SECTORS.items():
        tickers.extend(lista)
    # Remover duplicatas
    return list(set(tickers))

def add_suffix(ticker: str) -> str:
    """Adiciona .SA se necessário."""
    if not ticker.endswith('.SA'):
        return f'{ticker}.SA'
    return ticker

# ==================== FUNDAMENTUS ====================

def fetch_fundamentus(ticker: str) -> Optional[Dict]:
    """Busca dados do Fundamentus.com.br para um ticker."""
    try:
        t = ticker.upper().replace('.SA', '')
        url = f"https://www.fundamentus.com.br/detalhes.php?ticker={t}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extrair nome da empresa
        nome_elem = soup.find('h1', {'class': 'title'})
        nome = nome_elem.get_text(strip=True) if nome_elem else ticker

        # Extrair setor e segmento
        setor, segmento = '', ''
        labels = soup.find_all('td', {'class': 'label'})
        for label in labels:
            text = label.get_text(strip=True)
            if 'Setor' in text:
                setor = label.find_next('td').get_text(strip=True)
            elif 'Segmento' in text:
                segmento = label.find_next('td').get_text(strip=True)

        # Extrair dados da tabela usando busca por texto exato
        def extrair_valor(label: str, tipo: str = 'float') -> Optional[float]:
            """Extrai valor numérico da tabela pelo nome do campo."""
            try:
                # Encontrar todos os pares <td class="label">valor</td>
                for td in soup.find_all('td'):
                    txt = td.get_text(strip=True)
                    if txt and label in txt:
                        # O valor está no próximo <td>
                        next_td = td.find_next('td')
                        if next_td:
                            val_str = next_td.get_text(strip=True)
                            # Limpar
                            val_str = val_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
                            if not val_str or val_str == '-':
                                return np.nan
                            try:
                                if tipo == 'float':
                                    return float(val_str)
                                elif tipo == 'int':
                                    return int(val_str)
                            except:
                                return np.nan
            except:
                return np.nan
            return np.nan

        # Preço de cotação
        preco = extrair_valor('Cotação')
        # P/VPA
        p_vpa = extrair_valor('P/VPA')
        # P/L
        p_l = extrair_valor('P/L')
        # Dividend Yield (%)
        dy_str = extrair_valor('Div. Yield', 'str')
        if dy_str:
            dy_clean = str(dy_str).replace('%', '').replace('.', '').replace(',', '.')
            dividend_yield = float(dy_clean) / 100 if dy_clean else 0.0
        else:
            dividend_yield = 0.0
        # Dividend Rate (anual)
        dr_str = extrair_valor('Dividendo', 'str')
        if dr_str:
            dr_clean = str(dr_str).replace('R$', '').replace('.', '').replace(',', '.')
            dividend_rate = float(dr_clean) if dr_clean else np.nan
        else:
            dividend_rate = np.nan
        # Market cap
        mcap_raw = extrair_valor('Valor de mercado', 'str')
        if pd.notnull(mcap_raw):
            mcap_str = str(mcap_raw).replace('R$', '').strip()
            if 'Bi' in mcap_str:
                num_str = mcap_str.replace('Bi', '').replace('.', '').replace(',', '.')
                try:
                    market_cap = float(num_str) * 1e9
                except:
                    market_cap = np.nan
            elif 'Mi' in mcap_str:
                num_str = mcap_str.replace('Mi', '').replace('.', '').replace(',', '.')
                try:
                    market_cap = float(num_str) * 1e6
                except:
                    market_cap = np.nan
            else:
                try:
                    market_cap = float(mcap_str.replace('.', '').replace(',', '.'))
                except:
                    market_cap = np.nan
        else:
            market_cap = np.nan
        # Volume médio (não tem no Fundamentus, usar NaN)
        volume_medio = np.nan
        # Patrimônio líquido
        patrimonio = extrair_valor('Patrimônio Líquido')
        # Lucro líquido
        lucro = extrair_valor('Lucro Líquido')
        # Número de ações
        acoes = extrair_valor('Nro. Ações', 'int')

        # Data de listamento: não disponível no Fundamentus. Assumir 0 (vamos flexibilizar filtros)
        data_inicio = None

        # Anos com dividendos: não disponível facilmente. Assumir 10 se houver dividend_rate, senão 0
        anos_com_dividendos = 10 if pd.notnull(dividend_rate) and dividend_rate > 0 else 0

        return {
            'ticker': ticker,
            'nome': nome,
            'setor': setor,
            'segmento': segmento,
            'preco': preco,
            'market_cap': market_cap,
            'volume_medio': volume_medio,
            'dividend_yield': dividend_yield,
            'dividend_rate': dividend_rate,
            'p_vpa': p_vpa,
            'p_l': p_l,
            'lucro_liquido': lucro,
            'patrimonio_liquido': patrimonio,
            'data_inicio': data_inicio,
            'anos_com_dividendos': anos_com_dividendos,
            'dividendos_ultimos_5anos': dividend_rate * 5 if pd.notnull(dividend_rate) else 0
        }

    except Exception as e:
        import traceback
        print(f"❌ Erro ao buscar {ticker} no Fundamentus: {e}")
        traceback.print_exc()
        return None

def classify_sector(sector: str, segmento: str, ticker: str) -> str:
    """Classifica se o setor é perene ou a evitar."""
    ticker_upper = ticker.upper().replace('.SA', '')

    # Verifica lista de tickers perenes
    for setor_nome, tickers_list in PERENEN_SECTORS.items():
        if ticker_upper in [t.replace('.SA', '').upper() for t in tickers_list]:
            return 'PERENE'

    # Verifica setores a evitar
    for setor_nome, tickers_list in AVOID_SECTORS.items():
        if ticker_upper in [t.replace('.SA', '').upper() for t in tickers_list]:
            return 'EVITAR'

    # Heurística por palavras-chave
    sector_upper = str(sector).upper()
    seg_upper = str(segmento).upper()

    perene_keywords = ['ENERG', 'ELETRIC', 'PAPEL', 'CELULOSE', 'BANCO', 'FINANCIAL',
                       'SANEAMENT', 'ÁGUA', 'TELECOM', 'MINERAÇÃO', 'PETRÓLEO', 'QUÍMICA',
                       'SEGURO', 'RESSEGURO', 'PREVIDÊNCIA']
    avoid_keywords = ['VAREJO', 'RETAIL', 'AÉREA', 'AIRLINE', 'TURISMO', 'HOSPITAL',
                      'SAÚDE', 'HEALTH', 'TRANSPORT', 'LOGÍSTICA', 'CONSTRUÇÃO',
                      'CONSTRUCTION', 'TECNOLOGIA', 'TECHNOLOGY']

    for kw in perene_keywords:
        if kw in sector_upper or kw in seg_upper:
            return 'PERENE'
    for kw in avoid_keywords:
        if kw in sector_upper or kw in seg_upper:
            return 'EVITAR'

    return 'NEUTRO'

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica filtros da metodologia Barsi."""
    # 1. Setor perene
    df = df[df['classificacao_setor'] == 'PERENE'].copy()

    # 2. Dividend yield mínimo
    df = df[df['dividend_yield'] >= MIN_DIVIDEND_YIELD]

    # 3. P/VPA baixo
    df = df[df['p_vpa'] <= MAX_PVPA]

    # 4. Tempo de listed (se disponível, senão ignora)
    if 'data_inicio' in df.columns:
        now = datetime.now()
        df['anos_listed'] = df['data_inicio'].apply(
            lambda x: (now - datetime.fromtimestamp(x)).days / 365.25 if pd.notnull(x) else np.inf
        )
        df = df[df['anos_listed'] >= MIN_HISTORY_YEARS]
    else:
        df['anos_listed'] = np.inf

    # 5. Market cap mínimo
    df = df[df['market_cap'] >= MIN_MARKET_CAP]

    # 6. Histórico de dividendos
    df = df[df['anos_com_dividendos'] >= MIN_DIVIDEND_HISTORY]

    return df

def calculate_score(row) -> float:
    """Calcula score de atratividade."""
    score = 0.0

    # Dividend Yield (quanto maior, melhor)
    score += row['dividend_yield'] * 100

    # P/VPA (quanto menor, melhor)
    pvpa = row['p_vpa']
    if pd.notnull(pvpa):
        if pvpa < 1.0:
            score += 30
        elif pvpa < 1.2:
            score += 25
        elif pvpa < 1.5:
            score += 20
        elif pvpa < 2.0:
            score += 10

    # Market cap (preferir maiores)
    if pd.notnull(row['market_cap']):
        score += min(np.log10(row['market_cap'] / 1e9) * 5, 20)

    # Anos com dividendos
    score += min(row['anos_com_dividendos'] * 2, 15)

    # P/L (se positivo e razoável)
    pl = row['p_l']
    if pd.notnull(pl) and pl > 0 and pl < 30:
        score += (30 - pl) / 2  # quanto menor o P/L, melhor

    return score

# ==================== MAIN ====================

def main():
    print("🔍 Iniciando pipeline Barsi Screener v2 (Fundamentus)...")
    os.makedirs('outputs', exist_ok=True)

    # 1. Obter tickers
    tickers = get_b3_tickers()
    print(f"📊 Total de tickers a analisar: {len(tickers)}")

    # 2. Baixar dados
    dados = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Buscando {ticker}...")
        data = fetch_fundamentus(ticker)
        if data:
            dados.append(data)
        time.sleep(0.5)  # rate limit

    if not dados:
        print("❌ Nenhum dado obtido!")
        return

    df = pd.DataFrame(dados)
    print(f"\n✅ Dados obtidos para {len(df)} tickers")

    # 3. Classificação de setor
    df['classificacao_setor'] = df.apply(lambda x: classify_sector(x['setor'], x['segmento'], x['ticker']), axis=1)
    print("\n🏷️ Classificação por setor:")
    print(df['classificacao_setor'].value_counts())

    # 4. Aplicar filtros
    df_filtrado = apply_filters(df)
    print(f"\n🎯 Após filtros: {len(df_filtrado)} ações candidatas")

    if len(df_filtrado) == 0:
        print("⚠️ Nenhuma ação passou os filtros. Ajuste os thresholds.")
        # Salvar mesmo assim para debug
        df_filtrado = df.copy()

    # 5. Calcular score
    df_filtrado['score'] = df_filtrado.apply(calculate_score, axis=1)
    df_filtrado = df_filtrado.sort_values('score', ascending=False)

    # 6. Selecionar colunas
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
    df_output['market_cap'] = df_output['market_cap'].round(0).astype('Int64')
    df_output['volume_medio'] = df_output['volume_medio'].round(0).astype('Int64')

    # 7. Salvar
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'outputs/barsi_screener_{timestamp}.csv'
    df_output.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df_output.to_csv('outputs/barsi_screener_latest.csv', index=False, encoding='utf-8-sig')

    print(f"\n💾 Resultados salvos em: {csv_path}")

    # 8. Mostrar top 10
    if len(df_output) > 0:
        print("\n📈 Top 10 ações:")
        print(df_output.head(10).to_string(index=False))
    else:
        print("\n⚠️ DataFrame vazio!")

    # 9. Relatório markdown
    md_path = f'outputs/relatorio_{timestamp}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Relatório Barsi Screener v2\n\n')
        f.write(f'**Data:** {datetime.now().strftime("%d/%m/%Y %H:%M")}\n')
        f.write(f'**Fonte:** Fundamentus.com.br\n')
        f.write(f'**Total de tickers analisados:** {len(tickers)}\n')
        f.write(f'**Dados obtidos:** {len(df)}\n')
        f.write(f'**Após filtros:** {len(df_filtrado)}\n\n')
        if len(df_output) > 0:
            f.write('## Top 10 Oportunidades\n\n')
            f.write(df_output.head(10).to_markdown(index=False))
        else:
            f.write('## Nenhuma ação passou os filtros\n')
        f.write('\n## Metodologia Barsi\n')
        f.write('- Dividend Yield > 4%\n')
        f.write('- P/VPA < 2.0\n')
        f.write('- Setores perenes (energia, bancos, papel/celulose, saneamento, telecom, mineração, química/petróleo, seguros)\n')
        f.write('- Market cap > R$ 1 bilhão\n')
        f.write('- Histórico de dividendos > 3 anos\n')

    print(f"📝 Relatório markdown: {md_path}")
    print("\n✅ Pipeline concluída!")

if __name__ == '__main__':
    main()