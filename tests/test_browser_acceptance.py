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
        cls.thread.join(timeout=2)

    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.addAsyncCleanup(self.playwright.stop)
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 844})
        self.console_errors = []
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        await self.page.add_init_script("""
            class TestSpeechRecognition {
              constructor() { window.testRecognition = this; }
              start() { if (this.onstart) this.onstart(); }
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

    async def test_voice_note_appears_live_then_edits_and_saves_to_timeline(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click("#record-audio")
        await self.page.evaluate("testRecognition.emit('Billie drank water', false)")
        self.assertEqual(await self.page.input_value("#observation"), "Billie drank water")
        self.assertTrue(await self.page.is_editable("#observation"))

        await self.page.click("#stop-audio")
        await self.page.fill("#observation", "Billie drank water after her walk.")
        await self.page.click("#save-observation")

        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue")
        self.assertEqual(await self.page.locator(".timeline-card p").first.text_content(), "Billie drank water after her walk.")
        self.assertEqual(self.console_errors, [])

    async def test_mobile_handoff_has_no_horizontal_overflow(self):
        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="handoff"]')
        dimensions = await self.page.evaluate("({ viewport: innerWidth, content: document.documentElement.scrollWidth })")
        self.assertLessEqual(dimensions["content"], dimensions["viewport"])
        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue · Next carer")
        evidence = self.page.locator("[data-evidence-id]").first
        observation_id = await evidence.get_attribute("data-evidence-id")
        await evidence.click()
        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue")
        self.assertEqual(await self.page.locator(f"#observation-{observation_id}").count(), 1)
        self.assertEqual(self.console_errors, [])

    async def test_muse_gives_a_private_briefing_and_opens_the_handoff(self):
        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="assistant"]')

        self.assertEqual(await self.page.locator("h1").text_content(), "Muse · Your care assistant")
        self.assertIn("Billie Blue", await self.page.locator("#assistant-thread").text_content())
        self.assertIn("Charlie Rose", await self.page.locator("#assistant-thread").text_content())
        self.assertIn("stay in this browser", await self.page.locator(".assistant-privacy").text_content())
        dimensions = await self.page.evaluate("({ viewport: innerWidth, content: document.documentElement.scrollWidth })")
        self.assertLessEqual(dimensions["content"], dimensions["viewport"])

        await self.page.click('[data-assistant-prompt="attention"]')
        response = await self.page.locator(".assistant-message.muse").last.text_content()
        self.assertIn("not a diagnosis", response)
        self.assertTrue(await self.page.locator("#assistant-question").evaluate("element => element === document.activeElement"))

        await self.page.fill("#assistant-question", "Open a new care note")
        await self.page.press("#assistant-question", "Enter")
        self.assertIn("speak naturally", await self.page.locator(".assistant-message.muse").last.text_content())
        self.assertTrue(await self.page.locator("#assistant-question").evaluate("element => element === document.activeElement"))

        await self.page.click('[data-assistant-action="capture"]')
        self.assertEqual(await self.page.locator("h1").text_content(), "Capture the moment")
        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="assistant"]')
        await self.page.click('[data-assistant-action="story"]')
        self.assertEqual(await self.page.locator("h1").text_content(), "A lovely day, ready to share")
        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="assistant"]')

        await self.page.click('[data-assistant-action="handoff"]')
        self.assertEqual(await self.page.locator("h1").text_content(), "Billie Blue · Next carer")
        dimensions = await self.page.evaluate("({ viewport: innerWidth, content: document.documentElement.scrollWidth })")
        self.assertLessEqual(dimensions["content"], dimensions["viewport"])
        self.assertEqual(self.console_errors, [])
