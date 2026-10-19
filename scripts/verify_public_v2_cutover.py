#!/usr/bin/env python3
"""Verify that V2 is the only canonical public IA em Loop experience."""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://iaemloop.com.br"
errors: list[str] = []


def soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


root = soup(ROOT / "index.html")
if not root.select_one(".v2-global-nav"):
    errors.append("root_home_not_v2")
root_canonical = root.find("link", rel="canonical")
if not root_canonical or root_canonical.get("href") != SITE + "/":
    errors.append("root_canonical_invalid")

v2_pages = sorted((ROOT / "v2").rglob("*.html"))
for page in v2_pages:
    parsed = soup(page)
    canonical = parsed.find("link", rel="canonical")
    if not canonical or not str(canonical.get("href", "")).startswith(SITE + "/"):
        errors.append(f"missing_canonical {page.relative_to(ROOT)}")

legacy_checks = {
    ROOT / "blog/index.html": "/v2/blog/index.html",
    ROOT / "blog/posts/2026-10-19-gddy-godaddy-infraestrutura-agentes-ia.html": "/v2/blog/posts/2026-10-19-gddy-godaddy-infraestrutura-agentes-ia.html",
    ROOT / "metodologia_barsi.html": "/v2/metodos/besst-buffett.html",
    ROOT / "greenblatt_ned_landing_original.html": "/v2/metodos/magic-formula.html",
    ROOT / "area_privada.html": "/v2/area-privada.html?redirect=/privado/v2/index.html",
}
for path, destination in legacy_checks.items():
    parsed = soup(path)
    robots = parsed.find("meta", attrs={"name": "robots"})
    refresh = parsed.find("meta", attrs={"http-equiv": lambda value: value and value.lower() == "refresh"})
    if not robots or "noindex" not in str(robots.get("content", "")).lower():
        errors.append(f"legacy_indexable {path.relative_to(ROOT)}")
    if not refresh or destination not in str(refresh.get("content", "")):
        errors.append(f"legacy_not_redirected {path.relative_to(ROOT)}")

classic_posts = len(list((ROOT / "blog/posts").glob("*.html")))
v2_posts = len(list((ROOT / "v2/blog/posts").glob("*.html")))
if classic_posts != v2_posts:
    errors.append(f"post_count classic={classic_posts} v2={v2_posts}")

sitemap = ROOT / "sitemap.xml"
try:
    xml = ET.parse(sitemap)
    locations = [node.text or "" for node in xml.findall(".//{*}loc")]
except Exception as exc:
    errors.append(f"sitemap_invalid {exc}")
    locations = []
if len(locations) != len(set(locations)):
    errors.append("sitemap_duplicates")
if SITE + "/" not in locations:
    errors.append("sitemap_missing_root")
for location in locations:
    path = urlparse(location).path
    if path == "/v2/index.html" or path.startswith(("/privado/", "/area_privada", "/blog/")):
        errors.append(f"sitemap_noncanonical {path}")
    if path != "/" and not path.startswith("/v2/"):
        errors.append(f"sitemap_legacy {path}")

if errors:
    print("PUBLIC_V2_CUTOVER_FAILED")
    for error in errors[:100]:
        print(error)
    if len(errors) > 100:
        print(f"... {len(errors) - 100} more")
    sys.exit(1)

print(f"PUBLIC_V2_CUTOVER_OK v2_html={len(v2_pages)} blog_posts={v2_posts} sitemap_urls={len(locations)}")
