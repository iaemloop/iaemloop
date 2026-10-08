#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Build the isolated IA em Loop V2 public site from read-only V1 sources."""
from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "v2"
SITE = "https://iaemloop.com.br"

ROUTES = [
    {"source":"metodologia_barsi.html","target":"rankings/besst-buffett-b3.html","title":"BESST & Buffett B3","category":"Ranking B3","description":"Dividendos, setores perenes, qualidade e valor intrínseco em uma mesma leitura."},
    {"source":"historico_rankings.html","target":"rankings/historico/besst-buffett-b3.html","title":"Histórico BESST & Buffett B3","category":"Histórico B3","description":"Evolução mensal do ranking BESST & Buffett na bolsa brasileira."},
    {"source":"greenblatt_ned_landing_original.html","target":"rankings/magic-formula-b3.html","title":"Magic Formula B3","category":"Ranking B3","description":"Empresas eficientes e baratas ordenadas por ROIC e Earnings Yield."},
    {"source":"historico_rankings_magic_formula.html","target":"rankings/historico/magic-formula-b3.html","title":"Histórico Magic Formula B3","category":"Histórico B3","description":"Arquivo mensal do ranking Magic Formula para ações brasileiras."},
    {"source":"ranking_besst_buffett_dolarizado.html","target":"rankings/besst-buffett-eua.html","title":"BESST & Buffett EUA","category":"Ranking internacional","description":"Qualidade, previsibilidade e valuation aplicados a stocks americanas."},
    {"source":"historico_rankings_dolarizados.html","target":"rankings/historico/besst-buffett-eua.html","title":"Histórico BESST & Buffett EUA","category":"Histórico internacional","description":"Evolução mensal do ranking dolarizado BESST & Buffett."},
    {"source":"ranking_magic_formula_dolarizada.html","target":"rankings/magic-formula-eua.html","title":"Magic Formula EUA","category":"Ranking internacional","description":"ROIC, preço e eficiência operacional no universo de stocks."},
    {"source":"historico_rankings_magic_formula_dolarizada.html","target":"rankings/historico/magic-formula-eua.html","title":"Histórico Magic Formula EUA","category":"Histórico internacional","description":"Arquivo mensal da Magic Formula dolarizada."},
    {"source":"watchlist_buffett_permanente_eua.html","target":"rankings/watchlist-buffett-eua.html","title":"Watchlist Buffett Permanente EUA","category":"Radar internacional","description":"Empresas excepcionais para acompanhar continuamente, sem compra automática."},
    {"source":"historico_watchlist_buffett_permanente_eua.html","target":"rankings/historico/watchlist-buffett-eua.html","title":"Histórico da Watchlist Buffett EUA","category":"Histórico internacional","description":"Mudanças e permanências do radar Buffett ao longo do tempo."},
    {"source":"metodologia_watchlist_eua.html","target":"metodos/watchlist-buffett.html","title":"Método Watchlist Buffett EUA","category":"Metodologia","description":"Critérios de qualidade, resiliência e acompanhamento da watchlist permanente."},
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
})

NAV = [
    ("Início", "/v2/index.html"),
    ("Rankings", "/v2/rankings/index.html"),
    ("Métodos", "/v2/metodos/index.html"),
    ("Indicadores", "/v2/indicadores/index.html"),
    ("Blog", "/v2/blog/index.html"),
]


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


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


def sanitize_public_article(article: BeautifulSoup) -> None:
    """Remove real-custody disclosures while leaving public analysis intact."""
    for span in list(article.select(".meta span, .chips span")):
        if re.search(r"carteira real|custódia|aporte real|posição real", clean_text(span.get_text(" ")), re.I):
            span.decompose()

    for heading in list(article.find_all(["h2", "h3"])):
        heading_text = clean_text(heading.get_text(" "))
        if not re.search(r"carteira real|custódia|aporte real|posição na carteira", heading_text, re.I):
            continue
        siblings = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in ("h2", "h3"):
                break
            siblings.append(sibling)
        section_text = clean_text(" ".join(getattr(node, "get_text", lambda *_: str(node))(" ") for node in siblings))
        if PRIVATE_DETAIL.search(section_text):
            for sibling in siblings:
                sibling.extract()
            heading.decompose()

    for node in list(article.find_all(["p", "li", "tr", "div"])):
        if node.parent is None:
            continue
        text = clean_text(node.get_text(" "))
        if PRIVATE_CONTEXT.search(text) and (PRIVATE_DETAIL.search(text) or re.search(r"carteira real|custódia|aporte real", text, re.I)):
            node.decompose()

    # Editorial typo fixes are applied only to the isolated V2 output.
    for text_node in article.find_all(string=True):
        fixed = str(text_node).replace("posição que投入 no início", "posição iniciada no período")
        fixed = fixed.replace("o papéis está próximo", "o papel está próximo")
        fixed = re.sub(r"carteira real", "acompanhamento privado", fixed, flags=re.I)
        fixed = re.sub(r"custódia real", "custódia privada", fixed, flags=re.I)
        fixed = re.sub(r"aporte real", "acompanhamento privado", fixed, flags=re.I)
        if fixed != str(text_node):
            text_node.replace_with(fixed)
    for tag in article.find_all(True):
        for attr in ("alt", "title", "aria-label"):
            if not tag.has_attr(attr):
                continue
            value = str(tag[attr])
            value = re.sub(r"carteira real", "acompanhamento privado", value, flags=re.I)
            value = re.sub(r"custódia real", "custódia privada", value, flags=re.I)
            value = re.sub(r"aporte real", "acompanhamento privado", value, flags=re.I)
            tag[attr] = value


def nav_html() -> str:
    links = "".join(f'<a href="{href}" data-v2-nav>{label}</a>' for label, href in NAV)
    return f'''<header class="v2-site-nav v2-global-nav">
      <a class="v2-brand" href="/v2/index.html" aria-label="IA em Loop V2"><span class="v2-brand-mark">∞</span><span>IA em Loop<small>Investment observatory · V2</small></span></a>
      <button class="v2-menu-toggle" type="button" aria-expanded="false" aria-controls="v2-main-menu"><span></span><span></span><span></span><b class="sr-only">Abrir menu</b></button>
      <nav class="v2-main-menu" id="v2-main-menu" aria-label="Navegação principal">{links}<a class="v2-primary" href="/v2/area-privada.html?redirect=/privado/v2/index.html">Área privada</a></nav>
    </header>'''


def footer_html() -> str:
    return '''<footer class="v2-footer"><div><a class="v2-brand" href="/v2/index.html"><span class="v2-brand-mark">∞</span><span>IA em Loop<small>Dados, método e skin in the game</small></span></a><p>Conteúdo educacional. Não é recomendação personalizada de investimento.</p></div><nav aria-label="Links do rodapé"><a href="/v2/rankings/index.html">Rankings</a><a href="/v2/metodos/index.html">Metodologias</a><a href="/v2/indicadores/index.html">Indicadores</a><a href="/v2/blog/index.html">Blog</a><a href="/index.html">Visual clássico</a></nav></footer>'''


def document(title: str, description: str, body: str, extra_head: str = "", body_class: str = "") -> str:
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{html.escape(description, quote=True)}"><title>{html.escape(title)} | IA em Loop V2</title><link rel="stylesheet" href="/css/v2/observatory.css?v=4"><link rel="stylesheet" href="/css/v2/public.css?v=4">{extra_head}</head>
<body class="v2-page v2-public {body_class}">{nav_html()}<main>{body}</main>{footer_html()}<script src="/js/v2/public.js?v=4"></script><script src="/js/v2/shell.js?v=4"></script></body></html>'''


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
    if route["source"] == "ranking_fgc.html":
        inner = inner.replace('/scripts/fgc-dynamic.js?v=20260914', '/js/v2/fgc.js?v=4')
    breadcrumb = f'''<section class="v2-page-intro"><p class="v2-kicker">{html.escape(route['category'])}</p><div><h1>{html.escape(route['title'])}</h1><p>{html.escape(route['description'])}</p></div></section>'''
    source_note = f'''<div class="v2-source-ribbon"><span>Visual V2</span><p>Conteúdo público sincronizado da fonte canônica <code>/{html.escape(route['source'])}</code>.</p></div>'''
    body = breadcrumb + source_note + f'<div class="v2-content v2-imported-content">{inner}</div>'
    return document(route["title"], source_description, body, body_class="v2-data-page")


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

    return sorted(posts, key=date_key, reverse=True)


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
        card("Watchlist Buffett EUA","Radar permanente de empresas excepcionais.","/v2/rankings/watchlist-buffett-eua.html","Watchlist","05","blue"),
        card("Renda Fixa FGC","Comparativo de produtos protegidos pelo FGC.","/v2/rankings/renda-fixa-fgc.html","Renda fixa","06","cyan"),
    ]
    outputs["rankings/index.html"] = hub("Rankings para investigar, não para obedecer.","Seleção quantitativa","Quatro estratégias de ações, uma watchlist permanente e um radar de renda fixa.",ranking_cards,"v2-rankings")
    method_cards = [
        card("BESST & Buffett","Dividendos, perenidade, moat e margem de segurança.","/v2/metodos/besst-buffett.html","Metodologia","01","lime"),
        card("Magic Formula","Retorno sobre capital e rendimento do lucro.","/v2/metodos/magic-formula.html","Metodologia","02","cyan"),
        card("Watchlist Buffett EUA","Qualidade permanente sem automatizar compra.","/v2/metodos/watchlist-buffett.html","Metodologia","03","gold"),
    ]
    outputs["metodos/index.html"] = hub("A lógica vem antes da lista.","Metodologias","Entenda o que cada ranking procura, onde pode falhar e como deve ser interpretado.",method_cards,"v2-methods")
    indicator_cards = [
        card("Indicador Buffett","Bolsa dividida pelo PIB nos EUA e no Brasil.","/v2/indicadores/buffett.html","Valuation macro","01","blue"),
        card("Guia Bitcoin","Ciclos, preço e indicadores do ativo digital.","/v2/indicadores/bitcoin.html","Ativo digital","02","gold"),
    ]
    outputs["indicadores/index.html"] = hub("Contexto muda o peso de cada sinal.","Indicadores","Ferramentas para observar valuation agregado, ciclos e ativos fora das carteiras de ações.",indicator_cards,"v2-indicators")

    for route in ROUTES:
        outputs[route["target"]] = source_page(route)
    outputs["blog/index.html"] = blog_index(posts)
    for post in posts:
        outputs["blog/posts/" + str(post["slug"])] = blog_post(post)

    for rel, content in outputs.items():
        path = V2 / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

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
    sitemap.extend(f"  <url><loc>{SITE}{route}</loc></url>" for route in route_map["routes"])
    sitemap.append("</urlset>")
    (V2 / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    print(f"V2_BUILD_OK pages={len(outputs)} blog_posts={len(posts)}")


if __name__ == "__main__":
    build()
