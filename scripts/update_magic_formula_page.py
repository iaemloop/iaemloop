#!/usr/bin/env python3
"""
Atualiza a página Magic Formula com as regras editoriais do IA em Loop.

Regras obrigatórias:
- não incluir varejo;
- não incluir aviação/companhias aéreas;
- mostrar setor no ranking;
- deixar tickers clicáveis;
- publicar somente o Top 20 final. O CSV bruto pode ter 30 nomes, mas o site,
  o CSV filtrado e o histórico público da IA em Loop devem parar em 20.

O script usa o CSV bruto quando disponível, aplica as regras e reescreve a seção
do ranking. Se o CSV bruto não existir, usa a tabela HTML existente como fallback.
"""

from __future__ import annotations

import csv
import html
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "greenblatt_ned_landing_original.html"
CSV_IN = ROOT / "greenblatt_top30.csv"
CSV_OUT = ROOT / "greenblatt_top30_filtered.csv"


SECTOR_BY_TICKER = {
    "ANIM3": "Educação",
    "ASAI3": "Varejo",
    "AZUL4": "Aviação",
    "BEEF3": "Alimentos",
    "BRBI11": "Bancos",
    "BRAV3": "Petróleo/Gás",
    "CASH3": "Serviços financeiros",
    "CEAB3": "Varejo",
    "CMIN3": "Mineração",
    "CSED3": "Educação",
    "CSUD3": "Tecnologia/Serviços",
    "EUCA4": "Papel e madeira",
    "GMAT3": "Varejo",
    "GOLL4": "Aviação",
    "LEVE3": "Autopeças",
    "LREN3": "Varejo",
    "MILS3": "Máquinas/Equipamentos",
    "MOVI3": "Locação de veículos",
    "ODPV3": "Saúde/Odontologia",
    "PETR3": "Petróleo/Gás",
    "PETR4": "Petróleo/Gás",
    "PLPL3": "Construção civil",
    "POMO3": "Autopeças",
    "POMO4": "Autopeças",
    "PSSA3": "Seguros",
    "QUAL3": "Saúde",
    "RANI3": "Papel e celulose",
    "RECV3": "Petróleo/Gás",
    "SEER3": "Educação",
    "TGMA3": "Logística",
    "VALE3": "Mineração",
    "VAMO3": "Locação/Logística",
    "VLID3": "Tecnologia/Identificação",
    "VTRU3": "Educação",
    "WIZC3": "Seguros/Corretagem",
}

EXCLUDED_TICKERS = {
    "AMER3",
    "ASAI3",
    "AZUL4",
    "CEAB3",
    "GMAT3",
    "GOLL4",
    "LREN3",
    "MGLU3",
    "SBFG3",
    "VIIA3",
    "VIVA3",
}

EXCLUDED_SECTOR_WORDS = (
    "varejo",
    "retail",
    "aviação",
    "aviacao",
    "aérea",
    "aerea",
    "airline",
)


def fundamentus_link(ticker: str) -> str:
    return f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"


def is_excluded(ticker: str, sector: str) -> bool:
    normalized = sector.lower()
    return ticker in EXCLUDED_TICKERS or any(word in normalized for word in EXCLUDED_SECTOR_WORDS)


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def extract_rows(page_html: str) -> list[dict[str, str]]:
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", page_html, flags=re.S)
    if not tbody_match:
        raise RuntimeError("Tabela do ranking não encontrada")

    rows = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", tbody_match.group(1), flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S)
        if len(cells) < 7:
            continue
        ticker = strip_tags(cells[1])
        if len(cells) >= 8:
            roic_index = 3
            ey_index = 4
            ev_ebit_index = 5
            dy_index = 6
            score_index = 7
        else:
            roic_index = 2
            ey_index = 3
            ev_ebit_index = 4
            dy_index = 5
            score_index = 6
        rows.append(
            {
                "pos": strip_tags(cells[0]),
                "ticker": ticker,
                "setor": SECTOR_BY_TICKER.get(ticker, "Não classificado"),
                "roic": strip_tags(cells[roic_index]),
                "ey": strip_tags(cells[ey_index]),
                "ev_ebit": strip_tags(cells[ev_ebit_index]),
                "dy": strip_tags(cells[dy_index]),
                "score": strip_tags(cells[score_index]),
            }
        )
    return rows


def rows_from_csv() -> list[dict[str, str]]:
    if not CSV_IN.exists():
        return []
    rows = []
    with CSV_IN.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            ticker = row.get("ticker", "").strip().upper()
            if not ticker:
                continue
            sector = SECTOR_BY_TICKER.get(ticker, "Não classificado")
            if is_excluded(ticker, sector):
                continue
            try:
                roic = float(row.get("roic", 0) or 0)
            except ValueError:
                roic = 0
            try:
                ey = float(row.get("earnings_yield", 0) or 0)
            except ValueError:
                ey = 0
            ev_ebit = (1 / ey) if ey else None
            rows.append(
                {
                    "pos": row.get("rank_final", ""),
                    "ticker": ticker,
                    "setor": sector,
                    "roic": f"{roic * 100:.2f}%",
                    "ey": f"{ey * 100:.2f}%",
                    "ev_ebit": f"{ev_ebit:.2f}" if ev_ebit else "-",
                    "dy": "-",
                    "score": row.get("score", ""),
                }
            )
    return rows


def cell(content: str, align: str = "center", color: str | None = None, weight: str | None = None) -> str:
    style = f"text-align: {align}; padding: 0.6rem 0.3rem;"
    if color:
        style += f" color: {color};"
    if weight:
        style += f" font-weight: {weight};"
    return f'<td style="{style}">{content}</td>'


def build_rows(rows: list[dict[str, str]]) -> str:
    rendered = []
    for pos, row in enumerate(rows, 1):
        ticker = html.escape(row["ticker"])
        sector = html.escape(row["setor"])
        ticker_link = (
            f'<a href="{fundamentus_link(ticker)}" target="_blank" rel="noopener noreferrer">'
            f"<strong>{ticker}</strong></a>"
        )
        rendered.append(
            "                <tr>\n"
            f'                    {cell(str(pos), color="#E4D17F", weight="700")}\n'
            f'                    {cell(ticker_link, color="#AA8451", weight="600")}\n'
            f'                    {cell(sector, align="left")}\n'
            f'                    {cell(html.escape(row["roic"]), align="right", color="#10b981")}\n'
            f'                    {cell(html.escape(row["ey"]), align="right")}\n'
            f'                    {cell(html.escape(row["ev_ebit"]), align="right")}\n'
            f'                    {cell(html.escape(row["dy"]), align="right")}\n'
            f'                    {cell(html.escape(row["score"]), color="#E4D17F", weight="600")}\n'
            "                </tr>"
        )
    return "\n".join(rendered)


def replace_table(page_html: str, rows: list[dict[str, str]]) -> str:
    updated = datetime.now().strftime("%d/%m/%Y")
    page_html = re.sub(
        r"📅 <strong>Atualização:</strong> \d{2}/\d{2}/\d{4}",
        f"📅 <strong>Atualização:</strong> {updated}",
        page_html,
        count=1,
    )
    page_html = re.sub(
        r"Atualizado: \d{2}/\d{2}/\d{4}",
        f"Atualizado: {updated}",
        page_html,
        count=1,
    )
    top20 = rows[:20]
    page_html = re.sub(
        r"Dados: Fundamentus \+ yfinance \(.*?\)\. Setores: classificação B3 oficial\. \d+ empresas \(duplicata removida\)\.|Dados: Fundamentus \+ yfinance \(.*?\)\. Setores: classificação IA em Loop\. \d+ empresas após filtros de varejo e aviação\.",
        f"Dados: Fundamentus + yfinance ({updated}). Setores: classificação IA em Loop. Top 20 após filtros de varejo e aviação.",
        page_html,
        count=1,
    )
    page_html = re.sub(
        r"<colgroup>.*?</colgroup>",
        """<colgroup>
    <col style="width: 60px">
    <col style="width: 90px">
    <col style="width: 150px">
    <col style="width: 80px">
    <col style="width: 80px">
    <col style="width: 80px">
    <col style="width: 70px">
    <col style="width: 60px">
</colgroup>""",
        page_html,
        count=1,
        flags=re.S,
    )
    page_html = re.sub(
        r"<thead>.*?</thead>",
        """<thead>
                    <tr style="background: rgba(25,54,77,0.3);">
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: center; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">Pos</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: center; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">Ticker</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: left; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">Setor</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: right; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">ROIC</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: right; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">EY</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: right; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">EV/EBIT</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: right; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">DY%</th>
                        <th style="padding: 0.6rem 0.3rem; color: #E4D17F; font-weight: 600; text-align: center; border-bottom: 1px solid rgba(228, 209, 127, 0.15); font-size: 0.8rem;">Score</th>
                    </tr>
                </thead>""",
        page_html,
        count=1,
        flags=re.S,
    )
    return re.sub(
        r"<tbody>.*?</tbody>",
        f"<tbody>\n{build_rows(top20)}\n                </tbody>",
        page_html,
        count=1,
        flags=re.S,
    )


def update_csv(rows: list[dict[str, str]]) -> None:
    if not CSV_IN.exists():
        return
    with CSV_IN.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        csv_rows = []
        for row in reader:
            ticker = row.get("ticker", "").strip().upper()
            sector = SECTOR_BY_TICKER.get(ticker, "Não classificado")
            if is_excluded(ticker, sector):
                continue
            row["setor"] = sector
            csv_rows.append(row)
            if len(csv_rows) >= 20:
                break
    if not csv_rows:
        return
    fieldnames = list(csv_rows[0].keys())
    with CSV_OUT.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


def main() -> None:
    page_html = PAGE.read_text(encoding="utf-8")
    rows = rows_from_csv() or extract_rows(page_html)
    filtered = [row for row in rows if not is_excluded(row["ticker"], row["setor"])]
    top20 = filtered[:20]
    PAGE.write_text(replace_table(page_html, top20), encoding="utf-8")
    update_csv(top20)
    removed = len(rows) - len(filtered)
    truncated = max(0, len(filtered) - len(top20))
    print(f"Magic Formula atualizada: {len(top20)} linhas publicadas (Top 20), {removed} excluídas, {truncated} excedentes fora do site.")


if __name__ == "__main__":
    main()
