#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Validate generated V2 routes, links and isolation boundaries."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "v2"
ROUTE_MAP = json.loads((V2 / "content/route-map.json").read_text(encoding="utf-8"))
EXPECTED_POSTS = len(list((ROOT / "blog/posts").glob("*.html")))
errors: list[str] = []

if ROUTE_MAP.get("blog_posts") != EXPECTED_POSTS:
    errors.append(f"blog_posts={ROUTE_MAP.get('blog_posts')} expected={EXPECTED_POSTS}")
generated_posts = len(list((V2 / "blog/posts").glob("*.html")))
if generated_posts != EXPECTED_POSTS:
    errors.append(f"generated_blog_posts={generated_posts} expected={EXPECTED_POSTS}")

pages = sorted(V2.rglob("*.html"))
for page in pages:
    text = page.read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    rel = page.relative_to(ROOT).as_posix()
    if page.name != "area-privada.html":
        if not soup.select_one(".v2-global-nav"):
            errors.append(f"missing_global_nav {rel}")
        if len(soup.find_all("main")) != 1:
            errors.append(f"main_count={len(soup.find_all('main'))} {rel}")
    if re.search(r"fetch\((['\"])(?:\./|\.\./)*data/", text):
        errors.append(f"relative_fetch {rel}")
    for tag in soup.find_all(True):
        for attr in ("href", "src"):
            value = tag.get(attr)
            if not value or value.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "http://", "https://", "//")):
                continue
            parsed = urlparse(value)
            if not parsed.path.startswith("/"):
                errors.append(f"relative_{attr} {rel} -> {value}")
                continue
            target = parsed.path
            if target.startswith("/privado/v2/"):
                continue
            candidate = ROOT / target.lstrip("/")
            if target.endswith("/"):
                candidate = candidate / "index.html"
            if not candidate.exists():
                errors.append(f"broken_{attr} {rel} -> {target}")
            if attr == "href" and target.endswith(".html") and not target.startswith(("/v2/", "/privado/v2/")):
                # Imported editorial citations may point outside the IA em Loop site only via absolute URLs.
                if target in ROUTE_MAP.get("source_map", {}) or target.startswith("/blog/"):
                    errors.append(f"legacy_internal_link {rel} -> {target}")

if errors:
    print("V2_ROUTE_VALIDATION_FAILED")
    for error in errors[:100]:
        print(error)
    if len(errors) > 100:
        print(f"... {len(errors)-100} more")
    sys.exit(1)

print(f"V2_ROUTE_VALIDATION_OK html={len(pages)} generated={len(ROUTE_MAP['routes'])} blog_posts={ROUTE_MAP['blog_posts']}")
