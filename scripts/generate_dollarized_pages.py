#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


def load_assets(name: str) -> tuple[dict, list[dict]]:
    data = json.loads((OUTPUTS / name).read_text(encoding="utf-8"), parse_constant=lambda _: None)
    assets = []
    seen = set()
    for item in data["assets"]:
        ticker = item.get("ticker")
        if not ticker or not item.get("empresa"):
            continue
        ticker = str(ticker).upper()
        if ticker in seen:
            continue
        seen.add(ticker)
        item["ticker"] = ticker
        assets.append(item)
    return data["meta"], assets


def fmt(value, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number):
        return "-"
    return f"{number:.{digits}f}{suffix}"


def fmt_br(value, suffix: str = "", digits: int = 1) -> str:
    text = fmt(value, suffix=suffix, digits=digits)
    return text.replace('.', ',') if text != '-' else text


def fmt_watchlist_dy(value) -> str:
    formatted = fmt_br(value, '%')
    if formatted == '-':
        return '0,0% — não distribui dividendos recorrentes'
    return formatted


def pick(asset: dict, *keys: str):
    for key in keys:
        value = asset.get(key)
        if value is not None:
            return value
    return None


def load_fundamentals_by_ticker() -> dict[str, dict]:
    path = OUTPUTS / "stocks_eua_fundamentos_latest.json"
    data = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda _: None)
    return {str(item.get('ticker', '')).upper(): item for item in data.get('assets', []) if item.get('ticker')}


def page(title: str, subtitle: str, body: str, updated: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | IA em Loop</title>
  <meta name="description" content="{subtitle}">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Inter, sans-serif;
      background: linear-gradient(rgba(6, 8, 13, 0.94), rgba(6, 8, 13, 0.94)), url('assets/bg-carteiras.jpg') center/cover fixed;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 36px 18px;
    }}
    .container {{ max-width: 1180px; margin: 0 auto; }}
    .back {{ color: #E4D17F; text-decoration: none; font-weight: 700; display: inline-block; margin-bottom: 24px; }}
    header {{ margin-bottom: 28px; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.4rem); line-height: 1.05; color: #fff; margin-bottom: 12px; }}
    .tagline {{ color: #94a3b8; max-width: 820px; line-height: 1.7; }}
    .panel {{
      background: rgba(19, 29, 39, 0.78);
      border: 1px solid rgba(228, 209, 127, 0.2);
      border-radius: 12px;
      padding: 22px;
      box-shadow: 0 6px 25px rgba(0,0,0,0.28);
      margin-bottom: 22px;
    }}
    .links {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }}
    .links a {{ color: #06101a; background: #E4D17F; text-decoration: none; padding: 9px 13px; border-radius: 8px; font-weight: 800; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 920px; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid rgba(148,163,184,0.22); text-align: left; }}
    th {{ background: rgba(6,8,13,0.88); color: #E4D17F; position: sticky; top: 0; }}
    td.rank {{ color: #E4D17F; font-weight: 800; }}
    td.ticker {{ color: #6EE4EF; font-weight: 800; letter-spacing: 0; }}
    .table-wrap {{ overflow-x: auto; border-radius: 10px; }}
    .note {{ color: #94a3b8; font-size: 0.9rem; line-height: 1.7; }}
    footer {{ color: #64748b; text-align: center; margin-top: 30px; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="container">
    <a class="back" href="index.html">Voltar para IA em Loop</a>
    <header>
      <h1>{title}</h1>
      <p class="tagline">{subtitle}</p>
      <div class="links">
        <a href="ranking_besst_buffett_dolarizado.html">BESST & Buffett EUA</a>
        <a href="ranking_magic_formula_dolarizada.html">Magic Formula EUA</a>
        <a href="historico_rankings_dolarizados.html">Historico dolarizado</a>
        <a href="watchlist_buffett_permanente_eua.html">Watchlist EUA</a>
      </div>
    </header>
    {body}
    <footer>Atualizado em {updated}. Conteudo educativo, nao e recomendacao de investimento.</footer>
  </div>
</body>
</html>
"""


def build_besst() -> str:
    meta, assets = load_assets("besst_buffett_eua_latest.json")
    rows = "\n".join(
        f"<tr><td class='rank'>{idx}</td><td class='ticker'>{a['ticker']}</td><td>{a['empresa']}</td><td>{a.get('setor') or '-'}</td>"
        f"<td>{fmt(pick(a, 'pl', 'pe'))}</td><td>{fmt(a.get('ev_ebitda'))}</td><td>{fmt(pick(a, 'roe_pct', 'roe'), '%')}</td>"
        f"<td>{fmt(a.get('dividend_yield_pct'), '%')}</td><td>{fmt(a.get('score_total'))}</td></tr>"
        for idx, a in enumerate(assets, 1)
    )
    updated = meta.get("updated_at", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    body = f"""<section class="panel note">
      Ranking dolarizado baseado no composite BESST & Buffett para stocks/ADRs dos EUA. Linhas sem ticker foram descartadas da publicacao.
    </section>
    <section class="panel table-wrap"><table>
      <thead><tr><th>#</th><th>Ticker</th><th>Empresa</th><th>Setor</th><th>P/L</th><th>EV/EBITDA</th><th>ROE</th><th>Dividend Yield</th><th>Score</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></section>"""
    return page("Ranking BESST & Buffett Dolarizado", "Carteira dolarizada de qualidade, perenidade, seguranca e valuation para o ciclo mensal IA em Loop.", body, updated)


def build_magic() -> str:
    meta, assets = load_assets("magic_formula_eua_latest.json")
    rows = "\n".join(
        f"<tr><td class='rank'>{idx}</td><td class='ticker'>{a['ticker']}</td><td>{a['empresa']}</td><td>{a.get('setor') or '-'}</td>"
        f"<td>{fmt(pick(a, 'pl', 'pe'))}</td><td>{fmt(a.get('ev_ebitda'))}</td><td>{fmt(a.get('roic_proxy_pct'), '%')}</td>"
        f"<td>{fmt(a.get('earnings_yield_pct'), '%')}</td><td>{fmt(a.get('fcf_yield_pct'), '%')}</td><td>{fmt(a.get('score_total'), digits=3)}</td></tr>"
        for idx, a in enumerate(assets, 1)
    )
    updated = meta.get("updated_at", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    body = f"""<section class="panel note">
      Ranking dolarizado pela Magic Formula: qualidade operacional aproximada por retorno sobre capital e preco medido por yield de resultados.
    </section>
    <section class="panel table-wrap"><table>
      <thead><tr><th>#</th><th>Ticker</th><th>Empresa</th><th>Setor</th><th>P/L</th><th>EV/EBITDA</th><th>ROIC proxy</th><th>Earnings Yield</th><th>FCF Yield</th><th>Score</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></section>"""
    return page("Ranking Magic Formula Dolarizada", "Top stocks/ADRs dos EUA por retorno sobre capital e preco relativo, seguindo a frente dolarizada IA em Loop.", body, updated)


def build_history() -> str:
    besst_meta, besst = load_assets("besst_buffett_eua_latest.json")
    magic_meta, magic = load_assets("magic_formula_eua_latest.json")
    updated = max((besst_meta.get("updated_at") or "")[:10], (magic_meta.get("updated_at") or "")[:10])
    body = f"""<section class="panel">
      <h2>Julho/2026</h2>
      <p class="note">Primeiro mes publicado da frente dolarizada. BESST & Buffett EUA com {len(besst)} ativos validos e Magic Formula EUA com {len(magic)} ativos validos apos remover linhas sem ticker.</p>
    </section>
    <section class="panel table-wrap"><table>
      <thead><tr><th>Metodo</th><th>#1</th><th>#2</th><th>#3</th><th>Arquivo</th></tr></thead>
      <tbody>
        <tr><td>BESST & Buffett EUA</td><td>{besst[0]['ticker']}</td><td>{besst[1]['ticker']}</td><td>{besst[2]['ticker']}</td><td><a class="back" href="ranking_besst_buffett_dolarizado.html">ver ranking</a></td></tr>
        <tr><td>Magic Formula EUA</td><td>{magic[0]['ticker']}</td><td>{magic[1]['ticker']}</td><td>{magic[2]['ticker']}</td><td><a class="back" href="ranking_magic_formula_dolarizada.html">ver ranking</a></td></tr>
      </tbody>
    </table></section>"""
    return page("Historico de Rankings Dolarizados", "Historico mensal das carteiras dolarizadas IA em Loop, com BESST & Buffett EUA e Magic Formula EUA.", body, updated)


def build_watchlist() -> str:
    csv_path = OUTPUTS / "watchlist_buffett_permanente_eua_latest.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        selected = list(csv.DictReader(fh))
    fundamentals = load_fundamentals_by_ticker()
    updated = datetime.now().strftime("%Y-%m-%d")
    row_parts = []
    for idx, a in enumerate(selected, 1):
        ticker = str(a.get('ticker', '')).upper()
        f = fundamentals.get(ticker, {})
        row_parts.append(
            f"<tr><td class='rank'>{idx}</td><td class='ticker'>{ticker}</td><td>{a['empresa']}</td><td>{a.get('setor') or '-'}</td>"
            f"<td>{fmt_br(pick(f, 'pl', 'pe'))}</td><td>{fmt_br(f.get('ev_ebitda'))}</td>"
            f"<td>{fmt_br(pick(f, 'roe_pct', 'roe', 'return_on_equity'), '%')}</td>"
            f"<td>{fmt_watchlist_dy(pick(f, 'dividend_yield_pct', 'dividend_yield'))}</td></tr>"
        )
    rows = "\n".join(row_parts)
    body = f"""<section class="panel note">
      Empresas de qualidade que merecem acompanhamento permanente, mesmo quando nao entram no top 20 mensal por valuation.
    </section>
    <section class="panel table-wrap"><table>
      <thead><tr><th>#</th><th>Ticker</th><th>Empresa</th><th>Setor</th><th>P/L</th><th>EV/EBITDA</th><th>ROE</th><th>Dividend Yield</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></section>"""
    return page("Watchlist Buffett Permanente EUA", "Lista de acompanhamento permanente para stocks/ADRs de alta qualidade no universo dolarizado IA em Loop.", body, updated)


def main() -> None:
    pages = {
        "ranking_besst_buffett_dolarizado.html": build_besst(),
        "ranking_magic_formula_dolarizada.html": build_magic(),
        "historico_rankings_dolarizados.html": build_history(),
        "watchlist_buffett_permanente_eua.html": build_watchlist(),
    }
    for filename, content in pages.items():
        (ROOT / filename).write_text(content, encoding="utf-8")
        print(f"Generated {filename}")


if __name__ == "__main__":
    main()
