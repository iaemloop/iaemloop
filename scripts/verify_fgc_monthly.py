#!/usr/bin/env python3
"""Valida a publicação mensal do ranking FGC contra a coleta Yubb."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(row: dict) -> tuple:
    return tuple(row.get(field) for field in (
        "produto", "emissor", "distribuidor", "tipo", "rent_liquida", "minimo", "prazo"
    ))


def rent(row: dict) -> float:
    return float(str(row["rent_liquida"]).replace("% a.a.", "").replace(",", "."))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="Mês no formato YYYY-MM")
    args = parser.parse_args()

    raw = load(DATA / "fgc_products_raw.json")
    final = load(DATA / "fgc_products.json")
    snapshot_raw = load(DATA / f"fgc_products_raw_{args.month}.json")
    snapshot_final = load(DATA / f"fgc_products_{args.month}.json")
    metadata = load(DATA / f"fgc_collection_{args.month}.json")
    summary = load(DATA / "fgc_summary.json")
    updated = (DATA / "last_updated.txt").read_text(encoding="utf-8").strip()

    assert raw == snapshot_raw, "snapshot bruto diverge do latest"
    assert final == snapshot_final, "snapshot final diverge do latest"
    assert len(raw) == len({identity(row) for row in raw}), "ofertas brutas duplicadas"
    eligible = [row for row in raw if row.get("tem_fgc")]
    assert {identity(row) for row in eligible} == {identity(row) for row in final}, "ofertas FGC perdidas ou acrescentadas"
    assert [row.get("rank") for row in final] == list(range(1, len(final) + 1)), "ranks não sequenciais"
    assert all(row.get("tem_fgc") for row in final), "produto sem FGC no ranking"
    assert all(row.get("rating") not in (None, "", "-", "N/A") for row in final), "rating vazio/N/A"
    assert all(row.get("distribuidor") and row.get("fonte") == "Yubb" and row.get("fonte_url") for row in final), "linhagem incompleta"
    assert [rent(row) for row in final] == sorted((rent(row) for row in final), reverse=True), "ordenação de rentabilidade inválida"
    assert len(final) > len({row["produto"] for row in final}), "ofertas homônimas foram colapsadas"

    assert metadata["ofertas_unicas"] == len(raw)
    assert metadata["ofertas_fgc"] == len(final)
    assert metadata["cards_encontrados"] >= len(raw)
    assert summary["total_produtos"] == len(final)
    assert summary["ratings_na"] == 0
    assert updated.startswith(args.month + "-")

    dt = datetime.strptime(updated, "%Y-%m-%d")
    label = f"{MONTHS_PT[dt.month - 1]}/{dt.year}"
    date_br = dt.strftime("%d/%m/%Y")
    expected_copy = f"{label} — publicado em {date_br}. Base validada: {len(final)} produtos cobertos pelo FGC."
    legacy = (ROOT / "ranking_fgc.html").read_text(encoding="utf-8")
    v2 = (ROOT / "v2" / "rankings" / "renda-fixa-fgc.html").read_text(encoding="utf-8")
    assert expected_copy in legacy and expected_copy in v2, "cópia mensal/count não atualizada nas páginas"
    assert "via ${distribuidor}" in (ROOT / "js" / "v2" / "fgc.js").read_text(encoding="utf-8")

    print(
        f"FGC_MONTHLY_OK month={args.month} raw={len(raw)} eligible={len(final)} "
        f"issuers={summary['total_emissores']} ratings_na={summary['ratings_na']}"
    )


if __name__ == "__main__":
    main()
