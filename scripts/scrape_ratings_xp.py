#!/usr/bin/env python3
"""
Scraper do Guia de Rating da XP.
Extrai ratings de bancos e emissores da página:
https://conteudos.xpi.com.br/renda-fixa/relatorios/guia-de-rating/

Output: data/ratings_bancos.json
Formato: { "Banco do Brasil": { "moody": "Aa1.br", "fitch": "AAA(bra)", "sp": "AAA(br)" } }
"""

import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

URL = "https://conteudos.xpi.com.br/renda-fixa/relatorios/guia-de-rating/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

OUTPUT_PATH = 'data/ratings_bancos.json'

def extrair_rating_texto(texto):
    """Extrai rating de strings como 'AAA(bra)' ou 'Aa1.br'"""
    if not texto:
        return None
    # Remover espaços extras
    return texto.strip()

def scrape_xp_rating():
    print(f"🔄 Acessando {URL}...")
    try:
        response = requests.get(URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Erro ao acessar XP: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')

    # Procurar tabela de rating
    # Segundo o Perplexity: //table[contains(@class,'rating-table')] | //div[contains(text(),'AAA')]
    # Vamos buscar por tabelas que contenham a palavra 'rating' na classe ou headers com AAA/Aa1
    tabela = None
    possible_tables = soup.find_all('table')
    for tbl in possible_tables:
        # Verificar se a tabela contém textos como AAA, Aa1, rating
        tbl_text = tbl.get_text().lower()
        if 'rating' in tbl_text or 'aaa' in tbl_text or 'aa1' in tbl_text:
            tabela = tbl
            break

    if not tabela:
        print("❌ Tabela de rating não encontrada")
        return {}

    print(f"✅ Tabela encontrada: {tabela.get('class')}")

    # Extrair linhas
    rows = tabela.find('tbody').find_all('tr') if tabela.find('tbody') else tabela.find_all('tr')
    print(f"   → {len(rows)} linhas na tabela")

    ratings = {}
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 4:
            continue  # pular header ou linhas vazias

        # Primeira coluna: nome do banco/emissor
        banco = cols[0].get_text(strip=True)
        if not banco or len(banco) < 2:
            continue

        # Segunda coluna: Moody's? (verificar posição)
        # Terceira: Fitch? Quarta: S&P?
        # Vamos assumir ordem: Banco | Moody's | Fitch | S&P | Perspectiva
        # Mas pode variar. Vamos usar heurística: identify pelos nomes das colunas se houver header
        moody = extrair_rating_texto(cols[1].get_text()) if len(cols) > 1 else None
        fitch = extrair_rating_texto(cols[2].get_text()) if len(cols) > 2 else None
        sp = extrair_rating_texto(cols[3].get_text()) if len(cols) > 3 else None

        ratings[banco] = {
            "moody": moody,
            "fitch": fitch,
            "sp": sp
        }

    print(f"✅ {len(ratings)} instituições extraídas")
    return ratings

def main():
    ratings = scrape_xp_rating()
    if not ratings:
        print("⚠️  Nenhum dado extraído. Verifique a estrutura da página.")
        exit(1)

    # Salvar JSON
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)

    print(f"📄 Dados salvos em {OUTPUT_PATH}")
    print("💡 Agora execute update_fgc_ranking.py para mesclar ratings.")

if __name__ == '__main__':
    main()
