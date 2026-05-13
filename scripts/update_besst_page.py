#!/usr/bin/env python3
"""
Atualiza metodologia_barsi.html com o resultado mais recente do pipeline BESST.
"""

from __future__ import annotations

import csv
import html
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "metodologia_barsi.html"
CSV_IN = ROOT / "outputs" / "barsi_screener_latest.csv"

SECTOR_TRANSLATION = {
    "Energy": "Petróleo/Gás",
    "Utilities": "Energia",
    "Basic Materials": "Materiais básicos",
    "Financial Services": "Bancos",
    "Communication Services": "Telecomunicações",
}


def sector_pt(raw: str, segment: str) -> str:
    if "Bank" in segment:
        return "Bancos"
    if "Electric" in segment or raw == "Utilities":
        return "Energia"
    if "Oil" in segment or raw == "Energy":
        return "Petróleo/Gás"
    if "Paper" in segment:
        return "Papel e Celulose"
    if "Steel" in segment:
        return "Mineração/Siderurgia"
    return SECTOR_TRANSLATION.get(raw, raw or "-")


def fmt_percent(value: str) -> str:
    try:
        return f"{float(value):.1f}%"
    except ValueError:
        return "-"


def fmt_num(value: str) -> str:
    try:
        return f"{float(value):.2f}"
    except ValueError:
        return "-"


def ticker_link(ticker: str) -> str:
    escaped = html.escape(ticker)
    href = f"https://www.fundamentus.com.br/detalhes.php?papel={escaped}"
    return f'<a href="{href}" target="_blank" rel="noopener noreferrer"><strong>{escaped}</strong> 🔗</a>'


def load_rows() -> list[dict[str, str]]:
    rows = []
    with CSV_IN.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            rows.append(row)
    return rows


def build_tbody(rows: list[dict[str, str]]) -> str:
    html_rows = []
    for pos, row in enumerate(rows, 1):
        ticker = row["ticker"].strip().upper()
        sector = sector_pt(row.get("setor", ""), row.get("segmento", ""))
        html_rows.append(
            f"""                <tr>
                    <td><strong>{pos}</strong></td>
                    <td>{ticker_link(ticker)}</td>
                    <td>{html.escape(sector)}</td>
                    <td class="">{fmt_percent(row.get("dividend_yield", ""))}</td>
                    <td>{fmt_num(row.get("p_vpa", ""))}</td>
                    <td class="">-</td>
                    <td>{fmt_num(row.get("score", ""))}</td>
                </tr>"""
        )
    return "\n".join(html_rows)


def main() -> None:
    page_html = PAGE.read_text(encoding="utf-8")
    rows = load_rows()
    updated = datetime.now().strftime("%d/%m/%Y")
    page_html = re.sub(
        r"<p>📅 <strong>Atualização:</strong> .*?</p>",
        f'<p>📅 <strong>Atualização:</strong> {updated}</p>',
        page_html,
        count=1,
    )
    page_html = re.sub(
        r"<tbody>.*?</tbody>",
        f"<tbody>\n{build_tbody(rows)}\n                </tbody>",
        page_html,
        count=1,
        flags=re.S,
    )
    PAGE.write_text(page_html, encoding="utf-8")
    print(f"BESST atualizado com {len(rows)} linhas.")


if __name__ == "__main__":
    main()
