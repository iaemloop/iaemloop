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


def ticker_family(ticker: str) -> str:
    """Agrupa classes da mesma empresa: PETR3/PETR4 -> PETR; KLBN3/KLBN4 -> KLBN."""
    match = re.match(r"([A-Z]+)", ticker.strip().upper())
    return match.group(1) if match else ticker.strip().upper()


def load_rows() -> list[dict[str, str]]:
    # Regra IA em Loop: uma empresa só aparece uma vez.
    # Se duas classes/units surgirem no ranking bruto, fica o papel melhor ranqueado
    # pela própria ordenação do pipeline; as demais classes não contam como nova empresa.
    rows = []
    seen_families: set[str] = set()
    with CSV_IN.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            ticker = row.get("ticker", "").strip().upper()
            family = ticker_family(ticker)
            if family in seen_families:
                continue
            seen_families.add(family)
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
        r"Atualizado: \d{2}/\d{2}/\d{4}",
        f"Atualizado: {updated}",
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
