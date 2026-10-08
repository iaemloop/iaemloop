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
EXPLICIT_PRIVATE = re.compile(r"carteira real|custódia real|aporte real", re.I)
CONTEXT = re.compile(
    r"custódia|posição (?:real|da carteira|na carteira)|carteira (?:magic formula|besst|dolarizada)",
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
    full_text = " ".join(article.stripped_strings)
    if EXPLICIT_PRIVATE.search(full_text):
        errors.append(f"explicit_private_custody {page.name}")
    for node in article.find_all(["p", "li", "tr", "div"]):
        text = " ".join(node.stripped_strings)
        if CONTEXT.search(text) and DETAIL.search(text):
            errors.append(f"custody_detail {page.name}: {text[:140]}")
            break
    serialized = str(article)
    if "投入" in serialized or "o papéis está" in serialized:
        errors.append(f"editorial_corruption {page.name}")

if errors:
    print("V2_PUBLIC_PRIVACY_FAILED")
    print("\n".join(errors[:100]))
    sys.exit(1)

print(f"V2_PUBLIC_PRIVACY_OK posts={len(list(POSTS.glob('*.html')))}")
