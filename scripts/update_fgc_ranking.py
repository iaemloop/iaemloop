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
from datetime import datetime, timedelta

DATA_DIR = 'data'
RAW_FILE = os.path.join(DATA_DIR, 'fgc_products_raw.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'fgc_history.json')
RATINGS_FILE = os.path.join(DATA_DIR, 'ratings_bancos.json')
OUTPUT_FILE = os.path.join(DATA_DIR, 'fgc_products.json')
TIMESTAMP_FILE = os.path.join(DATA_DIR, 'last_updated.txt')

hoje = datetime.now()
hoje_str = hoje.strftime('%Y-%m-%d')

# Carregar histórico (mapeia nome_produto -> data_primeira)
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        historico = json.load(f)
else:
    historico = {}

# Carregar ratings de instituições (se disponível)
ratings_data = {}
if os.path.exists(RATINGS_FILE):
    with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
        ratings_data = json.load(f)
    print(f"✅ Ratings carregados: {len(ratings_data)} instituições")
else:
    print("⚠️  Ratings não encontrados. Campo 'rating' permanecerá 'N/A'")

# Carregar dados crus do Yubb
if not os.path.exists(RAW_FILE):
    print(f"❌ Arquivo de dados crus não encontrado: {RAW_FILE}")
    print("   Rode primeiro: python3 scripts/scrape_yubb_fgc.py")
    exit(1)

with open(RAW_FILE, 'r', encoding='utf-8') as f:
    produtos_crus = json.load(f)

produtos_atualizados = []
novos_count = 0

def encontrar_rating(emissor):
    """Busca rating para um emissor no dicionário de ratings"""
    if not ratings_data:
        return None
    # Busca exata
    if emissor in ratings_data:
        return ratings_data[emissor]
    # Busca case-insensitive e por substring comum
    emissor_lower = emissor.lower()
    for key, value in ratings_data.items():
        key_lower = key.lower()
        # Se o emissor contém a key ou vice-versa
        if emissor_lower in key_lower or key_lower in emissor_lower:
            return value
    return None

for produto in produtos_crus:
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
        if rating_info.get('fitch'):
            produto['rating'] = rating_info['fitch']
        elif rating_info.get('moody'):
            produto['rating'] = rating_info['moody']
        elif rating_info.get('sp'):
            produto['rating'] = rating_info['sp']
        else:
            # Usar o primeiro valor não nulo
            for val in rating_info.values():
                if val:
                    produto['rating'] = val
                    break
    else:
        produto['rating'] = 'N/A'
    
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

total = len(produtos_atualizados)
novos = sum(1 for p in produtos_atualizados if p['is_new'])

print(f"✅ Ranking atualizado em {hoje_str}")
print(f"📊 Total: {total} produtos")
print(f"🆕 Novos (primeira aparição < 30 dias): {novos}")
print(f"💾 Dados salvos em {OUTPUT_FILE}")
print(f"📜 Histórico salvo em {HISTORY_FILE}")
print(f"🕐 Timestamp: {TIMESTAMP_FILE}")
