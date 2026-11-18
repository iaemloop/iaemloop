#!/usr/bin/env python3
"""Importa os quatro rankings canônicos para os artefatos de publicação do site."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

B3_SECTOR = {
    "BBDC4": ("Financial Services", "Banks - Regional"),
    "PETR4": ("Energy", "Oil & Gas Integrated"),
    "SANB11": ("Financial Services", "Banks - Regional"),
    "GGBR4": ("Basic Materials", "Steel"),
    "VALE3": ("Basic Materials", "Other Industrial Metals & Mining"),
    "VIVT3": ("Communication Services", "Telecom Services"),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def write_rows(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_csv(source: Path, destination: Path) -> None:
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if not fieldnames:
        raise RuntimeError(f"CSV canônico sem cabeçalho: {source}")
    write_rows(destination, fieldnames, rows)


def import_besst_b3(source: Path, month: str) -> None:
    rows = read_rows(source)
    converted = []
    for row in rows:
        ticker = row["ticker"].strip().upper()
        sector, segment = B3_SECTOR.get(ticker, (row["atividade_economica"], row["atividade_economica"]))
        converted.append({
            "ticker": ticker,
            "nome": row["empresa"],
            "setor": sector,
            "segmento": segment,
            "classificacao_setor": "PERENE",
            "preco": row["preco_brl"],
            "market_cap": row["market_cap_brl"],
            "dividend_yield": row["dividend_yield_pct"],
            "dividend_rate": "",
            "p_vpa": row["p_vpa"],
            "p_l": row["p_l"],
            "anos_listed": row["anos_listado_min"],
            "anos_com_dividendos": row["anos_com_dividendos"],
            "score": row["score"],
        })
    fields = list(converted[0])
    latest = ROOT / "outputs" / "barsi_screener_latest.csv"
    monthly = ROOT / "outputs" / f"barsi_screener_{month}.csv"
    write_rows(latest, fields, converted)
    write_rows(monthly, fields, converted)


def import_magic_b3(source: Path, month: str) -> None:
    rows = read_rows(source)
    converted = []
    for row in rows:
        converted.append({
            "pos": row["rank"],
            "ticker": row["ticker"].strip().upper(),
            "setor": row["atividade_economica"],
            "roic": f'{float(row["roc_pct"]) / 100:.8f}',
            "ey": f'{float(row["earnings_yield_pct"]) / 100:.8f}',
            "ev_ebit": f'{float(row["ev_ebit"]):.2f}',
            "dy": "-",
            "score": row["score_magic"],
        })
    fields = list(converted[0])
    write_rows(ROOT / "greenblatt_top30_filtered.csv", fields, converted)
    write_rows(ROOT / "outputs" / f"magic_formula_b3_top20_{month}.csv", fields, converted)


def import_besst_us(source: Path, month: str) -> None:
    rows = read_rows(source)
    converted = []
    for row in rows:
        converted.append({
            "rank": row["rank"],
            "ticker": row["ticker"],
            "empresa": row["empresa"],
            "setor": row["setor"],
            "industria": row["atividade_economica"],
            "pl": row["p_l"],
            "ev_ebitda": "",
            "roe_pct": row["roe_pct"],
            "margem_operacional_pct": "",
            "fcf_yield_pct": "",
            "dividend_yield_pct": row["dividend_yield_pct"],
            "score_qualidade": "",
            "score_perenidade": "",
            "score_seguranca": "",
            "score_valuation": "",
            "score_total": row["score"],
            "fonte_dados": row["fonte"],
            "data_base": row["data_base"],
            "observacoes": "Ranking quantitativo mensal; não equivale a recomendação de aporte.",
        })
    write_rows(ROOT / "outputs" / f"besst_buffett_eua_top20_{month}.csv", list(converted[0]), converted)


def import_magic_us(source: Path, month: str) -> None:
    rows = read_rows(source)
    converted = []
    for row in rows:
        converted.append({
            "rank": row["rank"],
            "ticker": row["ticker"],
            "empresa": row["empresa"],
            "setor": row["setor"],
            "industria": row["atividade_economica"],
            "pl": "",
            "ev_ebitda": "",
            "roic_proxy_pct": row["roc_pct"],
            "earnings_yield_pct": row["earnings_yield_pct"],
            "ebitda_yield_pct": "",
            "fcf_yield_pct": "",
            "rank_qualidade": row["rank_roc"],
            "rank_preco": row["rank_earnings_yield"],
            "rank_fcf": "",
            "score_total": row["score_magic"],
            "fonte_dados": row["fonte"],
            "fonte_universo": "universo mensal IA em Loop",
            "data_base": row["data_base_preco"],
            "filtro_metodologico": "aprovado",
            "criterio_filtro": "ranking por retorno sobre capital e earnings yield",
            "risco_estrutural_status": "revisao_editorial_obrigatoria",
            "observacoes": "Ranking quantitativo mensal; não equivale a recomendação de aporte.",
        })
    write_rows(ROOT / "outputs" / f"magic_formula_eua_top20_{month}.csv", list(converted[0]), converted)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--month", default="2026-11")
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    names = {
        "besst_b3": source_dir / f"01_besst_buffett_b3_{args.month}.csv",
        "magic_b3": source_dir / f"02_magic_formula_b3_{args.month}.csv",
        "besst_us": source_dir / f"03_besst_buffett_stocks_{args.month}.csv",
        "magic_us": source_dir / f"04_magic_formula_stocks_{args.month}.csv",
    }
    missing = [str(path) for path in names.values() if not path.exists()]
    if missing:
        raise SystemExit("Arquivos canônicos ausentes: " + ", ".join(missing))

    canonical_dir = ROOT / "outputs" / "canonical" / args.month
    canonical_dir.mkdir(parents=True, exist_ok=True)
    for path in names.values():
        destination = canonical_dir / path.name
        if path.resolve() != destination.resolve():
            normalize_csv(path, destination)

    import_besst_b3(names["besst_b3"], args.month)
    import_magic_b3(names["magic_b3"], args.month)
    import_besst_us(names["besst_us"], args.month)
    import_magic_us(names["magic_us"], args.month)
    print(f"Rankings canônicos {args.month} importados: 4 carteiras.")


if __name__ == "__main__":
    main()
