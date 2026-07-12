import functools
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


@unittest.skipIf(async_playwright is None, "install requirements-crawler.txt and run crawl4ai-setup")
class BrowserAcceptanceTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        handler = functools.partial(SimpleHTTPRequestHandler, directory=root)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 844})
        await self.page.add_init_script("""
            class TestSpeechRecognition {
              constructor() { window.testRecognition = this; }
              start() {}
              stop() { if (this.onend) this.onend(); }
              emit(text, isFinal = false) {
                const result = [{ transcript: text }];
                result.isFinal = isFinal;
                this.onresult({ resultIndex: 0, results: [result] });
              }
            }
            window.SpeechRecognition = TestSpeechRecognition;
        """)
        await self.page.goto(self.url)
        await self.page.evaluate("localStorage.removeItem('dogcare-observations')")
        await self.page.reload()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_voice_note_appears_live_then_edits_and_saves_to_timeline(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click("#voice-note")
        await self.page.evaluate("testRecognition.emit('Billie drank water', false)")
        self.assertEqual(await self.page.input_value("#observation"), "Billie drank water")
        self.assertTrue(await self.page.is_editable("#observation") is False)

        await self.page.click("#voice-note")
        await self.page.fill("#observation", "Billie drank water after her walk.")
        await self.page.click("#save-observation")

        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue")
        self.assertEqual(await self.page.locator(".timeline-card p").first.text_content(), "Billie drank water after her walk.")

    async def test_mobile_handoff_has_no_horizontal_overflow(self):
        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="handoff"]')
        dimensions = await self.page.evaluate("({ viewport: innerWidth, content: document.documentElement.scrollWidth })")
        self.assertLessEqual(dimensions["content"], dimensions["viewport"])
        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue · Next carer")
