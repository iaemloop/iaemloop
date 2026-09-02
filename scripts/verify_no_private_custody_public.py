#!/usr/bin/env python3
"""Fail if private custody/real-portfolio files are present in the public IA em Loop site.

Run before publishing GitHub Pages. Public site may keep methodologies, rankings,
blog posts and educational references, but must not publish real custody pages,
position ledgers, broker notes, or carteira*_real pages.
"""
from __future__ import annotations
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DENY_NAME_PARTS = (
    'carteira_besst_real',
    'carteira_magic_formula_real',
    'carteira_besst_buffett_dolarizada_real',
    'carteira_magic_formula_dolarizada_real',
    'investment_costs_2026',
    'dollarized_portfolios_2026',
    'real_portfolio_site_summary_2026',
    'compras_b3_',
    'compras_stocks_',
    'sobras_aportes_',
)
DENY_TEXT_PATTERNS = (
    'Carteira Real:',
    'Abrir carteira real',
    'total em custódia',
    'Valor comprado</div>',
    'Proventos recebidos</div>',
)
DENY_REGEX_PATTERNS = (
    re.compile(r'href=["\'][^"\']*carteira_[^"\']*_real\.html["\']', re.I),
    re.compile(r'url\([^)]*carteira_[^)]*_real\.html[^)]*\)', re.I),
)
IGNORE_DIRS = {'.git', '__pycache__', '.hermes', '.venv', '.nvm'}
violations: list[str] = []
for path in ROOT.rglob('*'):
    if any(part in IGNORE_DIRS for part in path.parts):
        continue
    rel = path.relative_to(ROOT).as_posix()
    if path.is_file() and any(part in rel for part in DENY_NAME_PARTS):
        violations.append(f'PRIVATE_FILE:{rel}')
    if path.suffix.lower() in {'.html', '.xml', '.md', '.json'}:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for pat in DENY_TEXT_PATTERNS:
            if pat in text:
                violations.append(f'PRIVATE_TEXT:{rel}:{pat}')
        for regex in DENY_REGEX_PATTERNS:
            if regex.search(text):
                violations.append(f'PRIVATE_LINK:{rel}:{regex.pattern}')
if violations:
    print('PUBLIC_CUSTODY_GUARD_FAILED')
    for v in violations:
        print(v)
    sys.exit(1)
print('PUBLIC_CUSTODY_GUARD_OK')
