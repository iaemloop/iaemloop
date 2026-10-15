#!/usr/bin/env python3
"""Regression gate for semantic column alignment on public V2 rankings."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("v2build", ROOT / "v2/tools/build.py")
assert spec is not None and spec.loader is not None
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

EXPECTED_HEADERS = {
    "Pos": "center",
    "Rank": "center",
    "#": "center",
    "Ticker": "center",
    "Score": "center",
    "Score BESST": "center",
    "Empresa": "left",
    "Setor": "left",
    "Setor específico": "left",
    "Produto": "left",
    "Rating": "left",
    "Indexador": "left",
    "Tipo": "left",
    "Indústria": "left",
    "Observações": "left",
    "DY": "right",
    "DY%": "right",
    "P/VP": "right",
    "ROIC": "right",
    "ROIC proxy": "right",
    "ROE": "right",
    "EY": "right",
    "EV/EBIT": "right",
    "EV/EBITDA": "right",
    "P/L": "right",
    "Dividend Yield": "right",
    "Earnings Yield": "right",
    "FCF Yield": "right",
    "Rent. Bruta": "right",
    "Rent. Líquida": "right",
    "Mínimo": "right",
    "Prazo": "right",
    "Liq. 2 meses": "right",
}

for header, expected in EXPECTED_HEADERS.items():
    actual = build.ranking_column_alignment(header)
    assert actual == expected, (header, expected, actual)

ranking_routes = [
    route for route in build.ROUTES
    if route["target"].startswith(("rankings/", "radar/", "metodos/"))
]
assert ranking_routes
static_tables = static_rows = 0
for route in ranking_routes:
    path = ROOT / "v2" / route["target"]
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    page_classes = soup.body.get("class", [])
    assert "v2-ranking-page" in page_classes or "v2-tabular-page" in page_classes, path
    for table in soup.select(".v2-imported-content table"):
        static_tables += 1
        assert "v2-ranking-table" in table.get("class", []), (path, table.get("class"))
        headers = table.select("thead tr:first-child th")
        assert headers, path
        expected_classes = []
        for header in headers:
            expected = build.ranking_column_alignment(header.get_text(" ", strip=True))
            css_class = f"v2-align-{expected}"
            assert css_class in header.get("class", []), (path, header.get_text(" ", strip=True), header.get("class"))
            expected_classes.append(css_class)
        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) != len(expected_classes):
                continue
            static_rows += 1
            for cell, css_class in zip(cells, expected_classes):
                assert css_class in cell.get("class", []), (path, cell.get_text(" ", strip=True), css_class)

assert static_tables >= 20, static_tables
assert static_rows >= 400, static_rows

public_js = (ROOT / "js/v2/public.js").read_text(encoding="utf-8")
assert "MutationObserver" in public_js
assert "v2-ranking-page" in public_js
assert "v2-tabular-page" in public_js
assert "v2-align-center" in public_js and "v2-align-left" in public_js and "v2-align-right" in public_js

public_css = (ROOT / "css/v2/public.css").read_text(encoding="utf-8")
for alignment in ("center", "left", "right"):
    assert f".v2-ranking-table .v2-align-{alignment}" in public_css

methods_index = BeautifulSoup((ROOT / "v2/metodos/index.html").read_text(encoding="utf-8"), "html.parser")
assert not methods_index.select('a[href="/v2/metodos/watchlist-buffett.html"]')
watchlist_redirect = (ROOT / "v2/metodos/watchlist-buffett.html").read_text(encoding="utf-8")
assert 'content="noindex,nofollow,noarchive"' in watchlist_redirect
assert '/v2/radar/watchlist-buffett-eua.html' in watchlist_redirect
assert "/v2/metodos/watchlist-buffett.html" not in (ROOT / "v2/sitemap.xml").read_text(encoding="utf-8")

# Editorial tables are intentionally outside the ranking alignment contract.
editorial = BeautifulSoup(
    (ROOT / "v2/blog/posts/2026-09-02-analise-bmy-bristol-myers-pipeline-divida.html").read_text(encoding="utf-8"),
    "html.parser",
)
assert "v2-ranking-page" not in editorial.body.get("class", [])
assert not editorial.select("table.v2-ranking-table, .v2-align-center, .v2-align-left, .v2-align-right")

print(
    "V2_RANKING_ALIGNMENT_OK "
    f"routes={len(ranking_routes)} static_tables={static_tables} static_rows={static_rows} headers={len(EXPECTED_HEADERS)}"
)
