#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

CARD_MAPPING = {
    "BESST & Buffett B3": "/privado/carteira_besst.html",
    "Magic Formula B3": "/privado/carteira_magic_formula.html",
    "BESST & Buffett Dolarizada": "/privado/carteira_besst_dolarizada.html",
    "Magic Formula Dolarizada": "/privado/carteira_magic_formula_dolarizada.html",
}

CUSTODY_PAGES = {
    "carteira_besst.html": "besst_b3",
    "carteira_magic_formula.html": "magic_b3",
    "carteira_besst_dolarizada.html": "besst_usd",
    "carteira_magic_formula_dolarizada.html": "magic_usd",
}


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags(path):
    parser = TagCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.tags


class PrivateCustodyV2Test(unittest.TestCase):
    def test_portfolio_cards_open_exact_legacy_custody_endpoints(self):
        path = ROOT / "privado/v2/minha-carteira.html"
        found = {attrs.get("data-custody-label"): attrs.get("href") for tag, attrs in tags(path) if tag == "a" and attrs.get("data-custody-label")}
        self.assertEqual(found, CARD_MAPPING)
        for href in found.values():
            self.assertNotIn("graficos-custodia", href)
            self.assertNotIn("portfolio_key", href)

    def test_each_legacy_endpoint_keeps_secure_loader_and_uses_v2_assets(self):
        for filename, slug in CUSTODY_PAGES.items():
            with self.subTest(filename=filename):
                path = ROOT / "privado" / filename
                parsed = tags(path)
                html = path.read_text(encoding="utf-8")
                self.assertIn('body class="v2-page v2-custody-page"', html)
                links = [attrs.get("href") for tag, attrs in parsed if tag == "link"]
                scripts = [attrs.get("src") for tag, attrs in parsed if tag == "script" and attrs.get("src")]
                self.assertIn("/css/v2/observatory.css?v=20261016-session2", links)
                self.assertIn("/css/v2/custody.css?v=20261016-session2", links)
                self.assertIn("../js/iaemloop-auth-config.js?v=20261016-session2", scripts)
                self.assertIn("../js/v2/auth.js?v=20261016-session2", scripts)
                self.assertIn("../js/v2/custody-shell.js?v=20261016-session2", scripts)
                private_sections = [attrs for tag, attrs in parsed if tag == "section" and attrs.get("data-private-page")]
                self.assertEqual(private_sections[0]["data-private-page"], slug)
                frames = [attrs for tag, attrs in parsed if tag == "iframe" and "data-private-frame" in attrs]
                self.assertEqual(len(frames), 1)
                self.assertEqual(frames[0].get("sandbox"), "allow-popups allow-popups-to-escape-sandbox allow-same-origin")
                self.assertNotIn("allow-scripts", frames[0].get("sandbox", ""))
                self.assertIn("noindex, nofollow, noarchive", html)

    def test_asset_inputs_use_empty_runtime_datalist(self):
        path = ROOT / "privado/v2/minha-carteira.html"
        parsed = tags(path)
        inputs = {attrs.get("id"): attrs for tag, attrs in parsed if tag == "input"}
        self.assertEqual(inputs["holding-symbol"].get("list"), "asset-catalog")
        self.assertEqual(inputs["transaction-symbol"].get("list"), "asset-catalog")
        datalists = [attrs for tag, attrs in parsed if tag == "datalist"]
        self.assertEqual([attrs.get("id") for attrs in datalists], ["asset-catalog"])
        html = path.read_text(encoding="utf-8")
        self.assertNotIn('<option value="PETR4"', html)
        self.assertIn("../../js/privado/asset-search.js?v=20261016-session2", html)


if __name__ == "__main__":
    unittest.main()
