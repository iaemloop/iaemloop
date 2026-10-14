#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Reject real-custody disclosures from generated public V2 articles."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "v2/blog/posts"
EXPLICIT_PRIVATE = re.compile(r"carteiras?(?: brasileiras?)? rea(?:l|is)|carteiras? rea(?:l|is)(?: brasileiras?)?|custódia real|aporte real", re.I)
CONTEXT = re.compile(
    r"carteiras? brasileiras? reais|carteiras? reais|preços? médios?.{0,70}carteiras?|carteiras?.{0,70}preços? médios?|custódia|posição (?:real|da carteira|na carteira)|carteira (?:magic formula|besst|dolarizada)",
    re.I,
)
DETAIL = re.compile(
    r"preço médio|custo (?:médio|unitário)|valor (?:executado|investido|comprado)|"
    r"peso (?:da|na) carteira|%\s+da carteira|\b\d+[\d.,]*\s*(?:ações|ação|unidades)\b|"
    r"\b(?:R\$|US\$)\s*[\d.,]+",
    re.I,
)
errors: list[str] = []

for page in sorted(POSTS.glob("*.html")):
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    article = soup.select_one(".v2-article-content")
    if not article:
        errors.append(f"missing_article {page.name}")
        continue
    full_text = " ".join(soup.stripped_strings)
    full_text += " " + " ".join(str(tag.get(attr, "")) for tag in soup.find_all(True) for attr in ("content", "title", "alt", "aria-label"))
    if re.search(r"proventos futuros mapeados|presença tanto na carteira|essa dupla confirmação", full_text, re.I):
        errors.append(f"custody_derived_fact {page.name}")
    for paragraph in article.select('p,li,tr'):
        text = paragraph.get_text(' ', strip=True)
        if re.search(r"BESST|Magic Formula", text, re.I) and re.search(r"\b\d+[\d.,]*\s*(?:ações|ação|unidades?)\b", text, re.I):
            errors.append(f"method_custody_units {page.name}")
    if EXPLICIT_PRIVATE.search(full_text):
        errors.append(f"explicit_private_custody {page.name}")
    for node in article.find_all(["p", "li", "tr", "div"]):
        text = " ".join(node.stripped_strings)
        if CONTEXT.search(text) and DETAIL.search(text):
            errors.append(f"custody_detail {page.name}: {text[:140]}")
            break
    for image in article.select("img[src]"):
        src = str(image["src"]).split("?", 1)[0]
        if src.startswith("/") and src.endswith(".svg"):
            asset = ROOT / src.lstrip("/")
            asset_soup = BeautifulSoup(asset.read_text(encoding="utf-8"), "xml")
            asset_text = " ".join(asset_soup.stripped_strings)
            if EXPLICIT_PRIVATE.search(asset_text) or re.search(r"custódia|compra real|preço médio|\bPM\b|\d+[\d.,]*\s*(?:ações|ação|unidades)", asset_text, re.I):
                errors.append(f"private_referenced_asset {page.name}: {src}")
    metadata = " ".join(str(tag.get(attr, "")) for tag in soup.find_all(True) for attr in ("content", "title", "alt", "aria-label"))
    if CONTEXT.search(metadata) and DETAIL.search(metadata):
        errors.append(f"private_metadata {page.name}")
    serialized = str(article)
    if "投入" in serialized or "o papéis está" in serialized:
        errors.append(f"editorial_corruption {page.name}")

if errors:
    print("V2_PUBLIC_PRIVACY_FAILED")
    print("\n".join(errors[:100]))
    sys.exit(1)

print(f"V2_PUBLIC_PRIVACY_OK posts={len(list(POSTS.glob('*.html')))}")
