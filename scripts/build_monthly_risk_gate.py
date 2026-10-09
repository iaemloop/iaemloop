#!/usr/bin/env python3
"""Materializa o gate de publicação e de aporte dos rankings mensais."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def enrich(rows: list[dict[str, str]], sleeve: str, experiment: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    enriched = []
    for row in rows:
        item = dict(row)
        ticker = item.get("ticker", "").strip().upper()
        risk = experiment.get(ticker, {}) if sleeve == "magic-b3" else {}
        risk_veto = risk.get("risk_veto", "False").lower() == "true"
        warnings = int(float(risk.get("risk_warning_count") or 0))

        if sleeve == "besst-b3":
            market_cap = float(item.get("market_cap") or 0)
            item["fonte_universo"] = "pipeline BESST B3; setores perenes"
            item["liquidez_status"] = "checagem_operacional_pendente"
            item["tamanho_status"] = "aprovado" if market_cap >= 1_000_000_000 else "revisar"
            item["risco_estrutural_status"] = "revisao_corporativa_obrigatoria"
        elif sleeve == "magic-b3":
            item["fonte_universo"] = "Fundamentus; 652 registros; gate experimental 2026-10-09"
            item["liquidez_status"] = "aprovado_gate_2m_min_r500mil"
            item["tamanho_status"] = "aprovado_pl_min_r1milhao"
            item["risco_estrutural_status"] = "veto_experimental" if risk_veto else ("alerta_experimental" if warnings else "sem_alerta_experimental")
        else:
            item["fonte_universo"] = "universo IA em Loop EUA; 518 tickers; yfinance"
            item["liquidez_status"] = "proxy_universo_amplo; checagem_operacional_pendente"
            item["tamanho_status"] = "aprovado_market_cap_positivo_na_base"
            item["risco_estrutural_status"] = "revisao_corporativa_obrigatoria"

        item["publicacao_status"] = "publicavel_com_gate_separado"
        item["aporte_automatico"] = "nao"
        item["aporte_status"] = "bloqueado_por_veto_experimental" if risk_veto else "depende_de_dossie_e_decisao_mensal"
        item["gate_observacao"] = "Ranking educacional não constitui recomendação; aporte exige custódia, concentração, radar corporativo e aprovação humana."
        enriched.append(item)
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--experiment", required=True, type=Path)
    args = parser.parse_args()

    experiment_rows = read_csv(args.experiment)
    experiment = {row["ticker"].strip().upper(): row for row in experiment_rows}
    sources = {
        "besst-b3": ROOT / "outputs" / "barsi_screener_latest.csv",
        "magic-b3": ROOT / "greenblatt_top30_filtered.csv",
        "besst-usd": ROOT / "outputs" / f"besst_buffett_eua_top20_{args.month}.csv",
        "magic-usd": ROOT / "outputs" / f"magic_formula_eua_top20_{args.month}.csv",
    }
    all_rows = []
    summary = {"month": args.month, "automatic_contribution": False, "sleeves": {}}
    for sleeve, source in sources.items():
        rows = enrich(read_csv(source), sleeve, experiment)
        output = ROOT / "outputs" / f"risk_gate_{sleeve}_{args.month}.csv"
        write_csv(output, rows)
        blocked = sum(row["aporte_status"].startswith("bloqueado") for row in rows)
        summary["sleeves"][sleeve] = {"assets": len(rows), "blocked_for_contribution": blocked, "file": str(output.relative_to(ROOT))}
        for row in rows:
            all_rows.append({"sleeve": sleeve, **row})
    all_csv = ROOT / "outputs" / f"risk_gate_all_{args.month}.csv"
    write_csv(all_csv, all_rows)
    (ROOT / "outputs" / f"risk_gate_all_{args.month}.json").write_text(
        json.dumps({"month": args.month, "assets": all_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "outputs" / f"risk_gate_summary_{args.month}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
