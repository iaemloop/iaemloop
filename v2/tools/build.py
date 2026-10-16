#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Build the isolated IA em Loop V2 public site from read-only V1 sources."""
from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "v2"
SITE = "https://iaemloop.com.br"
ASSET_VERSION = 10

ROUTES = [
    {"source":"metodologia_barsi.html","target":"rankings/besst-buffett-b3.html","title":"BESST & Buffett B3","category":"Ranking B3","description":"Dividendos, setores perenes, qualidade e valor intrínseco em uma mesma leitura."},
    {"source":"historico_rankings.html","target":"rankings/historico/besst-buffett-b3.html","title":"Histórico BESST & Buffett B3","category":"Histórico B3","description":"Evolução mensal do ranking BESST & Buffett na bolsa brasileira."},
    {"source":"greenblatt_ned_landing_original.html","target":"rankings/magic-formula-b3.html","title":"Magic Formula B3","category":"Ranking B3","description":"Empresas eficientes e baratas ordenadas por ROIC e Earnings Yield."},
    {"source":"historico_rankings_magic_formula.html","target":"rankings/historico/magic-formula-b3.html","title":"Histórico Magic Formula B3","category":"Histórico B3","description":"Arquivo mensal do ranking Magic Formula para ações brasileiras."},
    {"source":"ranking_besst_buffett_dolarizado.html","target":"rankings/besst-buffett-eua.html","title":"BESST & Buffett EUA","category":"Ranking internacional","description":"Qualidade, previsibilidade e valuation aplicados a stocks americanas."},
    {"source":"historico_rankings_dolarizados.html","target":"rankings/historico/besst-buffett-eua.html","title":"Histórico BESST & Buffett EUA","category":"Histórico internacional","description":"Evolução mensal do ranking dolarizado BESST & Buffett."},
    {"source":"ranking_magic_formula_dolarizada.html","target":"rankings/magic-formula-eua.html","title":"Magic Formula EUA","category":"Ranking internacional","description":"ROIC, preço e eficiência operacional no universo de stocks."},
    {"source":"historico_rankings_magic_formula_dolarizada.html","target":"rankings/historico/magic-formula-eua.html","title":"Histórico Magic Formula EUA","category":"Histórico internacional","description":"Arquivo mensal da Magic Formula dolarizada."},
    {"source":"watchlist_buffett_permanente_eua.html","target":"radar/watchlist-buffett-eua.html","title":"Watchlist Buffett Permanente EUA","category":"Radar internacional","description":"Empresas excepcionais para acompanhar continuamente, sem compra automática."},
    {"source":"historico_watchlist_buffett_permanente_eua.html","target":"rankings/historico/watchlist-buffett-eua.html","title":"Histórico da Watchlist Buffett EUA","category":"Histórico internacional","description":"Mudanças e permanências do radar Buffett ao longo do tempo."},
    {"source":"metodologia_barsi.html","target":"metodos/besst-buffett.html","title":"Método BESST & Buffett","category":"Metodologia","description":"Como combinamos dividendos de setores perenes com qualidade e valor intrínseco."},
    {"source":"greenblatt_ned_landing_original.html","target":"metodos/magic-formula.html","title":"Método Magic Formula","category":"Metodologia","description":"A lógica por trás do ranking de empresas boas negociadas a preços interessantes."},
    {"source":"ranking_fgc.html","target":"rankings/renda-fixa-fgc.html","title":"Renda Fixa FGC","category":"Renda fixa","description":"Produtos protegidos pelo FGC organizados por retorno, prazo e indexador."},
    {"source":"indicador-buffett.html","target":"indicadores/buffett.html","title":"Indicador Buffett","category":"Indicador macro","description":"Valor de mercado das empresas listadas dividido pelo PIB nos EUA e no Brasil."},
    {"source":"bitcoin_landing.html","target":"indicadores/bitcoin.html","title":"Guia Bitcoin","category":"Ativo digital","description":"Preço, ciclos e indicadores para estudar Bitcoin sem atalhos narrativos."},
]

LEGACY_TO_V2 = {"/" + r["source"]: "/v2/" + r["target"] for r in ROUTES}
LEGACY_TO_V2.update({
    "/index.html":"/v2/index.html",
    "/blog/index.html":"/v2/blog/index.html",
    "/area_privada.html":"/v2/area-privada.html?redirect=/privado/v2/index.html",
    "/metodologia_watchlist_eua.html":"/v2/radar/watchlist-buffett-eua.html",
})

NAV = [
    ("Início", "/v2/index.html"),
    ("Métodos", "/v2/metodos/index.html"),
    ("Indicadores", "/v2/indicadores/index.html"),
    ("Rankings", "/v2/rankings/index.html"),
    ("Radar", "/v2/radar/index.html"),
    ("Blog", "/v2/blog/index.html"),
]

PORTFOLIO_DESTINATIONS = {
    "rankings/besst-buffett-b3.html": "/privado/carteira_besst.html",
    "metodos/besst-buffett.html": "/privado/carteira_besst.html",
    "rankings/historico/besst-buffett-b3.html": "/privado/carteira_besst.html",
    "rankings/magic-formula-b3.html": "/privado/carteira_magic_formula.html",
    "metodos/magic-formula.html": "/privado/carteira_magic_formula.html",
    "rankings/historico/magic-formula-b3.html": "/privado/carteira_magic_formula.html",
    "rankings/besst-buffett-eua.html": "/privado/carteira_besst_dolarizada.html",
    "rankings/historico/besst-buffett-eua.html": "/privado/carteira_besst_dolarizada.html",
    "rankings/magic-formula-eua.html": "/privado/carteira_magic_formula_dolarizada.html",
    "rankings/historico/magic-formula-eua.html": "/privado/carteira_magic_formula_dolarizada.html",
}


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def ranking_column_alignment(header: str) -> str:
    """Return the semantic alignment for a public ranking column."""
    normalized = unicodedata.normalize("NFKD", clean_text(header)).encode("ascii", "ignore").decode().lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized == "#" or re.search(r"\b(?:pos(?:icao)?|rank|ticker|codigo|score)\b", normalized):
        return "center"
    if re.search(
        r"\b(?:empresa|companhia|nome|setor|segmento|industria|produto|emissor|instituicao|"
        r"rating|indexador|tipo|categoria|observac(?:ao|oes)|ativo)\b",
        normalized,
    ):
        return "left"
    return "right"


def annotate_ranking_tables(soup: BeautifulSoup) -> None:
    """Apply one semantic alignment contract to static ranking tables."""
    for table in soup.select("table"):
        headers = table.select("thead tr:first-child th")
        if not headers:
            continue
        classes = list(dict.fromkeys([*table.get("class", []), "v2-ranking-table"]))
        table["class"] = classes
        alignments = []
        for header in headers:
            alignment = ranking_column_alignment(header.get_text(" ", strip=True))
            css_class = f"v2-align-{alignment}"
            header["class"] = list(dict.fromkeys([*header.get("class", []), css_class]))
            alignments.append(css_class)
        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) != len(alignments):
                continue
            for cell, css_class in zip(cells, alignments):
                cell["class"] = list(dict.fromkeys([*cell.get("class", []), css_class]))


PRIVATE_CONTEXT = re.compile(
    r"carteira real|custódia|aporte real|posição (?:real|da carteira|na carteira)|"
    r"carteira (?:magic formula|besst|dolarizada)",
    re.IGNORECASE,
)
PRIVATE_DETAIL = re.compile(
    r"preço médio|custo (?:médio|unitário)|valor (?:executado|investido|comprado)|"
    r"peso (?:da|na) carteira|%\s+da carteira|\b\d+[\d.,]*\s*(?:ações|ação|unidades)\b|"
    r"\b(?:R\$|US\$)\s*[\d.,]+",
    re.IGNORECASE,
)


# Disclosure detection happens before any neutralization so private numbers cannot orphan.
DISCLOSURE = re.compile(
    r"carteiras?(?: brasileiras?)? rea(?:l|is)|carteiras? reais|custódia|aporte real|compra real|"
    r"peso.{0,50}(?:na|da) carteira|presença confirmada.{0,70}carteiras?|"
    r"carteira (?:BESST(?: & Buffett)?|Magic Formula|dolarizada) real|"
    r"posição pequena.{0,90}carteira|proventos futuros mapeados|essa dupla confirmação|"
    r"presença tanto na carteira|"
    r"posiç(?:ão|ões) (?:real|da carteira|na carteira)|"
    r"preços? médios?.{0,90}carteiras?|carteiras?.{0,90}preços? médios?|"
    r"variaç(?:ão|ões) (?:vs\.?|contra)\s*(?:PM|preço médio)|"
    r"exposição real.{0,90}carteiras?|presença.{0,90}carteiras?.{0,30}reais",
    re.I,
)


def is_disclosure(text: str) -> bool:
    return bool(DISCLOSURE.search(text) or (PRIVATE_CONTEXT.search(text) and PRIVATE_DETAIL.search(text)) or
                (re.search(r"BESST|Magic Formula", text, re.I) and
                 re.search(r"\b\d+[\d.,]*\s*(?:ações|ação|unidades?)\b", text, re.I)))


def public_text(text: str) -> str:
    text = clean_text(text)
    # Protect abbreviations/decimal punctuation while splitting disclosure sentences.
    protected = re.sub(r"\b(vs|Var|Sr|Sra)\.", lambda m: m.group(0).replace(".", "∯"), text, flags=re.I)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ0-9•])", protected)
    kept = [part.replace("∯", ".") for part in parts if not is_disclosure(part)]
    return " ".join(kept).replace("posição que投入 no início", "posição iniciada no período").replace("o papéis está próximo", "o papel está próximo")


def sanitize_public_article(article: BeautifulSoup) -> None:
    """Strip private leaf blocks; preserve public prose in mixed paragraphs."""
    for image in list(article.find_all("img")):
        src = str(image.get("src", "")).split("?", 1)[0]
        if src.startswith("/") and src.endswith(".svg"):
            asset = ROOT / src.lstrip("/")
            if asset.exists():
                svg = BeautifulSoup(asset.read_text(encoding="utf-8"), "xml")
                asset_text = clean_text(svg.get_text(" "))
                if is_disclosure(asset_text) or re.search(r"preço médio|\bPM\b|\d+[\d.,]*\s*(?:ações|ação|unidades)", asset_text, re.I):
                    parent = image.parent
                    image.decompose()
                    if parent.name == "figure" and not parent.find("img"):
                        parent.decompose()
    for node in list(article.find_all(["p", "li", "tr", "div", "span", "h1", "h2", "h3"])):
        if node.parent is None:
            continue
        # Handle structured rows and scorecards as a complete private leaf.
        leaf = node.name == "tr" or not node.find(["p", "li", "tr", "div"])
        if not leaf:
            continue
        text = clean_text(node.get_text(" "))
        if not is_disclosure(text):
            continue
        safe = public_text(text)
        if safe and node.name in ("p", "li"):
            node.clear()
            node.append(safe)
        else:
            node.decompose()
    for tag in article.find_all(True):
        for attr in ("alt", "title", "aria-label"):
            if tag.has_attr(attr):
                tag[attr] = public_text(str(tag[attr]))
    for text_node in list(article.find_all(string=True)):
        fixed = str(text_node).replace("posição que投入 no início", "posição iniciada no período").replace("o papéis está próximo", "o papel está próximo")
        if fixed != str(text_node):
            text_node.replace_with(fixed)
    # Remove an empty section heading without destroying the neighboring analysis.
    for heading in list(article.find_all(["h2", "h3"])):
        sibling = heading.find_next_sibling()
        if sibling is None or sibling.name in ("h2", "h3"):
            heading.decompose()


def nav_html() -> str:
    links = "".join(f'<a href="{href}" data-v2-nav>{label}</a>' for label, href in NAV)
    return f'''<header class="v2-site-nav v2-global-nav">
      <a class="v2-brand" href="/v2/index.html" aria-label="IA em Loop V2"><span class="v2-brand-mark">∞</span><span>IA em Loop<small>Investment observatory · V2</small></span></a>
      <button class="v2-menu-toggle" type="button" aria-expanded="false" aria-controls="v2-main-menu"><span></span><span></span><span></span><b class="sr-only">Abrir menu</b></button>
      <nav class="v2-main-menu" id="v2-main-menu" aria-label="Navegação principal">{links}<a class="v2-primary" href="/v2/area-privada.html?redirect=/privado/v2/index.html">Área privada</a></nav>
    </header>'''


def footer_html() -> str:
    return '''<footer class="v2-footer"><div><a class="v2-brand" href="/v2/index.html"><span class="v2-brand-mark">∞</span><span>IA em Loop<small>Dados, método e skin in the game</small></span></a><p>Conteúdo educacional. Não é recomendação de investimento.</p></div><nav aria-label="Links do rodapé"><a href="/v2/rankings/index.html">Rankings</a><a href="/v2/metodos/index.html">Metodologias</a><a href="/v2/indicadores/index.html">Indicadores</a><a href="/v2/blog/index.html">Blog</a><a href="/index.html">Visual clássico</a></nav></footer>'''


def document(title: str, description: str, body: str, extra_head: str = "", body_class: str = "") -> str:
    title = public_text(title) or "Análise de investimentos"
    description = public_text(description) or "Análise educacional do IA em Loop."
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{html.escape(description, quote=True)}"><title>{html.escape(title)} | IA em Loop V2</title><link rel="stylesheet" href="/css/v2/observatory.css?v={ASSET_VERSION}"><link rel="stylesheet" href="/css/v2/public.css?v={ASSET_VERSION}">{extra_head}</head>
<body class="v2-page v2-public {body_class}">{nav_html()}<main>{body}</main>{footer_html()}<script src="/js/v2/public.js?v={ASSET_VERSION}"></script><script src="/js/v2/shell.js?v={ASSET_VERSION}"></script></body></html>'''


def resolve_url(value: str, source: str, attr: str) -> str:
    if not value or value.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return value
    parsed = urlparse(value)
    if parsed.scheme or value.startswith("//"):
        return value
    source_url = SITE + "/" + source
    absolute = urlparse(urljoin(source_url, value)).path
    if parsed.query:
        absolute += "?" + parsed.query
    if parsed.fragment:
        absolute += "#" + parsed.fragment
    path_only = absolute.split("?", 1)[0].split("#", 1)[0]
    if attr == "href":
        if path_only.startswith("/blog/posts/"):
            suffix = path_only.removeprefix("/blog/posts/")
            absolute = "/v2/blog/posts/" + suffix
        elif path_only in LEGACY_TO_V2:
            mapped = LEGACY_TO_V2[path_only]
            fragment = ("#" + parsed.fragment) if parsed.fragment else ""
            absolute = mapped + fragment
    return absolute


def extract_source(source: str) -> tuple[str, str]:
    raw = (ROOT / source).read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    title = clean_text(soup.title.get_text(" ") if soup.title else Path(source).stem)
    description_tag = soup.find("meta", attrs={"name":"description"})
    description = description_tag.get("content", "") if description_tag else ""

    for selector in [".back-button", "a.back", ".theme-toggle", "#backToTop", ".back-to-top", ".footer", "footer"]:
        for node in soup.select(selector):
            node.decompose()
    for script in soup.find_all("script"):
        src = script.get("src", "")
        if any(x in src for x in ("theme-switcher", "pagead2", "adsbygoogle")):
            script.decompose()
            continue
        if not src and script.string:
            script.string.replace_with(re.sub(
                r"fetch\((['\"])(?!https?:|/)([^'\"]+)\1\)",
                lambda match: f"fetch({match.group(1)}{resolve_url(match.group(2), source, 'src')}{match.group(1)})",
                script.string,
            ))
    # Remove only imported mastheads, never dated data/update cards.
    for hero in soup.select("section.hero"):
        for heading in list(hero.find_all("h1")):
            heading.decompose()
    for node in list(soup.select(".header-card, header")):
        if node.parent is not None and node.find("h1"):
            node.decompose()
    for node in list(soup.find_all(["p", "div", "span"])):
        if node.parent is not None and not node.find(True) and re.fullmatch(
            r"Conteúdo educacional\. Não (?:é|constitui) recomendação(?: personalizada)? de investimento\.",
            clean_text(node.get_text(" ")), re.I,
        ):
            node.decompose()
    is_history = source.startswith("historico_")
    if is_history:
        tabs = soup.select_one(".tabs")
        if tabs is None:
            monthly_sections = [
                section for section in soup.select("section")
                if section.select_one("table") and section.find(["h2", "h3"])
            ]
            if len(monthly_sections) > 1:
                tabs = soup.new_tag("div", attrs={
                    "class": "tabs v2-history-tabs",
                    "role": "tablist",
                    "aria-label": "Meses do histórico",
                })
                monthly_sections[0].insert_before(tabs)
                for idx, section in enumerate(monthly_sections):
                    heading = section.find(["h2", "h3"])
                    panel_id = f"history-month-{idx}"
                    panel = soup.new_tag("div", attrs={
                        "class": "tab-content" + (" active" if idx == 0 else ""),
                        "id": panel_id,
                        "role": "tabpanel",
                    })
                    section.wrap(panel)
                    button = soup.new_tag("button", attrs={
                        "class": "tab" + (" active" if idx == 0 else ""),
                        "type": "button",
                        "role": "tab",
                        "aria-controls": panel_id,
                        "aria-selected": "true" if idx == 0 else "false",
                        "onclick": f"switchTab({json.dumps(panel_id)}, this)",
                    })
                    button.string = clean_text(heading.get_text(" "))
                    tabs.append(button)
        if tabs is not None:
            tabs["class"] = list(dict.fromkeys([*tabs.get("class", []), "v2-history-tabs"]))
            tabs["role"] = "tablist"
            tabs["aria-label"] = "Meses do histórico"

    # Static history buttons must not depend on the nonstandard global event.
    static_tabs = soup.select("button.tab[onclick]")
    if static_tabs:
        for old_script in list(soup.find_all("script")):
            if not old_script.get("src") and "function switchTab" in (old_script.string or old_script.decode_contents()):
                old_script.decompose()
        for button in static_tabs:
            match = re.fullmatch(r"switchTab\(['\"]([^'\"]+)['\"](?:,\s*this)?\)", button["onclick"])
            if match:
                target_id = match.group(1)
                button["onclick"] = "switchTab(" + json.dumps(target_id) + ", this)"
                button["type"] = "button"
                button["role"] = "tab"
                button["aria-controls"] = target_id
                button["aria-selected"] = "true" if "active" in button.get("class", []) else "false"
                target = soup.find(id=target_id)
                if target is not None:
                    target["role"] = "tabpanel"
        script = soup.new_tag("script")
        script.string = """
function switchTab(id, button) {
  const root = document.querySelector('.v2-imported-content');
  const target = document.getElementById(id);
  if (!root || !target || !root.contains(target) || !button) return;
  root.querySelectorAll('.tab,.tab-content').forEach(el => el.classList.remove('active'));
  root.querySelectorAll('.tab[aria-selected]').forEach(el => el.setAttribute('aria-selected', 'false'));
  target.classList.add('active');
  button.classList.add('active');
  button.setAttribute('aria-selected', 'true');
}
"""
        (soup.body or soup).append(script)
    content = soup.body or soup
    for main in content.find_all("main"):
        main.unwrap()
    for tag in content.find_all(True):
        for attr in ("href", "src"):
            if tag.has_attr(attr):
                tag[attr] = resolve_url(str(tag[attr]), source, attr)
        if tag.name == "a" and tag.get("target") == "_blank":
            tag["rel"] = "noopener noreferrer"
    inner = "".join(str(child) for child in content.contents)
    return inner, description or title


def source_page(route: dict[str, str]) -> str:
    inner, source_description = extract_source(route["source"])
    inner_soup = BeautifulSoup(inner, "html.parser")
    if route["target"] in ("rankings/historico/besst-buffett-eua.html", "rankings/historico/magic-formula-eua.html"):
        for node in list(inner_soup.select(".kpis, .portfolio-v31-title")):
            node.decompose()
    if route["source"] == "ranking_fgc.html":
        # Match the script path, independent of the legacy cache version.
        for script in list(inner_soup.find_all("script")):
            if str(script.get("src", "")).split("?", 1)[0] == "/scripts/fgc-dynamic.js":
                script["src"] = f"/js/v2/fgc.js?v={ASSET_VERSION}"
            elif "function applyFilters()" in (script.string or script.decode_contents()):
                script.decompose()  # V2 loader owns the filters after rendering rows.

    portfolio_destination = PORTFOLIO_DESTINATIONS.get(route["target"])
    if portfolio_destination:
        login_href = f"/v2/area-privada.html?redirect={portfolio_destination}"
        for anchor in inner_soup.find_all("a", href=True):
            href = str(anchor.get("href", ""))
            if "/area-privada.html" in href or "/area_privada.html" in href:
                anchor["href"] = login_href

    is_ranking = route["target"].startswith(("rankings/", "radar/"))
    is_tabular = is_ranking or route["target"].startswith("metodos/")
    if is_tabular:
        annotate_ranking_tables(inner_soup)
    for heading in list(inner_soup.find_all("h1")):
        heading.decompose()
    inner = str(inner_soup)
    body = f'<div class="v2-content v2-imported-content"><h1 class="v2-data-title">{html.escape(route["title"])}</h1>{inner}</div>'
    body_class = "v2-data-page v2-ranking-page" if is_ranking else "v2-data-page v2-tabular-page" if is_tabular else "v2-data-page"
    return document(route["title"], source_description, body, body_class=body_class)


def card(title: str, description: str, href: str, tag: str, index: str, accent: str = "blue") -> str:
    return f'''<a class="v2-catalog-card accent-{accent}" href="{href}"><span class="v2-card-index">{index}</span><div><p class="v2-card-tag">{tag}</p><h3>{title}</h3><p>{description}</p></div><b>Explorar <span aria-hidden="true">↗</span></b></a>'''


def hub(title: str, kicker: str, description: str, cards: list[str], body_class: str = "") -> str:
    body = f'''<section class="v2-hub-hero"><p class="v2-kicker">{kicker}</p><h1>{title}</h1><p>{description}</p></section><section class="v2-catalog-grid">{''.join(cards)}</section>'''
    return document(title, description, body, body_class=body_class)


def parse_blog_cards() -> list[dict[str, Any]]:
    soup = BeautifulSoup((ROOT / "blog/index.html").read_text(encoding="utf-8"), "html.parser")
    posts = []
    for a in soup.select("a.post-card"):
        href = a.get("href", "")
        if not href.startswith("posts/"):
            continue
        posts.append({
            "source": "blog/" + href,
            "slug": Path(href).name,
            "title": clean_text(a.find("h2").get_text(" ") if a.find("h2") else href),
            "summary": clean_text(a.find("p").get_text(" ") if a.find("p") else ""),
            "chips": [clean_text(x.get_text(" ")) for x in a.select(".chips span")],
        })
    indexed = {str(post["slug"]) for post in posts}
    for path in sorted((ROOT / "blog/posts").glob("*.html")):
        if path.name in indexed:
            continue
        post_soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        posts.append({
            "source": path.relative_to(ROOT).as_posix(),
            "slug": path.name,
            "title": clean_text(post_soup.find("h1").get_text(" ") if post_soup.find("h1") else path.stem),
            "summary": clean_text(post_soup.select_one(".dek").get_text(" ") if post_soup.select_one(".dek") else ""),
            "chips": [clean_text(x.get_text(" ")) for x in post_soup.select(".meta span")],
        })

    def date_key(post: dict[str, Any]) -> datetime:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", str(post["slug"]))
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        for chip in post["chips"]:
            try:
                return datetime.strptime(str(chip), "%d/%m/%Y")
            except ValueError:
                pass
        return datetime.min

    posts = sorted(posts, key=date_key, reverse=True)
    for post in posts:
        post["title"] = public_text(str(post["title"])) or "Análise de investimentos"
        post["summary"] = public_text(str(post["summary"]))
        post["chips"] = [safe for chip in post["chips"] if (safe := public_text(str(chip)))]
    return posts


def blog_index(posts: list[dict[str, Any]]) -> str:
    cards = []
    for post in posts:
        chips = "".join(f"<span>{html.escape(str(chip))}</span>" for chip in post["chips"][:6])
        cards.append(f'''<a class="v2-post-card" href="/v2/blog/posts/{post['slug']}"><div class="v2-post-chips">{chips}</div><h2>{html.escape(str(post['title']))}</h2><p>{html.escape(str(post['summary']))}</p><b>Ler análise <span aria-hidden="true">↗</span></b></a>''')
    body = f'''<section class="v2-hub-hero v2-blog-hero"><p class="v2-kicker">Análises · cenário · empresas</p><h1>Leitura para quem prefere contexto a ruído.</h1><p>O arquivo editorial completo do IA em Loop em uma experiência de leitura independente.</p><label class="v2-search"><span>Buscar no arquivo</span><input class="v2-search-input" type="search" placeholder="Ticker, empresa ou tema…" autocomplete="off"></label></section><section class="v2-post-grid" data-v2-search-list>{''.join(cards)}</section><p class="v2-empty-state" hidden>Nenhum artigo encontrado para essa busca.</p>'''
    return document("Blog", "Análises do IA em Loop sobre ações, macroeconomia, geopolítica e inteligência artificial.", body, body_class="v2-blog")


def blog_post(post: dict[str, Any]) -> str:
    inner, description = extract_source(str(post["source"]))
    parsed = BeautifulSoup(inner, "html.parser")
    source_article = parsed.find("article")
    if source_article:
        sanitize_public_article(source_article)
    article_html = "".join(str(child) for child in source_article.contents) if source_article else inner
    body = f'''<nav class="v2-breadcrumb" aria-label="Trilha"><a href="/v2/index.html">Início</a><span>/</span><a href="/v2/blog/index.html">Blog</a><span>/</span><span>Artigo</span></nav><article class="v2-content v2-article-content">{article_html}</article><aside class="v2-next-reading"><p class="v2-kicker">Continue explorando</p><h2>Volte ao arquivo completo.</h2><a class="v2-primary" href="/v2/blog/index.html">Ver todas as análises</a></aside>'''
    return document(str(post["title"]), description, body, body_class="v2-blog-post")


def home(posts: list[dict[str, Any]]) -> str:
    latest = posts[:3]
    latest_cards = "".join(f'''<a class="v2-editorial-card" href="/v2/blog/posts/{p['slug']}"><span>{html.escape(str(p['chips'][0] if p['chips'] else 'Análise'))}</span><h3>{html.escape(str(p['title']))}</h3><p>{html.escape(str(p['summary']))}</p></a>''' for p in latest)
    cards = [
        card("BESST & Buffett B3","Dividendos, qualidade e valor intrínseco.","/v2/rankings/besst-buffett-b3.html","Brasil","01","lime"),
        card("Magic Formula B3","ROIC e Earnings Yield para ordenar oportunidades.","/v2/rankings/magic-formula-b3.html","Brasil","02","cyan"),
        card("BESST & Buffett EUA","Qualidade e valuation no mercado americano.","/v2/rankings/besst-buffett-eua.html","Estados Unidos","03","coral"),
        card("Magic Formula EUA","Eficiência e preço aplicados a stocks.","/v2/rankings/magic-formula-eua.html","Estados Unidos","04","gold"),
        card("Renda Fixa FGC","Produtos cobertos pelo FGC comparados com clareza.","/v2/rankings/renda-fixa-fgc.html","Renda fixa","05","cyan"),
        card("Indicadores","Buffett, Bitcoin e leituras de ciclo.","/v2/indicadores/index.html","Contexto","06","blue"),
    ]
    body = f'''<section class="v2-full-hero"><div class="v2-hero-copy"><p class="v2-kicker">Investimentos com inteligência artificial · skin in the game</p><h1>Dados para pensar.<br><em>Método para decidir.</em></h1><p>Rankings, metodologias, indicadores e análises conectados em um observatório público — com a custódia real protegida na área privada.</p><div class="v2-actions"><a class="v2-primary" href="/v2/rankings/index.html">Explorar rankings</a><a class="v2-secondary" href="/v2/area-privada.html?redirect=/privado/v2/index.html">Entrar na área privada</a></div></div><div class="v2-signal-art"><div class="v2-signal-number">∞</div><p>Observar.<br>Comparar.<br>Reavaliar.</p><span>IA em Loop · V2</span></div></section><section class="v2-ticker"><span>BRASIL</span><b>BESST + BUFFETT</b><span>ESTADOS UNIDOS</span><b>MAGIC FORMULA</b><span>MACRO</span><b>SKIN IN THE GAME</b></section><section class="v2-home-section"><div class="v2-section-title"><p class="v2-kicker">Mapa do observatório</p><h2>Comece por onde sua pergunta está.</h2><p>Cada área tem uma função: selecionar, entender, contextualizar ou acompanhar.</p></div><div class="v2-catalog-grid">{''.join(cards)}</div></section><section class="v2-split-feature"><div><p class="v2-kicker">Método antes do ticker</p><h2>Rankings não são ordens de compra.</h2><p>São pontos de partida auditáveis. A V2 aproxima critérios, históricos e contexto para reduzir decisões por impulso.</p><a class="v2-secondary" href="/v2/metodos/index.html">Entender as metodologias</a></div><div class="v2-principles"><article><b>01</b><h3>Selecionar</h3><p>Filtros quantitativos para encontrar onde vale investigar.</p></article><article><b>02</b><h3>Validar</h3><p>Qualidade, risco, ciclo e valuation antes da execução.</p></article><article><b>03</b><h3>Acompanhar</h3><p>Históricos para distinguir mudança real de ruído mensal.</p></article></div></section><section class="v2-home-section"><div class="v2-section-title"><p class="v2-kicker">Últimas leituras</p><h2>O que está no radar agora.</h2><a href="/v2/blog/index.html">Abrir arquivo completo ↗</a></div><div class="v2-editorial-grid">{latest_cards}</div></section>'''
    return document("Início", "IA em Loop V2: rankings, metodologias, indicadores, análises e área privada de investimentos.", body, body_class="v2-home")


def build() -> None:
    posts = parse_blog_cards()
    outputs: dict[str, str] = {}
    outputs["index.html"] = home(posts)

    ranking_cards = [
        card("BESST & Buffett B3","Ranking atual e histórico mensal.","/v2/rankings/besst-buffett-b3.html","Ações brasileiras","01","lime"),
        card("Magic Formula B3","Ranking atual e histórico mensal.","/v2/rankings/magic-formula-b3.html","Ações brasileiras","02","cyan"),
        card("BESST & Buffett EUA","Ranking dolarizado de qualidade e valor.","/v2/rankings/besst-buffett-eua.html","Stocks","03","coral"),
        card("Magic Formula EUA","ROIC e preço no universo americano.","/v2/rankings/magic-formula-eua.html","Stocks","04","gold"),
        card("Renda Fixa FGC","Comparativo de produtos protegidos pelo FGC.","/v2/rankings/renda-fixa-fgc.html","Renda fixa","06","cyan"),
    ]
    outputs["rankings/index.html"] = hub("Rankings para investigar, não para obedecer.","Seleção quantitativa","Quatro estratégias de ações e um comparativo de renda fixa.",ranking_cards,"v2-rankings")
    outputs["radar/index.html"] = hub("Empresas para acompanhar.","Radar de qualidade","Watchlists são acompanhamento, não rankings ou ordens de compra.",[
        card("Watchlist Buffett EUA","Radar permanente de empresas excepcionais.","/v2/radar/watchlist-buffett-eua.html","Watchlist","01","blue"),
    ],"v2-radar")
    # Keep existing bookmarks working without indexing the retired route.
    outputs["rankings/watchlist-buffett-eua.html"] = document("Watchlist Buffett EUA", "A watchlist agora está no Radar.", '<section class="v2-hub-hero"><h1>Watchlist Buffett EUA</h1><a href="/v2/radar/watchlist-buffett-eua.html">Abrir radar Buffett EUA</a></section>', extra_head='<meta name="robots" content="noindex,nofollow,noarchive"><meta http-equiv="refresh" content="0;url=/v2/radar/watchlist-buffett-eua.html">')
    method_cards = [
        card("BESST & Buffett","Dividendos, perenidade, moat e margem de segurança.","/v2/metodos/besst-buffett.html","Metodologia","01","lime"),
        card("Magic Formula","Retorno sobre capital e rendimento do lucro.","/v2/metodos/magic-formula.html","Metodologia","02","cyan"),
    ]
    outputs["metodos/index.html"] = hub("A lógica vem antes da lista.","Metodologias","Entenda o que cada ranking procura, onde pode falhar e como deve ser interpretado.",method_cards,"v2-methods")
    indicator_cards = [
        card("Indicador Buffett","Bolsa dividida pelo PIB nos EUA e no Brasil.","/v2/indicadores/buffett.html","Valuation macro","01","blue"),
        card("Guia Bitcoin","Ciclos, preço e indicadores do ativo digital.","/v2/indicadores/bitcoin.html","Ativo digital","02","gold"),
    ]
    outputs["indicadores/index.html"] = hub("Contexto muda o peso de cada sinal.","Indicadores","Ferramentas para observar valuation agregado, ciclos e ativos fora das carteiras de ações.",indicator_cards,"v2-indicators")

    for route in ROUTES:
        outputs[route["target"]] = source_page(route)
    # Watchlists belong to Radar, not to the catalogue of methodologies.
    # Preserve the former URL as a non-indexed compatibility redirect.
    outputs["metodos/watchlist-buffett.html"] = document(
        "Watchlist Buffett EUA",
        "A lista de observação agora está no Radar.",
        '<section class="v2-hub-hero"><h1>Watchlist Buffett EUA</h1><p>Listas de observação ficam no Radar.</p><a href="/v2/radar/watchlist-buffett-eua.html">Abrir Watchlist Buffett EUA</a></section>',
        extra_head='<meta name="robots" content="noindex,nofollow,noarchive"><link rel="canonical" href="https://iaemloop.com.br/v2/radar/watchlist-buffett-eua.html"><meta http-equiv="refresh" content="0;url=/v2/radar/watchlist-buffett-eua.html">',
    )
    outputs["blog/index.html"] = blog_index(posts)
    for post in posts:
        outputs["blog/posts/" + str(post["slug"])] = blog_post(post)

    for rel, content in outputs.items():
        path = V2 / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(line.rstrip() for line in content.splitlines()), encoding="utf-8")

    route_map = {
        "generated_at":date.today().isoformat(),
        "legacy_preserved":True,
        "routes":sorted("/v2/" + rel for rel in outputs),
        "source_map":{r["source"]:"/v2/" + r["target"] for r in ROUTES},
        "blog_posts":len(posts),
    }
    (V2 / "content").mkdir(exist_ok=True)
    (V2 / "content/route-map.json").write_text(json.dumps(route_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    compatibility_redirects = {
        "/v2/rankings/watchlist-buffett-eua.html",
        "/v2/metodos/watchlist-buffett.html",
    }
    sitemap.extend(f"  <url><loc>{SITE}{route}</loc></url>" for route in route_map["routes"] if route not in compatibility_redirects)
    sitemap.append("</urlset>")
    (V2 / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    print(f"V2_BUILD_OK pages={len(outputs)} blog_posts={len(posts)}")


if __name__ == "__main__":
    build()
