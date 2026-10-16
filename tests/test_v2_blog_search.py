#!/usr/bin/env python3
import contextlib
import http.server
import os
import shutil
import socket
import threading
import unittest
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, _format, *_args):
        pass

    def translate_path(self, path):
        path = unquote(path.split('?', 1)[0].split('#', 1)[0])
        return str(ROOT / path.lstrip('/'))


@contextlib.contextmanager
def serve_site():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class BlogSearchRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = serve_site()
        cls.base_url = cls.server.__enter__()
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
        launch_options = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            launch_options['executable_path'] = executable
        cls.browser = cls.playwright.chromium.launch(**launch_options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.__exit__(None, None, None)

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.goto(f'{self.base_url}/v2/blog/index.html', wait_until='networkidle')
        self.input = self.page.locator('.v2-search-input')
        self.cards = self.page.locator('.v2-post-card')
        self.empty = self.page.locator('.v2-empty-state')
        self.total = self.cards.count()
        self.assertGreater(self.total, 1)

    def tearDown(self):
        self.page.close()

    def visible_cards(self):
        return self.page.locator('.v2-post-card:visible')

    def assert_sapr11_results(self, expected_count):
        visible = self.visible_cards()
        hidden_count = self.page.locator('.v2-post-card[hidden]').count()
        displays = self.page.locator('.v2-post-card[hidden]').evaluate_all(
            "cards => [...new Set(cards.map(card => getComputedStyle(card).display))]"
        )
        self.assertEqual(
            visible.count(),
            expected_count,
            f'expected {expected_count} visible SAPR11 card(s); hidden={hidden_count}, hidden computed displays={displays}',
        )
        self.assertTrue(all('SAPR11' in text for text in visible.all_inner_texts()))
        self.assertTrue(self.empty.is_hidden())

    def test_input_search_enter_words_no_result_and_clear(self):
        # The input event filters immediately and CSS must honor the hidden attribute.
        self.input.fill('sapr11')
        self.assert_sapr11_results(2)

        # Search terms are case/accent insensitive and may appear in any order.
        self.input.fill('PRECATÓRIO sanepar SAPR11')
        self.assert_sapr11_results(1)

        # Enter applies a value even when no input event was dispatched.
        self.input.evaluate("input => { input.value = 'sanepar sapr11'; }")
        self.input.press('Enter')
        self.assert_sapr11_results(1)

        # The native search event (including a search-field clear action) is supported.
        self.input.evaluate("input => { input.value = 'sapr11'; input.dispatchEvent(new Event('search')); }")
        self.assert_sapr11_results(2)

        self.input.fill('resultado-impossivel-xyz')
        self.assertEqual(self.visible_cards().count(), 0)
        self.assertTrue(self.empty.is_visible())

        self.input.evaluate("input => { input.value = ''; input.dispatchEvent(new Event('search')); }")
        self.assertEqual(self.visible_cards().count(), self.total)
        self.assertTrue(self.empty.is_hidden())
        print(
            f'BLOG_SEARCH_BROWSER_OK total={self.total} sapr11=2 multiword=1 '
            f'enter=1 no_result=0 clear={self.total}'
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
