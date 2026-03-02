#!/usr/bin/env python3
"""
Scraper da página de Renda Fixa do Yubb com paginação completa.
Extrai TODOS os produtos FGC de todas as páginas e gera data/fgc_products_raw.json.
"""

import requests
import json
import re
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ============================================
# CONFIGURAÇÃO
# ============================================
BASE_URL = "https://yubb.com.br/investimentos/renda-fixa"

# Parâmetros fixos da consulta
QUERY_PARAMS = {
    'ignore': 'cookies',
    'investment_type': 'renda-fixa',
    'months': '12',
    'principal': '5000.0',
    'sort_by': 'net_return'
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

DATA_DIR = 'data'
OUTPUT_RAW = os.path.join(DATA_DIR, 'fgc_products_raw.json')

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def build_url(page):
    """Constrói URL com parâmetros de consulta e página"""
    params = QUERY_PARAMS.copy()
    params['collection_page'] = page
    query = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{BASE_URL}?{query}"

def extrair_valor_monetario(texto):
    """Remove R$, espaços, e converte para float"""
    if not texto:
        return 0.0
    num = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try:
        return float(num)
    except:
        return 0.0

def extrair_rentabilidade(texto):
    """Extrai o número da rentabilidade (ex: '12,95% a.a.' → 12.95)"""
    if not texto:
        return 0.0
    match = re.search(r'([\d,]+)', texto)
    if match:
        return float(match.group(1).replace(',', '.'))
    return 0.0

def extrair_indexador(produto_nome):
    """Extrai o indexador do nome do produto"""
    nome = produto_nome.lower()
    if 'cdi' in nome:
        return 'CDI'
    elif 'ipca' in nome:
        return 'IPCA+'
    elif 'selic' in nome:
        return 'Selic'
    elif 'pré' in nome or 'prefixado' in nome:
        return 'Pré-Fixado'
    elif 'pós' in nome or 'pos' in nome:
        return 'Pós-Fixado'
    else:
        return 'CDI'  # default

def calcular_prazo_tipo(prazo_str):
    """Calcula o tipo de prazo a partir da data (DD/MM/YYYY)"""
    try:
        data_prazo = datetime.strptime(prazo_str, '%d/%m/%Y')
        hoje = datetime.now()
        diff = (data_prazo - hoje).days
        meses = diff // 30
        if meses <= 12:
            return 'Curto'
        elif meses <= 24:
            return 'Medio'
        else:
            return 'Longo'
    except:
        return 'Medio'

def extrair_produtos_de_html(html):
    """Extrai produtos de um HTML da página do Yubb"""
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all('article', class_='investmentCard')
    produtos = []
    
    for card in cards:
        # --- Tipo (LCA, LCI, CDB, etc.)
        classes = card.get('class', [])
        tipo = next((c for c in classes if c in ['lca', 'lci', 'cdb', 'lf', 'tesouro-direto']), 'cdb')
        
        # --- Produto
        h3 = card.select_one('.investmentCard__header h3')
        if h3 and h3.strong:
            produto_nome = h3.strong.get_text(strip=True)
        else:
            continue
        
        # Emissor (última linha da tabela)
        rows = card.select('.investmentCard__section tbody tr')
        if len(rows) >= 5:
            emissor = rows[4].td.get_text(strip=True) if rows[4].td else 'N/A'
        else:
            emissor = 'N/A'
        
        # Distribuidor (4ª linha)
        if len(rows) >= 4:
            distribuidor = rows[3].td.get_text(strip=True) if rows[3].td else 'N/A'
        else:
            distribuidor = 'N/A'
        
        # --- Rentabilidades
        if len(rows) >= 1:
            rent_liquida_text = rows[0].td.get_text(strip=True)
            rent_liquida = extrair_rentabilidade(rent_liquida_text)
            rent_bruta = rent_liquida  # FGC normalmente isento, então igual
        else:
            rent_liquida = 0.0
            rent_bruta = 0.0
        
        # --- Investimento mínimo
        if len(rows) >= 2:
            minimo_text = rows[1].td.get_text(strip=True)
            minimo = extrair_valor_monetario(minimo_text)
        else:
            minimo = 0.0
        
        # --- Prazo
        if len(rows) >= 3:
            prazo_cell = rows[2].td
            if prazo_cell:
                prazo_text = prazo_cell.get_text(strip=True)
                match = re.search(r'(\d{2}/\d{2}/\d{4})', prazo_text)
                if match:
                    prazo = match.group(1)
                else:
                    prazo = prazo_text
                prazo_tipo = calcular_prazo_tipo(prazo) if re.match(r'\d{2}/\d{2}/\d{4}', prazo) else 'Medio'
            else:
                prazo = ''
                prazo_tipo = 'Medio'
        else:
            prazo = ''
            prazo_tipo = 'Medio'
        
        # --- FGC
        fgc_badge = card.select_one('.certification__tag .text-success')
        tem_fgc = fgc_badge is not None
        
        # --- Indexador
        indexador = extrair_indexador(produto_nome)
        
        # Montar produto dict
        produto = {
            "produto": produto_nome,
            "emissor": emissor,
            "rating": "N/A",  # Não disponível no card do Yubb
            "indexador": indexador,
            "tipo": tipo.upper(),
            "rent_bruta": f"{rent_bruta:.2f}% a.a.",
            "rent_liquida": f"{rent_liquida:.2f}% a.a.",
            "minimo": f"R$ {minimo:,.2f}".replace(',', '.'),
            "prazo": prazo,
            "prazo_tipo": prazo_tipo,
            "tem_fgc": tem_fgc,
            "data_primeira": None,  # Será preenchido depois
            "is_new": False
        }
        produtos.append(produto)
    
    return produtos

def detectar_total_paginas(html):
    """Analisa a paginação e retorna o número total de páginas"""
    soup = BeautifulSoup(html, 'html.parser')
    # Procurar links de paginação: <a href="...collection_page=18">18</a>
    page_links = soup.find_all('a', href=re.compile(r'collection_page=\d+'))
    pages = []
    for link in page_links:
        try:
            page_num = int(re.search(r'collection_page=(\d+)', link['href']).group(1))
            pages.append(page_num)
        except:
            pass
    if pages:
        return max(pages)
    return 1  # fallback: só uma página

# ============================================
# SCRAPING PRINCIPAL
# ============================================

print(f"🔄 Buscando página 1...")
try:
    response = requests.get(build_url(1), headers=HEADERS, timeout=30)
    response.raise_for_status()
except Exception as e:
    print(f"❌ Erro ao acessar Yubb: {e}")
    exit(1)

# Detectar total de páginas
total_paginas = detectar_total_paginas(response.text)
print(f"✅ Total de páginas detectado: {total_paginas}")

# Coletar produtos de todas as páginas
todos_produtos = []

for pagina in range(1, total_paginas + 1):
    if pagina > 1:
        print(f"🔄 Buscando página {pagina}...")
        try:
            response = requests.get(build_url(pagina), headers=HEADERS, timeout=30)
            response.raise_for_status()
        except Exception as e:
            print(f"⚠️  Erro na página {pagina}: {e}. Pulando...")
            continue
    
    produtos_pagina = extrair_produtos_de_html(response.text)
    todos_produtos.extend(produtos_pagina)
    print(f"   → {len(produtos_pagina)} produtos encontrados (total acumulado: {len(todos_produtos)})")

# Remover duplicatas por nome de produto (o Yubb pode repetir entre páginas?)
vistos = set()
produtos_unicos = []
for p in todos_produtos:
    nome = p['produto']
    if nome not in vistos:
        vistos.add(nome)
        produtos_unicos.append(p)

print(f"\n✅ Total de produtos únicos: {len(produtos_unicos)}")

# Salvar dados crus
os.makedirs(DATA_DIR, exist_ok=True)
with open(OUTPUT_RAW, 'w', encoding='utf-8') as f:
    json.dump(produtos_unicos, f, ensure_ascii=False, indent=2)

print(f"📄 Dados salvos em {OUTPUT_RAW}")
print("⚠️  Lembre-se de rodar update_fgc_ranking.py para mesclar com histórico e gerar fgc_products.json")
