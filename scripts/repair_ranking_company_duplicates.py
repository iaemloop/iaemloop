#!/usr/bin/env python3
"""Remove duplicate share classes/issuers from published rankings.

Keeps the best-ranked occurrence and renumbers each affected table. It never
combines fundamentals from different securities. Historical lists can contain
fewer than 20 entries when the archived source does not retain lower-ranked
replacement candidates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_FILES = [
    ROOT / "historico_rankings.html",
    ROOT / "historico_rankings_magic_formula.html",
    ROOT / "historico_rankings_dolarizados.html",
    ROOT / "historico_rankings_magic_formula_dolarizada.html",
]
CURRENT_BESST_USD = ROOT / "ranking_besst_buffett_dolarizado.html"
LATEST_BESST_USD = ROOT / "outputs" / "besst_buffett_eua_latest.json"
LATEST_BESST_USD_CSV = ROOT / "outputs" / "besst_buffett_eua_latest.csv"

ROW_RE = re.compile(r"<tr>.*?</tr>", re.S)
TICKER_RE = re.compile(r"(?:class=['\"]ticker['\"][^>]*>|<strong>|font-weight:\s*600[^>]*>)([A-Z]{1,6}(?:\d{1,2}|\.[A-Z])?)(?:</td>|</strong>)")
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub("", value)).strip()


def issuer_key(ticker: str, cells: list[str]) -> str:
    ticker = ticker.upper()
    if ticker in {"GOOG", "GOOGL"}:
        return "US:ALPHABET"
    # B3 numerical share classes and units belong to the same issuer.
    if re.fullmatch(r"[A-Z]{4,6}\d{1,2}", ticker):
        return "BR:" + re.match(r"[A-Z]+", ticker).group(0)
    # For US tables, the company name is the cell immediately after ticker.
    try:
        idx = next(i for i, c in enumerate(cells) if c == ticker)
        if idx + 1 < len(cells):
            company = cells[idx + 1].lower()
            company = re.sub(r"\b(class [a-z]|incorporated|inc\.?|corporation|company|plc|ltd\.?)\b.*$", "", company).strip(" ,.-")
            if company:
                return "US:" + company
    except StopIteration:
        pass
    return "T:" + ticker


def dedup_table(table: str) -> tuple[str, list[str]]:
    tbody_match = re.search(r"(<tbody[^>]*>)(.*?)(</tbody>)", table, re.S)
    if not tbody_match:
        return table, []
    body = tbody_match.group(2)
    rows = ROW_RE.findall(body)
    if not rows:
        return table, []
    kept: list[str] = []
    removed: list[str] = []
    seen: set[str] = set()
    rank = 0
    for row in rows:
        match = TICKER_RE.search(row)
        if not match:
            kept.append(row)
            continue
        ticker = match.group(1).upper()
        cells = [clean(x) for x in TD_RE.findall(row)]
        key = issuer_key(ticker, cells)
        if key in seen:
            removed.append(ticker)
            continue
        seen.add(key)
        rank += 1
        row = re.sub(r"(<td[^>]*>)(\d+)(</td>)", lambda m: f"{m.group(1)}{rank}{m.group(3)}", row, count=1)
        kept.append(row)
    if not removed:
        return table, []
    new_body = "\n".join(kept)
    return table[:tbody_match.start(2)] + new_body + table[tbody_match.end(2):], removed


def repair_html(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    removed: list[str] = []
    def repl(match: re.Match[str]) -> str:
        table, gone = dedup_table(match.group(0))
        removed.extend(gone)
        return table
    new = re.sub(r"<table(?:\s[^>]*)?>.*?</table>", repl, text, flags=re.S)
    if new != text:
        path.write_text(new, encoding="utf-8")
    return {"file": path.name, "removed": removed, "changed": new != text}


def repair_latest_json() -> dict:
    data = json.loads(LATEST_BESST_USD.read_text(encoding="utf-8"))
    seen: set[str] = set()
    kept = []
    removed = []
    for row in data.get("assets", []):
        ticker = str(row.get("ticker", "")).upper()
        key = "US:ALPHABET" if ticker in {"GOOG", "GOOGL"} else "T:" + ticker
        if key in seen:
            removed.append(ticker)
            continue
        seen.add(key)
        kept.append(row)
    data["assets"] = kept
    if removed:
        LATEST_BESST_USD.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"file": LATEST_BESST_USD.name, "removed": removed, "count": len(kept)}


def main() -> None:
    results = [repair_html(path) for path in HISTORY_FILES + [CURRENT_BESST_USD]]
    results.append(repair_latest_json())
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
