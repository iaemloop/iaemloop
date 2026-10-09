#!/usr/bin/env python3
"""Gera transparência operacional e concentração do ranking FGC."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fgc_products.json"
SUMMARY = ROOT / "data" / "fgc_summary.json"

rows = json.loads(DATA.read_text(encoding="utf-8"))
for row in rows:
    row.setdefault("carencia", None)
    row.setdefault("liquidez", None)
    row["dados_operacionais_status"] = "carencia_e_liquidez_nao_informadas_pela_fonte"
DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

counts = Counter(row.get("emissor") or "Não informado" for row in rows)
rating_na = sum((row.get("rating") or "N/A") == "N/A" for row in rows)
summary = {
    "total_produtos": len(rows),
    "total_emissores": len(counts),
    "maior_concentracao": {
        "emissor": counts.most_common(1)[0][0] if counts else None,
        "produtos": counts.most_common(1)[0][1] if counts else 0,
        "percentual": round((counts.most_common(1)[0][1] / len(rows) * 100), 2) if rows else 0,
    },
    "ratings_na": rating_na,
    "carencia_disponivel": False,
    "liquidez_disponivel": False,
    "aviso": "O ranking compara rentabilidade líquida estimada. Confirme carência, liquidez, tributação, limite FGC por instituição/conglomerado e condições da plataforma antes de investir.",
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
