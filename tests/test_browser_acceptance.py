import asyncio
import os
import sys
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tenant_isolation import ApiServerTestCase, _cookie_from, _http, _latest_link  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(async_playwright is None, "run uv run --python 3.12 --with playwright python -m unittest discover -s tests -v")
class BrowserFixture(unittest.IsolatedAsyncioTestCase, ApiServerTestCase):
    api_mode = True
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = f"http://127.0.0.1:{cls.port}"
        status, body, _ = _http(cls.port, "POST", "/api/auth/request",
                                {"email": "adine@lebusdestoutous.example"})
        assert status == 200, body
        link = _latest_link(os.environ["DC_OUTBOX"], "adine@lebusdestoutous.example")
        path = urlparse(link).path + "?" + urlparse(link).query
        status, _, headers = _http(cls.port, "GET", path)
        assert status == 302, status
        cls.sid = _cookie_from(headers)
        assert cls.sid
        import server as _server  # noqa: E402
        cls.seed_obs = _server.SEED_OBS

    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.addAsyncCleanup(self.playwright.stop)
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context(viewport={"width": 390, "height": 844})
        self.addAsyncCleanup(self.context.close)
        await self.context.add_cookies([{
            "name": "dc_s", "value": self.sid, "url": self.url, "httpOnly": True,
        }])
        self.page = await self.context.new_page()
        self.page.set_default_timeout(10000)
        self.console_errors = []
        self.page.on("console", lambda message: self.console_errors.append(message.text) if message.type == "error" else None)
        self.page_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
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
        _http(self.port, "PUT", "/api/prefs", {"language": "en"}, cookie=self.sid)
        _http(self.port, "PUT", "/api/observations", {"observations": self.seed_obs}, cookie=self.sid)
        _http(self.port, "PUT", "/api/invites", {"invites": []}, cookie=self.sid)
        await self.page.goto(self.url)
        await self.wait_ready()

    async def wait_ready(self):
        await self.page.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
        if self.api_mode:
            self.assertTrue(await self.page.evaluate("DogCareAPI.ready"))
        self.assertGreater(await self.page.locator('#app-content > *').count(), 0)

    async def asyncTearDown(self):
        if self.api_mode:
            await self.page.evaluate("window.DogCareAPI?.whenSaved()")
        self.assertEqual(self.page_errors, [])


class BrowserAcceptanceTest(BrowserFixture):
    async def test_recording_player_keeps_supported_sources_and_escapes_its_label(self):
        for src in ('data:audio/webm;codecs=opus;base64,YQ==',
                    'data:audio/mp4;codecs=mp4a.40.2;base64,YQ==',
                    'data:audio/wav;base64,YQ==', '/api/blobs/' + 'a' * 32 + '.webm'):
            player = await self.page.evaluate('''src => {
                const template = document.createElement('template');
                template.innerHTML = audioHtml({url:src,duration:1}, '<voice "note">');
                const audio = template.content.querySelector('audio');
                return {src:audio?.getAttribute('src'), label:audio?.getAttribute('aria-label')};
            }''', src)
            self.assertEqual(player, {'src': src, 'label': 'Play <voice "note">'})

    async def test_stored_time_and_date_render_as_text_in_every_view(self):
        markup = '<svg onload="window.injected=true"></svg>'
        observations = {"billie": [
            {"id": 801, "text": "Time check", "title": "Time", "tags": [], "time": markup, "date": "Today"},
            {"id": 802, "text": "Date check", "title": "Date", "tags": [], "time": "09:00", "date": markup},
        ], "charlie": []}
        if self.api_mode:
            status, body, _ = _http(self.port, "PUT", "/api/observations", {"observations": observations}, self.sid)
            self.assertEqual(status, 200, body)
        else:
            await self.page.evaluate("data => localStorage.setItem('dogcare-observations', JSON.stringify(data))", observations)
        await self.page.reload()
        await self.wait_ready()
        for view in ('dashboard', 'dogs', 'handoff'):
            await self.page.evaluate('view => navigate(view)', view)
            self.assertIn(markup, await self.page.locator('#app-content').text_content())
            self.assertEqual(await self.page.locator('#app-content [onload], #app-content [onerror]').count(), 0)
            self.assertFalse(await self.page.evaluate('Boolean(window.injected)'))
        await self.page.evaluate("navigate('dogs')")
        self.assertEqual(await self.page.locator('#observation-802 time').text_content(), '09:00 · ' + markup)
        self.assertEqual(self.console_errors, [])

    async def test_voice_note_appears_live_then_edits_and_saves_to_timeline(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click("#record-audio")
        await self.page.evaluate("testRecognition.emit('Billie drank water', false)")
        self.assertEqual(await self.page.input_value("#observation"), "Billie drank water")
        self.assertTrue(await self.page.is_editable("#observation"))

        await self.page.click("#stop-audio")
        await self.page.fill("#observation", "Billie drank water after her walk.")
        await self.page.click("#save-observation")
        await self.page.wait_for_selector('.timeline-card')
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
        self.assertIn("business’s own account" if self.api_mode else "stay in this browser", await self.page.locator(".assistant-privacy").text_content())
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

    async def test_french_voice_note_persists_across_invite_and_muse_flows(self):
        await self.page.select_option("#language-picker", "fr")
        await self.page.wait_for_function('document.documentElement.lang === "fr"')
        self.assertEqual(await self.page.locator("html").get_attribute("lang"), "fr")

        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click("#record-audio")
        await self.page.evaluate("testRecognition.emit('Billie a bu de l eau', true)")
        await self.page.click("#stop-audio")
        await self.page.fill("#observation", "Billie a bu de l’eau après sa promenade.")
        await self.page.click("#save-observation")
        await self.page.wait_for_selector('.timeline-card')
        self.assertEqual(
            await self.page.locator(".timeline-card p").first.text_content(),
            "Billie a bu de l’eau après sa promenade.",
        )

        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="invite"]')
        self.assertEqual(await self.page.locator("h2").first.text_content(), "Préparer une invitation")
        await self.page.fill("#invite-name", "Camille Martin")
        await self.page.fill("#invite-email", "camille@example.com")
        await self.page.click("#create-invite")
        await self.page.wait_for_function('document.querySelector("#pending-invites").textContent.includes("Camille Martin")')
        self.assertIn("Camille Martin", await self.page.locator("#pending-invites").text_content())

        await self.page.click("#mobile-menu")
        await self.page.click('[data-page="assistant"]')
        self.assertEqual(await self.page.locator("h1").text_content(), "Muse · Votre assistant de soin")
        self.assertEqual(await self.page.locator("html").get_attribute("lang"), "fr")
        self.assertEqual(self.console_errors, [])

    async def test_mobile_capture_discloses_storage_and_transcription(self):
        await self.page.click('.topbar [data-go="capture"]')
        copy = await self.page.locator('.composer-actions small').text_content()
        self.assertIn("business’s own account" if self.api_mode else "stay in this browser", copy)
        self.assertIn("provider for transcription", await self.page.locator('.transcription-privacy').text_content())
        dimensions = await self.page.evaluate("({ viewport: innerWidth, content: document.documentElement.scrollWidth })")
        self.assertLessEqual(dimensions["content"], dimensions["viewport"])
        self.assertEqual(self.console_errors, [])


class QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class StaticBrowserAcceptanceTest(BrowserAcceptanceTest):
    api_mode = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietStaticHandler, directory=str(ROOT)))
        cls.static_thread = threading.Thread(target=cls.static_httpd.serve_forever, daemon=True)
        cls.static_thread.start()
        cls.url = f"http://127.0.0.1:{cls.static_httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.static_httpd.shutdown()
        cls.static_httpd.server_close()
        cls.static_thread.join(timeout=2)
        super().tearDownClass()


class AccountRecoveryTest(BrowserFixture):
    async def test_legacy_unsafe_recording_urls_never_render_or_fetch(self):
        urls = ['" onerror="window.injected=true', 'javascript:alert(1)',
                'https://example.com/voice.webm', '//example.com/voice.webm',
                '/api/auth/verify?t=untrusted']
        observations = {"billie": [{"id": index, "text": "Legacy voice", "title": "Voice",
                                    "tags": [], "audio": {"url": url, "duration": 1}}
                                   for index, url in enumerate(urls, 901)]}
        with self.server_mod.connection() as c:
            user = c.execute('SELECT id, business_id FROM user WHERE email=?', ('adine@lebusdestoutous.example',)).fetchone()
            self.server_mod.replace_observations(c, user['business_id'], user['id'], observations)
        requests = []
        self.page.on('request', lambda request: requests.append(request.url))
        await self.page.reload()
        await self.wait_ready()
        for view in ('dogs', 'gallery', 'story'):
            await self.page.evaluate('view => navigate(view)', view)
            self.assertEqual(await self.page.locator('#app-content audio').count(), 0)
        for url in urls:
            self.assertIsNone(await self.page.evaluate('url => audioFile({url})', url))
        self.assertFalse(any('example.com' in url or 'untrusted' in url for url in requests))
        self.assertFalse(await self.page.evaluate('Boolean(window.injected)'))
        self.assertEqual(self.console_errors, [])

    async def test_timed_out_capture_restores_interaction_and_keeps_draft(self):
        release = asyncio.Event()
        started = asyncio.Event()
        finished = asyncio.Event()

        async def stall(route):
            started.set()
            await release.wait()
            await route.abort()
            finished.set()

        await self.page.route('**/api/blobs', stall)
        await self.page.clock.install()
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'Keep this timed out draft')
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
        await self.page.click('#save-observation')
        await asyncio.wait_for(started.wait(), timeout=5)
        try:
            await self.page.clock.fast_forward(30001)
            self.assertFalse(await self.page.evaluate('savePending'))
            self.assertFalse(await self.page.evaluate("document.querySelector('.app-shell').inert"))
            self.assertTrue(await self.page.is_editable('#observation'))
            self.assertFalse(await self.page.is_disabled('#save-observation'))
            self.assertEqual(await self.page.input_value('#observation'), 'Keep this timed out draft')
            self.assertEqual(await self.page.evaluate('audioDraft.url'), 'data:audio/webm;base64,YQ==')
            await self.page.fill('#observation', 'Edited after timeout')
        finally:
            release.set()
            await asyncio.wait_for(finished.wait(), timeout=5)
        await self.page.unroute('**/api/blobs', stall)
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        self.assertEqual(await self.page.locator('.timeline-card p').first.text_content(), 'Edited after timeout')

    async def test_switching_accounts_in_another_tab_cannot_save_old_history_or_audio(self):
        original_sid = self.sid
        _, original, _ = _http(self.port, 'GET', '/api/state', cookie=original_sid)
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'Old account draft')
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
        other_sid = await self.fresh_account()
        other = await self.context.new_page()
        await other.goto(self.url)
        await other.wait_for_function('document.querySelector("#app-content").dataset.ready === "true"')
        _, before, _ = _http(self.port, 'GET', '/api/state', cookie=other_sid)
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await self.page.input_value('#observation'), 'Old account draft')
        self.assertIn('reload', await self.page.locator('#toast').text_content())
        _, after, _ = _http(self.port, 'GET', '/api/state', cookie=other_sid)
        self.assertEqual(after, before)
        _, after, _ = _http(self.port, 'GET', '/api/state', cookie=original_sid)
        self.assertEqual(after, original)
        self.assertFalse((Path(self.server_mod.blobs_dir()) / str(before['business_id'])).exists())

    async def test_two_tabs_keep_first_saved_note_and_preserve_stale_draft(self):
        other = await self.context.new_page()
        await other.goto(self.url)
        await other.wait_for_function('document.querySelector("#app-content").dataset.ready === "true"')
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'First tab note')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await other.click('.topbar [data-go="capture"]')
        await other.fill('#observation', 'Second tab draft')
        await other.click('#save-observation')
        await other.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await other.input_value('#observation'), 'Second tab draft')
        self.assertIn('reload', await other.locator('#toast').text_content())
        _, saved, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        self.assertEqual(saved['observations']['billie'][0]['text'], 'First tab note')
        self.assertNotIn('Second tab draft', [item['text'] for item in saved['observations']['billie']])

    async def test_invitation_waits_for_save_and_failed_preferences_preserve_state(self):
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="invite"]')
        await self.page.fill('#invite-name', 'Waiting Carer')
        await self.page.fill('#invite-email', 'waiting@example.com')
        release = asyncio.Event()
        started = asyncio.Event()

        async def delay(route):
            started.set()
            await release.wait()
            await route.continue_()

        await self.page.route('**/api/invites', delay)
        await self.page.click('#create-invite')
        await asyncio.wait_for(started.wait(), timeout=5)
        try:
            self.assertNotIn('Waiting Carer', await self.page.locator('#pending-invites').text_content())
            self.assertTrue(await self.page.is_disabled('#create-invite'))
        finally:
            release.set()
        await self.page.wait_for_function('document.querySelector("#pending-invites").textContent.includes("Waiting Carer")')
        await self.page.route('**/api/prefs', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
        await self.page.select_option('#language-picker', 'fr')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await self.page.input_value('#language-picker'), 'en')
        self.assertEqual(await self.page.locator('html').get_attribute('lang'), 'en')

    async def test_capture_waits_for_upload_and_save_before_clearing_draft(self):
        release = asyncio.Event()
        started = asyncio.Event()

        async def delay(route):
            started.set()
            await release.wait()
            await route.continue_()

        await self.page.route('**/api/blobs', delay)
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'Wait for my recording')
        await self.page.click('#save-observation')
        await asyncio.wait_for(started.wait(), timeout=5)
        try:
            self.assertEqual(await self.page.locator('#observation').count(), 1)
            self.assertEqual(await self.page.input_value('#observation'), 'Wait for my recording')
            self.assertTrue(await self.page.is_disabled('#save-observation'))
            self.assertTrue(await self.page.evaluate('Boolean(audioDraft)'))
            self.assertNotIn('Saved to', await self.page.locator('#toast').text_content())
        finally:
            release.set()
        await self.page.wait_for_selector('.timeline-card')
        self.assertEqual(await self.page.locator('.timeline-card p').first.text_content(), 'Wait for my recording')
        self.assertTrue(await self.page.evaluate('audioDraft === null'))
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('state.observations.billie[0].text'), 'Wait for my recording')

    async def test_failed_capture_keeps_text_and_audio_for_retry_without_duplicates(self):
        await self.page.route('**/api/observations', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'Retry this note')
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await self.page.locator('#observation').count(), 1)
        self.assertEqual(await self.page.input_value('#observation'), 'Retry this note')
        self.assertTrue(await self.page.evaluate('Boolean(audioDraft)'))
        self.assertNotIn('Saved to', await self.page.locator('#toast').text_content())
        self.assertEqual(await self.page.evaluate('state.observations.billie.filter(item => item.text === "Retry this note").length'), 0)
        await self.page.unroute('**/api/observations')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('state.observations.billie.filter(item => item.text === "Retry this note").length'), 1)

    async def fresh_account(self):
        sid = self.login(self.id().rsplit('.', 1)[-1] + '@example.com')
        await self.context.add_cookies([{'name': 'dc_s', 'value': sid, 'url': self.url, 'httpOnly': True}])
        return sid

    async def test_delayed_hydration_prevents_early_navigation_and_writes(self):
        release = asyncio.Event()

        async def delay(route):
            await release.wait()
            await route.continue_()

        await self.page.route('**/api/state', delay)
        await self.page.reload(wait_until='domcontentloaded')
        self.assertTrue(await self.page.is_disabled('#language-picker'))
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator('#observation').count(), 0)
        self.assertEqual(await self.page.locator('.timeline-card').count(), 0)
        release.set()
        await self.wait_ready()
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.locator('#observation').count(), 1)
        self.assertEqual(self.console_errors, [])

    async def test_failed_hydration_never_saves_demo_history_and_reload_recovers(self):
        await self.page.route('**/api/state', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
        await self.page.reload()
        await self.page.wait_for_selector('#retry-account')
        self.assertFalse(await self.page.evaluate('DogCareAPI.ready'))
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator('.timeline-card').count(), 0)
        await self.page.evaluate('DogCareAPI.saveObservations({billie:[{text:"Must never persist"}]})')
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        self.assertEqual(status, 200)
        self.assertEqual(state['observations'], self.seed_obs)
        await self.page.unroute('**/api/state')
        await self.page.click('#retry-account')
        await self.wait_ready()
        await self.page.click('.topbar [data-go="capture"]')
        self.assertTrue(await self.page.is_editable('#observation'))

    async def test_import_notice_precedes_recording_transfer_and_references_persist(self):
        sid = await self.fresh_account()
        audio = 'data:audio/webm;codecs=opus;base64,' + 'YWFh' * 600000
        snapshot = {'billie': [{'id': 81, 'text': 'Retained recording', 'tags': [], 'audio': {'url': audio, 'duration': 12}}]}
        await self.page.evaluate('(snapshot) => localStorage.setItem("dogcare-observations", JSON.stringify(snapshot))', snapshot)
        notices = []
        uploads = []

        async def accept(dialog):
            notices.append(dialog.message)
            await dialog.accept()

        self.page.on('dialog', accept)
        self.page.on('request', lambda request: uploads.append(len(notices)) if request.url.endswith('/api/blobs') else None)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(uploads, [1])
        self.assertIn('signed-in members of your business', notices[0])
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=sid)
        self.assertEqual(status, 200)
        self.assertTrue(state['imported'])
        self.assertTrue(state['observations']['billie'][0]['audio']['url'].startswith('/api/blobs/'))
        self.assertEqual(await self.page.evaluate('state.observations.billie[0].audio.url'), state['observations']['billie'][0]['audio']['url'])
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'A second note after import')
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(uploads, [1])
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(len(notices), 1)
        self.assertEqual(await self.page.evaluate('state.observations.billie[0].text'), 'A second note after import')

    async def test_failed_import_keeps_local_records_until_successful_retry(self):
        sid = await self.fresh_account()
        await self.page.evaluate('localStorage.setItem("dogcare-language", "fr")')
        await self.page.route('**/api/import', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
        await self.page.reload()
        await self.page.wait_for_selector('#retry-account')
        self.assertEqual(await self.page.evaluate('localStorage.getItem("dogcare-language")'), 'fr')
        self.assertEqual(await self.page.evaluate('Object.keys(localStorage).filter(key => key.startsWith("dogcare-imported")).length'), 0)
        self.assertEqual(await self.page.evaluate('DogCareAPI.getObservations().billie[0].text'), self.seed_obs['billie'][0]['text'])
        await self.page.unroute('**/api/import')
        await self.page.click('#retry-account')
        await self.wait_ready()
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=sid)
        self.assertEqual(status, 200)
        self.assertEqual(state['language'], 'fr')
        self.assertEqual(state['observations'], self.seed_obs)
        self.assertEqual(await self.page.locator('html').get_attribute('lang'), 'fr')

    async def test_empty_server_history_is_not_replaced_with_demo_data(self):
        _http(self.port, 'PUT', '/api/observations', {'observations': {}}, cookie=self.sid)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('Object.values(state.observations).flat().length'), 0)
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'First real observation')
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        self.assertEqual(status, 200)
        self.assertEqual(len(state['observations']['billie']), 1)
        self.assertEqual(state['observations']['charlie'], [])
        self.assertEqual(self.console_errors, [])
