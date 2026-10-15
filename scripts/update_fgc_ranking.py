#!/usr/bin/env python3
"""
Atualiza ranking FGC:
- Lê dados crus do Yubb (fgc_products_raw.json)
- Mescla com histórico (fgc_history.json) mantendo data_primeira
- Mescla com ratings de instituições (ratings_bancos.json) se disponível
- Calcula is_new (produto com < 30 dias)
- Gera fgc_products.json (pronto para site)
- Salva timestamp da atualização
"""

import json
import os
import re
from datetime import datetime, timedelta

DATA_DIR = 'data'
RAW_FILE = os.path.join(DATA_DIR, 'fgc_products_raw.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'fgc_history.json')
RATINGS_FILE = os.path.join(DATA_DIR, 'ratings_bancos.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'fgc_products.json')
TIMESTAMP_FILE = os.path.join(DATA_DIR, 'last_updated.txt')
PAGE_FILE = 'ranking_fgc.html'

hoje = datetime.now()
hoje_str = hoje.strftime('%Y-%m-%d')

# Carregar histórico (mapeia nome_produto -> data_primeira).
# Versões antigas salvavam {primeira_data, ultima_data, count}; normalize para string.
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        historico_raw = json.load(f)
    historico = {}
    for nome, valor in historico_raw.items():
        if isinstance(valor, str):
            historico[nome] = valor
        elif isinstance(valor, dict):
            historico[nome] = valor.get('primeira_data') or valor.get('data_primeira') or hoje_str
else:
    historico = {}

# Carregar ratings de instituições (se disponível)
ratings_data = {}
if os.path.exists(RATINGS_FILE):
    with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
        ratings_data = json.load(f)
    print(f"✅ Ratings carregados: {len(ratings_data)} instituições")
else:
    print("⚠️  Ratings não encontrados. Emissores sem classificação ficarão como 'Sem rating público'")

EMISSOR_ALIASES = {
    'Agibank': 'BANCO AGIBANK S.A.',
    'BBM': 'BANCO BOCOM BBM S.A.',
    'BDMG': 'BANCO DE DESENVOLVIMENTO DE MINAS GERAIS S.A. - BDMG',
    'BMG': 'BANCO BMG S.A.',
    'BR Partners': 'BR PARTNERS BANCO DE INVESTIMENTO S.A.',
    'BS2': 'BANCO BS2 S.A.',
    'BTG Pactual': 'Banco BTG Pactual S.A.',
    'BV': 'BANCO VOTORANTIM S.A.',
    'Banco ABC Brasil': 'BANCO ABC BRASIL S.A.',
    'Banco Industrial do Brasil': 'BANCO INDUSTRIAL DO BRASIL S.A.',
    'Banco Inter': 'BANCO INTER S.A.',
    'Banco Seguro': 'BANCO SEGURO S.A.',
    'Bancoob': 'BANCO COOPERATIVO SICOOB S.A.',
    'Bari': 'BANCO BARI DE INVESTIMENTOS E FINANCIAMENTOS S.A.',
    'Bradesco': 'BANCO BRADESCO S.A.',
    'C6 Bank': 'BANCO C6 S.A.',
    'Caixa Geral': 'BANCO CAIXA GERAL - BRASIL S.A.',
    'Caruana Financeira': 'CARUANA S.A. - SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO',
    'China Construction Bank': 'China Construction Bank (Brasil)',
    'Digimais': 'BANCO DIGIMAIS S.A.',
    'Fator': 'BANCO FATOR S.A.',
    'Fibra': 'BANCO FIBRA S.A.',
    'Haitong': 'HAITONG BANCO DE INVESTIMENTO DO BRASIL S.A.',
    'Luso Brasileiro': 'BANCO LUSO BRASILEIRO S.A.',
    'Mercado Livre': 'MERCADO CRÉDITO SOCIEDADE DE CRÉDITO, FINANCIAMENTO E INVESTIMENTO S.A.',
    'Mercantil': 'BANCO MERCANTIL DO BRASIL S.A. - Banco Mercantil',
    'NBC': 'NOVO BANCO CONTINENTAL S.A. BANCO MÚLTIPLO',
    'Omni Banco': 'OMNI BANCO S.A.',
    'Original': 'BANCO ORIGINAL S.A.',
    'Ourinvest': 'BANCO OURINVEST S.A.',
    'PAN': 'BANCO PAN S.A.',
    'Paraná Banco': 'PARANÁ BANCO S.A.',
    'Paulista': 'BANCO PAULISTA S.A.',
    'Pine': 'BANCO PINE S.A.',
    'Rendimento': 'BANCO RENDIMENTO S.A.',
    'Rodobens': 'BANCO RODOBENS S.A.',
    'Topázio': 'BANCO TOPÁZIO S.A.',
    'Tribanco': 'BANCO TRIÂNGULO S.A.',
    'Votorantim': 'BANCO VOTORANTIM S.A.',
}

UNRATED_ISSUERS = {
    'Alfa',
    'Facta Financeira',
    'RNX',
    'Realize Financeira',
}

RATING_OVERRIDES = {
    # Fitch reafirmou AAA(bra) para o PagBank em 19/05/2026.
    'PagBank': {'fitch': 'AAA', 'moody': None, 'sp': None},
}

# Carregar dados crus do Yubb
if not os.path.exists(RAW_FILE):
    print(f"❌ Arquivo de dados crus não encontrado: {RAW_FILE}")
    print("   Rode primeiro: python3 scripts/scrape_yubb_fgc.py")
    exit(1)

with open(RAW_FILE, 'r', encoding='utf-8') as f:
    produtos_crus = json.load(f)

known_issuers = set(EMISSOR_ALIASES) | set(RATING_OVERRIDES) | UNRATED_ISSUERS | set(ratings_data)
unknown_issuers = sorted({
    str(produto.get('emissor', '')).strip()
    for produto in produtos_crus
    if produto.get('tem_fgc') and str(produto.get('emissor', '')).strip() not in known_issuers
})
if unknown_issuers:
    raise RuntimeError(
        'Emissores sem mapeamento exato de rating: ' + ', '.join(unknown_issuers)
    )

produtos_atualizados = []
novos_count = 0

def encontrar_rating(emissor):
    """Busca rating somente por emissor exato ou alias explicitamente validado."""
    if emissor in RATING_OVERRIDES:
        return RATING_OVERRIDES[emissor]
    if emissor in UNRATED_ISSUERS or not ratings_data:
        return None
    canonical = str(EMISSOR_ALIASES.get(emissor, emissor) or '')
    return ratings_data.get(canonical)

for produto in produtos_crus:
    # A página ranking_fgc.html deve exibir apenas produtos cobertos pelo FGC.
    if not produto.get('tem_fgc'):
        continue

    nome = produto['produto']
    
    if nome in historico:
        produto['data_primeira'] = historico[nome]
    else:
        produto['data_primeira'] = hoje_str
        historico[nome] = hoje_str
        novos_count += 1
    
    # Recalcular is_new
    data_primeira = datetime.strptime(produto['data_primeira'], '%Y-%m-%d')
    dias = (hoje - data_primeira).days
    produto['is_new'] = dias < 30
    
    # Mesclar rating
    emissor = produto.get('emissor', '')
    rating_info = encontrar_rating(emissor)
    if rating_info:
        # Priorizar: Fitch > Moody's > S&P (ou qualquer disponível)
        if rating_info.get('fitch') not in (None, '', '-', 'N/A'):
            produto['rating'] = rating_info['fitch']
        elif rating_info.get('moody') not in (None, '', '-', 'N/A'):
            produto['rating'] = rating_info['moody']
        elif rating_info.get('sp') not in (None, '', '-', 'N/A'):
            produto['rating'] = rating_info['sp']
        else:
            produto['rating'] = 'Sem rating público'
    else:
        produto['rating'] = 'Sem rating público'
    
    produtos_atualizados.append(produto)

# Ordenar por rentabilidade líquida
produtos_atualizados.sort(key=lambda x: float(x['rent_liquida'].replace('% a.a.', '').replace(',', '.')), reverse=True)
for i, p in enumerate(produtos_atualizados, 1):
    p['rank'] = i

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(produtos_atualizados, f, ensure_ascii=False, indent=2)

with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
    json.dump(historico, f, ensure_ascii=False, indent=2)

with open(TIMESTAMP_FILE, 'w', encoding='utf-8') as f:
    f.write(hoje_str)

if os.path.exists(PAGE_FILE):
    with open(PAGE_FILE, 'r', encoding='utf-8') as f:
        page = f.read()
    months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
              'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    label = f"{months[hoje.month - 1]}/{hoje.year}"
    date_br = hoje.strftime('%d/%m/%Y')
    page = re.sub(
        r'<p class="tagline"><strong>Atualização oficial:</strong> .*?</p>',
        f'<p class="tagline"><strong>Atualização oficial:</strong> {label} — publicado em {date_br}. Base validada: {len(produtos_atualizados)} produtos cobertos pelo FGC. Conteúdo educativo; não é recomendação de investimento.</p>',
        page,
        count=1,
    )
    page = re.sub(r'Última atualização: \d{2}/\d{2}/\d{4}', f'Última atualização: {date_br}', page, count=1)
    page = re.sub(r'scripts/fgc-dynamic\.js\?v=\d+', f'scripts/fgc-dynamic.js?v={hoje.strftime("%Y%m%d")}', page, count=1)
    with open(PAGE_FILE, 'w', encoding='utf-8') as f:
        f.write(page)

total = len(produtos_atualizados)
novos = sum(1 for p in produtos_atualizados if p['is_new'])

print(f"✅ Ranking atualizado em {hoje_str}")
print(f"📊 Total: {total} produtos")
print(f"🆕 Novos (primeira aparição < 30 dias): {novos}")
print(f"💾 Dados salvos em {OUTPUT_FILE}")
print(f"📜 Histórico salvo em {HISTORY_FILE}")
print(f"🕐 Timestamp: {TIMESTAMP_FILE}")
