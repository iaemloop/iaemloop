from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
POST = ROOT / "v2/blog/posts/2026-11-16-allstate-catastrofes-premios-reservas-3t26.html"
CSS = ROOT / "css/v2/public.css"


class V2BlogCardSpacingTest(unittest.TestCase):
    def test_allstate_card_labels_have_source_whitespace(self):
        """Prevent words from being concatenated if a future CSS rule regresses."""
        html = POST.read_text(encoding="utf-8")
        for block_class in ("scorecard", "matrix"):
            block = re.search(
                rf'<div class="{block_class}">(.*?)</div></div>', html, flags=re.DOTALL
            )
            self.assertIsNotNone(block, f"missing {block_class} block")
            self.assertNotRegex(block.group(1), r"</strong><span>")

    def test_card_labels_are_visually_separated_by_shared_css(self):
        """All V2 scorecard and matrix labels must render on separate lines."""
        css = re.sub(r"\s+", "", CSS.read_text(encoding="utf-8"))
        selector = (
            ".v2-article-content.scorecard>div>strong,"
            ".v2-article-content.scorecard>div>span,"
            ".v2-article-content.matrix>div>strong,"
            ".v2-article-content.matrix>div>span{display:block}"
        )
        self.assertIn(selector, css)


if __name__ == "__main__":
    unittest.main()
