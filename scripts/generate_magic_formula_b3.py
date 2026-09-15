#!/usr/bin/env python3
"""Gera a fonte mensal da Magic Formula B3 a partir do Fundamentus.

A publicação não deve reutilizar silenciosamente o CSV de um mês anterior.
Este coletor baixa a tabela corrente, aplica os filtros quantitativos canônicos,
consolida classes da mesma empresa pela maior liquidez e grava o ranking bruto.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "greenblatt_top30.csv"
SOURCE_URL = "https://www.fundamentus.com.br/resultado.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": "https://www.fundamentus.com.br/",
}


def parse_percent(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    ) / 100


def fetch_table() -> pd.DataFrame:
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text), decimal=",", thousands=".")
    if len(tables) != 1 or len(tables[0]) < 100:
        raise RuntimeError("Tabela do Fundamentus ausente ou incompleta")
    return tables[0]


def build_ranking(df: pd.DataFrame) -> pd.DataFrame:
    required = {"Papel", "ROIC", "EV/EBIT", "Mrg Ebit", "Liq.2meses", "Patrim. Líq"}
    missing = required.difference(df.columns)
    if missing:
        raise RuntimeError(f"Colunas ausentes no Fundamentus: {sorted(missing)}")

    work = df.copy()
    work["ROIC"] = parse_percent(work["ROIC"])
    work["Mrg Ebit"] = parse_percent(work["Mrg Ebit"])
    for column in ("EV/EBIT", "Liq.2meses", "Patrim. Líq"):
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work = work[
        (work["ROIC"] > 0)
        & (work["EV/EBIT"] > 0)
        & (work["Mrg Ebit"] > 0)
        & (work["Liq.2meses"] >= 500_000)
        & (work["Patrim. Líq"] >= 1_000_000)
    ].copy()
    work["company"] = work["Papel"].str.extract(r"^([A-Z]{4})", expand=False)
    work = work.sort_values("Liq.2meses", ascending=False).drop_duplicates("company", keep="first")
    work["earnings_yield"] = 1 / work["EV/EBIT"]
    work["rank_roic"] = work["ROIC"].rank(ascending=False, method="min").astype(int)
    work["rank_ey"] = work["earnings_yield"].rank(ascending=False, method="min").astype(int)
    work["score"] = work["rank_roic"] + work["rank_ey"]
    work = work.sort_values(["score", "rank_roic", "rank_ey", "Papel"]).head(40).copy()
    work["rank_final"] = range(1, len(work) + 1)

    result = work.rename(columns={"Papel": "ticker", "ROIC": "roic"})[
        ["ticker", "roic", "earnings_yield", "rank_roic", "rank_ey", "score", "rank_final"]
    ]
    if len(result) < 30:
        raise RuntimeError(f"Ranking curto demais: {len(result)} linhas")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    ranking = build_ranking(fetch_table())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(args.output, index=False)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"Magic Formula B3 gerada: {len(ranking)} linhas; fonte={SOURCE_URL}; fetched_at={stamp}")
    print(ranking.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
