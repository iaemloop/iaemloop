#!/usr/bin/env python3
"""
Publica os rankings mensais do IA em Loop.

Fluxo:
1. Roda o pipeline BESST/Barsi e atualiza metodologia_barsi.html.
2. Atualiza a página Magic Formula a partir do greenblatt_top30.csv.
3. Adiciona ou substitui o mês corrente nos históricos:
   - historico_rankings.html
   - historico_rankings_magic_formula.html

Uso:
    python3 scripts/publish_monthly_rankings.py
    python3 scripts/publish_monthly_rankings.py --month 2026-05
    python3 scripts/publish_monthly_rankings.py --skip-pipelines
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BESST_CSV = ROOT / "outputs" / "barsi_screener_latest.csv"
MAGIC_FILTERED_CSV = ROOT / "greenblatt_top30_filtered.csv"
MAGIC_SOURCE_CSV = ROOT / "greenblatt_top30.csv"
MAGIC_CSV = MAGIC_FILTERED_CSV if MAGIC_FILTERED_CSV.exists() else MAGIC_SOURCE_CSV
BESST_HISTORY = ROOT / "historico_rankings.html"
MAGIC_HISTORY = ROOT / "historico_rankings_magic_formula.html"

MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

SECTOR_BY_TICKER = {
    "ALUP11": "Energia", "ANIM3": "Educação", "ASAI3": "Varejo alimentar",
    "BBAS3": "Bancos", "BBDC4": "Bancos", "BEEF3": "Alimentos", "BMGB4": "Bancos",
    "BPAC5": "Bancos", "BRBI11": "Bancos", "BRAV3": "Petróleo e gás",
    "CASH3": "Tecnologia/serviços financeiros", "CMIN3": "Mineração", "CPFE3": "Energia",
    "CSED3": "Educação", "CSNA3": "Mineração/Siderurgia", "CSUD3": "Tecnologia/serviços",
    "CURY3": "Construção civil", "ENGI3": "Energia", "ENGI11": "Energia",
    "EQTL3": "Energia", "EUCA4": "Madeira e papel", "KLBN3": "Papel e Celulose",
    "KLBN4": "Papel e Celulose", "LEVE3": "Autopeças", "MILS3": "Máquinas e equipamentos",
    "MOVI3": "Locação de veículos", "NEOE3": "Energia", "ODPV3": "Saúde/Odontologia",
    "PCAR3": "Varejo alimentar", "PETR3": "Petróleo e gás", "PETR4": "Petróleo e gás",
    "PLPL3": "Construção civil", "POMO3": "Material rodoviário", "POMO4": "Material rodoviário",
    "PSSA3": "Seguros", "QUAL3": "Saúde", "RANI3": "Papel e celulose",
    "RECV3": "Petróleo e gás", "SANB11": "Bancos", "SAPR11": "Saneamento",
    "SEER3": "Educação", "TAEE11": "Energia", "TGMA3": "Logística",
    "VALE3": "Mineração", "VAMO3": "Locação de veículos e máquinas", "VLID3": "Tecnologia/serviços",
    "VTRU3": "Educação", "WIZC3": "Serviços financeiros",
}


def run(cmd: list[str], *, allow_fail: bool = False) -> None:
    print(f"\n$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT, text=True)
    if proc.returncode and not allow_fail:
        raise SystemExit(proc.returncode)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))




def ticker_family(ticker: str) -> str:
    """Agrupa classes da mesma empresa: PETR3/PETR4 -> PETR; KLBN3/KLBN4 -> KLBN."""
    match = re.match(r"([A-Z]+)", ticker.strip().upper())
    return match.group(1) if match else ticker.strip().upper()


def one_ticker_per_company(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    # Regra IA em Loop: publicar uma empresa só uma vez.
    # O papel mantido é o melhor ranqueado na ordenação de origem; empates continuam
    # resolvidos pela ordenação bruta do pipeline/fonte.
    out = []
    seen_families: set[str] = set()
    for row in rows:
        ticker = row.get("ticker", "").strip().upper()
        family = ticker_family(ticker)
        if family in seen_families:
            continue
        seen_families.add(family)
        out.append(row)
    return out

def pct(value: str, *, already_percent: bool = False) -> str:
    try:
        v = float(str(value).replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return "-"
    if not already_percent and abs(v) <= 1:
        v *= 100
    return f"{v:.1f}%"


def num(value: str, digits: int = 2) -> str:
    try:
        return f"{float(str(value).replace(',', '.')):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def money_mi(value: str) -> str:
    if value in (None, "", "-"):
        return "-"
    try:
        v = float(str(value).replace("R$", "").replace("mi", "").strip().replace(",", "."))
    except ValueError:
        return html.escape(str(value))
    # Se vier em reais, converter para milhões; se já vier pequeno, assumir milhões.
    if abs(v) > 1_000_000:
        v = v / 1_000_000
    return f"R$ {v:.1f} mi"


def sector(row: dict[str, str]) -> str:
    ticker = row.get("ticker", "").strip().upper()
    raw = row.get("setor", "") or row.get("sector", "")
    segment = row.get("segmento", "") or row.get("industry", "")
    if ticker in SECTOR_BY_TICKER:
        return SECTOR_BY_TICKER[ticker]
    if "Bank" in segment or "Financial" in raw:
        return "Bancos"
    if "Electric" in segment or raw == "Utilities":
        return "Energia"
    if "Oil" in segment or raw == "Energy":
        return "Petróleo e gás"
    if "Paper" in segment:
        return "Papel e Celulose"
    if "Steel" in segment:
        return "Mineração/Siderurgia"
    translations = {
        "Energy": "Petróleo e gás",
        "Utilities": "Energia",
        "Basic Materials": "Materiais básicos",
        "Financial Services": "Bancos",
        "Communication Services": "Telecomunicações",
    }
    return translations.get(raw, raw or "-")


def fundamentus_link(ticker: str) -> str:
    ticker_h = html.escape(ticker)
    return f'<a href="https://www.fundamentus.com.br/detalhes.php?papel={ticker_h}" target="_blank"><strong>{ticker_h}</strong></a>'


def build_besst_entry(month: str, updated: str) -> str:
    rows = one_ticker_per_company(read_csv(BESST_CSV))
    body = []
    for pos, row in enumerate(rows[:30], 1):
        ticker = row.get("ticker", "").strip().upper()
        body.append(
            f'                        <tr><td>{pos}</td><td>{fundamentus_link(ticker)}</td>'
            f'<td>{html.escape(sector(row))}</td>'
            f'<td>{pct(row.get("dividend_yield", ""), already_percent=True)}</td>'
            f'<td>{num(row.get("p_vpa", ""))}</td>'
            f'<td>-</td><td>-</td><td>{num(row.get("score", ""))}</td></tr>'
        )
    label = month_label_slash(month)
    return f"""            {{
                id: '{month}',
                label: '{label}',
                tabela: `
                <table>
                    <thead><tr><th>Pos</th><th>Ticker</th><th>Setor</th><th>DY</th><th>P/VP</th><th>ROIC</th><th>ROE</th><th>Score BESST</th></tr></thead>
                    <tbody>
{chr(10).join(body)}
                    </tbody>
                </table>`
            }}"""


def update_besst_history(month: str, updated: str) -> None:
    text = BESST_HISTORY.read_text(encoding="utf-8")
    entry = build_besst_entry(month, updated)
    # Remove entrada existente do mesmo mês, se houver.
    text = re.sub(
        rf"\n\s*\{{\s*id:\s*'{re.escape(month)}'.*?\n\s*\}},(?=\n\s*\{{)",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        rf"\n\s*\{{\s*id:\s*'{re.escape(month)}'.*?\n\s*\}}(?=\n\s*\])",
        "",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace("        const rankings = [\n", f"        const rankings = [\n{entry},\n", 1)
    text = re.sub(r"Atualizado: \d{2}/\d{2}/\d{4}", f"Atualizado: {updated}", text, count=1)
    BESST_HISTORY.write_text(text, encoding="utf-8")


def build_magic_table(month: str) -> str:
    rows = read_csv(MAGIC_CSV)
    body = []
    for pos, row in enumerate(rows[:20], 1):
        ticker = row.get("ticker", "").strip().upper()
        ey = row.get("earnings_yield") or row.get("ey") or ""
        roic = row.get("roic", "")
        ev_ebit = row.get("ev_ebit", "")
        if not ev_ebit:
            try:
                ey_float = float(ey)
                ev_ebit = f"{1 / ey_float:.2f}" if ey_float else "-"
            except (TypeError, ValueError, ZeroDivisionError):
                ev_ebit = "-"
        body.append(
            f'<tr><td style="color:#E4D17F;font-weight:700">{pos}</td>'
            f'<td style="color:#AA8451;font-weight:600">{html.escape(ticker)}</td>'
            f'<td>{html.escape(row.get("setor") or sector(row))}</td>'
            f'<td style="color:#10b981">{pct(roic)}</td>'
            f'<td>{pct(ey)}</td>'
            f'<td>{html.escape(str(ev_ebit))}</td>'
            f'<td>{html.escape(str(row.get("dy") or row.get("dividend_yield") or "-"))}</td>'
            f'<td style="color:#E4D17F;font-weight:600">{html.escape(str(row.get("score", "")))}</td></tr>'
        )
    return f"""<table>
<thead><tr><th>Pos</th><th>Ticker</th><th>Setor</th><th>ROIC</th><th>EY</th><th>EV/EBIT</th><th>DY%</th><th>Score</th></tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
</table>"""


def normalize_magic_switcher(text: str) -> str:
    generic = """<script>
function switchTab(id) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const content = document.getElementById(id);
  if (content) content.classList.add('active');
  document.querySelectorAll('.tab').forEach(t => {
    const onclick = t.getAttribute('onclick') || '';
    if (onclick.includes("'" + id + "'") || onclick.includes('"' + id + '"')) {
      t.classList.add('active');
    }
  });
}
</script>"""
    if "function switchTab(id)" in text:
        return re.sub(r"<script>\s*function switchTab\(id\).*?</script>", generic, text, flags=re.S)
    return text.replace("</body>", generic + "\n</body>", 1)


def update_magic_history(month: str) -> None:
    text = normalize_magic_switcher(MAGIC_HISTORY.read_text(encoding="utf-8"))
    tab_id = f"rank-{month}"
    label = month_label_space(month)
    button = f'<button class="tab active" onclick="switchTab(\'{tab_id}\')">{label}</button>'
    content = f"""<div id="{tab_id}" class="tab-content active" data-month="{month}">
<div class="card">
<div style="overflow-x:auto;">
{build_magic_table(month)}
</div>
<p style="text-align:center;color:var(--muted);font-size:0.8rem;margin-top:1rem;">Dados: Fundamentus + yfinance ({label})</p>
</div>
</div>"""
    # Desativa abas/conteúdos ativos atuais.
    text = re.sub(r'class="tab active"', 'class="tab"', text)
    text = re.sub(r'class="tab-content active"', 'class="tab-content"', text)
    # Remove mês já gerado por este script, se existir.
    text = re.sub(rf'<button class="tab" onclick="switchTab\(\'{re.escape(tab_id)}\'\)">.*?</button>\s*', '', text)
    text = re.sub(rf'<div id="{re.escape(tab_id)}" class="tab-content" data-month="{re.escape(month)}">.*?</div>\s*</div>\s*', '', text, flags=re.S)
    text = text.replace('<div class="tabs">\n', f'<div class="tabs">\n{button}\n', 1)
    end_tabs = text.find('</div>', text.find('<div class="tabs">'))
    if end_tabs == -1:
        raise RuntimeError("Bloco de tabs do Magic Formula não encontrado")
    insert_at = end_tabs + len('</div>')
    text = text[:insert_at] + "\n" + content + text[insert_at:]
    text = re.sub(r"Atualizado: .*?</p>", f"Atualizado: {label}</p>", text, count=1)
    MAGIC_HISTORY.write_text(text, encoding="utf-8")


def month_label_slash(month: str) -> str:
    year, mm = month.split("-")
    return f"{MONTHS_PT[int(mm)]}/{year}"


def month_label_space(month: str) -> str:
    year, mm = month.split("-")
    return f"{MONTHS_PT[int(mm)]} {year}"


def pipeline_python() -> str:
    """Usa uma virtualenv própria do projeto para não depender do venv do Hermes nem do Python gerenciado pelo Homebrew."""
    venv_python = ROOT / ".venv-rankings" / "bin" / "python"
    recreate = False
    if venv_python.exists():
        try:
            version = subprocess.check_output([str(venv_python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], text=True).strip()
            if version not in {"3.9", "3.10", "3.11", "3.12"}:
                print(f"Virtualenv de rankings usa Python {version}; recriando com Python estável.")
                recreate = True
        except Exception:
            recreate = True
    if recreate:
        shutil.rmtree(venv_python.parent.parent)
    if not venv_python.exists():
        # Preferir /usr/bin/python3 no macOS 12: o Python Homebrew 3.14 quebra curl_cffi/yfinance neste host.
        seed = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else "/usr/local/bin/python3"
        print(f"Criando virtualenv de rankings em {venv_python.parent.parent}...")
        subprocess.check_call([seed, "-m", "venv", str(venv_python.parent.parent)], cwd=ROOT)
    return str(venv_python)


def run_pipelines(skip: bool) -> None:
    if skip:
        print("Pulando execução dos pipelines (--skip-pipelines).")
        return
    py = pipeline_python()
    # Instala dependências necessárias para os pipelines existentes.
    run([py, "-m", "pip", "install", "pandas", "numpy", "yfinance", "beautifulsoup4"])
    # BESST: pipeline funcional atual gera outputs/barsi_screener_latest.csv.
    run([py, "pipeline_final.py"])
    run([py, "scripts/update_besst_page.py"])
    # Magic Formula: hoje o repositório possui o CSV greenblatt_top30.csv como fonte.
    # O script aplica filtros editoriais, setor e atualiza a página principal.
    run([py, "scripts/update_magic_formula_page.py"])


def validate_outputs(month: str) -> None:
    checks = [
        (ROOT / "metodologia_barsi.html", ["Atualização", "<tbody", "fundamentus.com.br"]),
        (ROOT / "greenblatt_ned_landing_original.html", ["Setor", "Magic Formula", "fundamentus.com.br"]),
        (BESST_HISTORY, [month_label_slash(month), "Score BESST"]),
        (MAGIC_HISTORY, [month_label_space(month), "Setor", "ROIC", "EY"]),
    ]
    for path, terms in checks:
        text = path.read_text(encoding="utf-8")
        missing = [term for term in terms if term not in text]
        if missing:
            raise RuntimeError(f"Validação falhou em {path.name}: ausentes {missing}")
    print("Validação local OK.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=datetime.now().strftime("%Y-%m"), help="Mês no formato YYYY-MM")
    parser.add_argument("--skip-pipelines", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}", args.month):
        raise SystemExit("--month deve estar no formato YYYY-MM")
    updated = datetime.now().strftime("%d/%m/%Y")
    run_pipelines(args.skip_pipelines)
    update_besst_history(args.month, updated)
    update_magic_history(args.month)
    validate_outputs(args.month)
    print(f"Rankings mensais publicados localmente para {args.month}.")


if __name__ == "__main__":
    main()
