#!/usr/bin/env python3
"""Reject private custody payloads from the publishable IA em Loop repository.

The guard scans deployable text, data, and source formats recursively. Exclusions are
limited to VCS metadata, local caches/environments, vendored dependency trees, and
this verifier source (which contains adversarial fixtures used by its self-test).
"""
from __future__ import annotations

import csv
import io
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

TEXT_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson",
    ".html", ".htm", ".xml", ".svg", ".md", ".vue", ".svelte",
    ".sql", ".txt", ".yaml", ".yml", ".toml", ".ini", ".conf", ".css",
}
IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".hermes", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", "node_modules", "vendor", "third_party",
}
DENY_NAME_PARTS = (
    "carteira_besst_real",
    "carteira_magic_formula_real",
    "carteira_besst_buffett_dolarizada_real",
    "carteira_magic_formula_dolarizada_real",
    "investment_costs_2026",
    "dollarized_portfolios_2026",
    "real_portfolio_site_summary_2026",
    "compras_b3_",
    "compras_stocks_",
    "sobras_aportes_",
    "update_real_carteiras_from_july_notes",
    "update_investment_cost_ledger_from_known_notes",
    "update_real_portfolio_pages_from_ledgers",
)
DENY_TEXT_PATTERNS = (
    "abrir carteira real",
    "total em custódia",
    "valor comprado</div>",
    "proventos recebidos</div>",
)
DENY_LINK_REGEXES = (
    re.compile(r"href=[\"'][^\"']*carteira_[^\"']*_real\.html[\"']", re.I),
    re.compile(r"url\([^)]*carteira_[^)]*_real\.html[^)]*\)", re.I),
)

ASSET_FIELDS = {"ticker", "symbol", "asset", "ativo"}
QUANTITY_FIELDS = {"quantity", "qtd", "shares", "units", "unidades"}
MONEY_FIELDS = {
    "price", "preco", "valor", "average_price_brl", "average_price_usd",
    "avg_price_brl", "avg_price_usd", "gross_value_brl", "gross_operations_brl",
    "gross_operations_usd", "executed_value_usd", "settlement_total_brl",
    "cost_total_brl", "cost_total_usd", "usd_received", "brl_sent",
    "commercial_rate_brl_per_usd", "vet_brl_per_usd", "spread_percent",
    "iof_percent", "dividend", "dividends", "dividends_usd", "proventos",
}
TRANSACTION_FIELDS = {
    "broker", "corretora", "portfolio", "carteira", "note_number",
    "nota_corretagem", "settlement_date", "trade_date", "execution_date",
    "fees", "costs", "brokerage_brl", "exchange_fees_brl", "iof_brl",
    "fx_spread_brl", "source_status",
}
ALL_SENSITIVE_FIELDS = ASSET_FIELDS | QUANTITY_FIELDS | MONEY_FIELDS | TRANSACTION_FIELDS

_LITERAL_FIELD_RE = re.compile(
    r"(?ix)(?:[\"'](?P<quoted>[a-z_][a-z0-9_]*)[\"']|\b(?P<bare>[a-z_][a-z0-9_]*)\b)"
    r"\s*(?::|=)\s*(?:[\"'][^\"'\r\n]{1,120}[\"']|[-+]?\d+(?:[.,]\d+)?)"
)
_TRADE_CALL_RE = re.compile(
    r"(?ix)\b(?:trade|holding|position)\s*\(\s*[\"'][A-Z]{1,6}\d{0,2}[\"']"
    r"\s*,\s*\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?"
)


def is_ignored(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    if path.resolve() == SELF:
        return True
    if any(part in IGNORE_DIRS for part in relative.parts):
        return True
    return False


def literal_sensitive_fields(text: str) -> set[str]:
    fields: set[str] = set()
    for match in _LITERAL_FIELD_RE.finditer(text):
        field = (match.group("quoted") or match.group("bare")).casefold()
        if field in ALL_SENSITIVE_FIELDS:
            fields.add(field)
    return fields


def has_structured_custody_payload(text: str) -> bool:
    fields = literal_sensitive_fields(text)
    has_asset = bool(fields & ASSET_FIELDS)
    has_quantity = bool(fields & QUANTITY_FIELDS)
    has_money = bool(fields & MONEY_FIELDS)
    has_transaction = bool(fields & TRANSACTION_FIELDS)
    if has_asset and has_quantity and has_money:
        return True
    if has_transaction and has_money and len(fields) >= 4:
        return True
    return _TRADE_CALL_RE.search(text) is not None


def delimited_has_custody_payload(text: str, delimiter: str) -> bool:
    try:
        rows = csv.reader(io.StringIO(text), delimiter=delimiter)
        header = next(rows, [])
    except (csv.Error, UnicodeError):
        return False
    fields = {cell.strip().casefold() for cell in header}
    has_asset = bool(fields & ASSET_FIELDS)
    has_quantity = bool(fields & QUANTITY_FIELDS)
    has_money = bool(fields & MONEY_FIELDS)
    has_transaction = bool(fields & TRANSACTION_FIELDS)
    return (has_asset and has_quantity and has_money) or (
        has_transaction and has_money and len(fields & ALL_SENSITIVE_FIELDS) >= 4
    )


def scan_tree(root: Path) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or is_ignored(path, root):
            continue
        rel_path = path.relative_to(root)
        # Handle minified file exemptions: only skip if in trusted directory
        if path.name.endswith(('.min.js', '.min.css')):
            if any(part in IGNORE_DIRS for part in rel_path.parts):
                continue  # skip minified files in trusted directories
            # else, do not skip; process normally
        relative = rel_path.as_posix()
        folded_relative = relative.casefold()
        folded_relative = relative.casefold()
        if any(part in folded_relative for part in DENY_NAME_PARTS):
            violations.append(f"PRIVATE_FILE:{relative}")
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        folded = text.casefold()
        if any(pattern in folded for pattern in DENY_TEXT_PATTERNS):
            violations.append(f"PRIVATE_TEXT:{relative}")
        if any(regex.search(text) for regex in DENY_LINK_REGEXES):
            violations.append(f"PRIVATE_LINK:{relative}")
        if has_structured_custody_payload(text):
            violations.append(f"PRIVATE_STRUCTURED_DATA:{relative}")
        suffix = path.suffix.casefold()
        delimiter = {".csv": ",", ".tsv": "\t"}.get(suffix)
        if delimiter and delimited_has_custody_payload(text, delimiter):
            label = "PRIVATE_CSV_DATA" if suffix == ".csv" else "PRIVATE_TSV_DATA"
            violations.append(f"{label}:{relative}")
    return sorted(set(violations))


def run_adversarial_tests() -> list[str]:
    """Prove supported deployable formats cannot carry private payloads."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="public-custody-guard-") as temp:
        root = Path(temp)
        clean = {
            "schema.py": "FIELDS = ('ticker', 'quantity', 'average_price_brl')\n",
            "security.js": "const allowedColumns = ['broker', 'note_number', 'fees'];\n",
            "template.csv": "ticker,company,sector\n",
            "maintenance.sh": "#!/bin/sh\nset -eu\nprintf '%s\\n' 'site maintenance'\n",
            "app.min.js": "(()=>{const e='public site';console.log(e)})();\n",
            "site.min.css": "html,body{margin:0;padding:0}body{font-family:sans-serif}\n",
        }
        for name, content in clean.items():
            (root / name).write_text(content, encoding="utf-8")
        if scan_tree(root):
            failures.append("self-test:clean schema/security fixtures were rejected")

        mutations = {
            "payload.py": (
                "positions = [{'ticker': 'TEST3', 'qtd': 7, "
                "'average_price_brl': 12.34, 'note_number': '987654321'}]\n"
            ),
            "payload.js": (
                "const holding = { ticker: 'TEST', quantity: 3, "
                "avg_price_usd: 45.67, broker: 'Example Broker' };\n"
            ),
            "payload.csv": (
                "ticker,quantity,average_price_brl,broker,note_number,settlement_date\n"
                "TEST3,7,12.34,Example Broker,987654321,2026-01-02\n"
            ),
            "payload.tsv": (
                "ticker\tquantity\taverage_price_brl\tbroker\tnote_number\n"
                "TEST3\t7\t12.34\tExample Broker\t987654321\n"
            ),
            "payload.sh": (
                "#!/bin/sh\nticker='TEST3'\nquantity=7\naverage_price_brl=12.34\n"
            ),
            "payload.min.js": (
                "const p={ticker:'TEST',quantity:3,avg_price_usd:45.67};\n"
            ),
            "payload.min.css": (
                ":root{ticker:'TEST';quantity:3;avg_price_usd:45.67}\n"
            ),
        }
        for name, content in mutations.items():
            path = root / name
            path.write_text(content, encoding="utf-8")
            findings = scan_tree(root)
            if not any(finding.endswith(name) for finding in findings):
                failures.append(f"self-test:{name} private payload was not rejected")
            path.unlink()
    return failures


def main() -> int:
    failures = run_adversarial_tests()
    violations = scan_tree(ROOT)
    if failures or violations:
        print("PUBLIC_CUSTODY_GUARD_FAILED")
        for failure in failures:
            print(failure)
        for violation in violations:
            print(violation)
        return 1
    print("PUBLIC_CUSTODY_GUARD_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
