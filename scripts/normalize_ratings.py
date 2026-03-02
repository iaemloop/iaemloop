#!/usr/bin/env python3
"""
Normaliza ratings removendo:
- Pontos (.)
- Plus (+)
- Sufixos 'br' ou 'bra' (case-insensitive)
- Ratings '0' ou '0 -'
Mantém apenas letras maiúsculas (A-Z) e barras (/) se houver.
"""

import json
import re
import sys

def normalize_rating(rating):
    """Normaliza um rating conforme as regras especificadas."""
    if rating is None or rating == "" or rating == "N/A":
        return "N/A"
    
    # Converter para string
    rating_str = str(rating).strip()
    
    # Remover '0 -' ou '0' no início
    rating_str = re.sub(r'^0\s*-\s*', '', rating_str)
    rating_str = re.sub(r'^0+$', '', rating_str)
    
    # Remover sufixos br/bra (case-insensitive) - tanto no final quanto entre parênteses
    rating_str = re.sub(r'\(?\s*(br|bra)\s*\)?$', '', rating_str, flags=re.IGNORECASE)
    
    # Remover prefixos BR/BRA (case-insensitive) no início
    rating_str = re.sub(r'^(br|bra)\s*', '', rating_str, flags=re.IGNORECASE)
    
    # Remover pontos e plus
    rating_str = rating_str.replace('.', '').replace('+', '')
    
    # Manter apenas letras maiúsculas A-Z e barra (/) se houver
    rating_str = re.sub(r'[^A-Z/]', '', rating_str.upper())
    
    # Se ficou vazio, retornar N/A
    if not rating_str:
        return "N/A"
    
    return rating_str

def normalize_ratings_json(filepath):
    """Lê o arquivo JSON, normaliza todos os ratings, e salva de volta."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Contador de mudanças
    changes = 0
    
    # Processar cada empresa
    for empresa, ratings in data.items():
        for agency in ['moody', 'fitch', 'sp']:
            if agency in ratings:
                old_val = ratings[agency]
                if old_val is not None and old_val != "" and old_val != "N/A":
                    new_val = normalize_rating(old_val)
                    if new_val != old_val:
                        ratings[agency] = new_val
                        changes += 1
                        # print(f"{empresa} - {agency}: {old_val} -> {new_val}")
    
    # Salvar de volta
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {filepath}: {changes} ratings normalizados")
    return changes

def normalize_fgc_products(filepath):
    """Normaliza o rating no fgc_products.json."""
    with open(filepath, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    changes = 0
    
    for product in products:
        if 'rating' in product:
            old_val = product['rating']
            if old_val is not None and old_val != "" and old_val != "N/A":
                new_val = normalize_rating(old_val)
                if new_val != old_val:
                    product['rating'] = new_val
                    changes += 1
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {filepath}: {changes} produtos com rating normalizado")
    return changes

if __name__ == "__main__":
    base_dir = '/Users/diegoteixeira/.openclaw/workspace/iaemloop-site'
    
    print("🔧 Normalizando ratings...")
    
    total_changes = 0
    total_changes += normalize_ratings_json(f'{base_dir}/data/ratings_bancos.json')
    total_changes += normalize_fgc_products(f'{base_dir}/data/fgc_products.json')
    
    print(f"\n✅ Total de mudanças: {total_changes}")
