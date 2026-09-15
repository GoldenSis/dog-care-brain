import asyncio
import json
import os
import sys
import threading
import unittest
from datetime import datetime, timezone
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
        self.context = await self.browser.new_context(viewport={"width": 390, "height": 844}, timezone_id='Europe/Paris')
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
        if not self.api_mode:
            # Shared journey assertions use English; the anonymous default is
            # checked separately from this explicit saved preference.
            await self.page.select_option('#language-picker', 'en')

    async def wait_ready(self):
        await self.page.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
        if self.api_mode:
            self.assertTrue(await self.page.evaluate("DogCareAPI.ready"))
        self.assertGreater(await self.page.locator('#app-content > *').count(), 0)

    async def capture_evidence(self, name):
        directory = os.environ.get('DOGCARE_EVIDENCE_DIR')
        if directory:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            await self.page.screenshot(path=str(path / name), full_page=True,
                                       animations='disabled')

    async def asyncTearDown(self):
        if self.api_mode:
            await self.page.evaluate("window.DogCareAPI?.whenSaved()")
        self.assertEqual(self.page_errors, [])


class BrowserAcceptanceTest(BrowserFixture):
    async def test_capture_drafts_stay_with_their_dog_across_navigation(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('#observation')
        self.assertEqual(await self.page.locator('#observation').count(), 1)
        billie_note = 'TEST MUSE — Billie drank water after a 10 minute walk.'
        charlie_note = 'TEST MUSE — Charlie rested for 15 minutes.'
        await self.page.fill('#observation', billie_note)
        await self.page.click('[data-capture-dog="billie"]')
        await self.capture_evidence(f'draft-reselect-{self.api_mode}.png')
        self.assertEqual(await self.page.input_value('#observation'), billie_note)
        await self.page.click('[data-capture-dog="charlie"]')
        self.assertEqual(await self.page.input_value('#observation'), '')
        await self.page.fill('#observation', charlie_note)
        await self.page.select_option('#language-picker', 'fr')
        self.assertEqual(await self.page.input_value('#observation'), charlie_note)
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="handoff"]')
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.input_value('#observation'), charlie_note)
        await self.page.click('[data-capture-dog="billie"]')
        self.assertEqual(await self.page.input_value('#observation'), billie_note)
        self.assertIn('Nutrition', await self.page.locator('#detected').text_content())
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.input_value('#observation'), '')
        await self.page.click('[data-capture-dog="charlie"]')
        self.assertEqual(await self.page.input_value('#observation'), charlie_note)
        self.assertEqual(self.console_errors, [])

    async def test_changing_language_does_not_translate_a_users_draft(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'Care moment')
        await self.page.select_option('#language-picker', 'fr')
        self.assertEqual(await self.page.input_value('#observation'), 'Care moment')
        await self.page.click('#observation')
        await self.page.fill('#observation', '<textarea> literal text & accents é')
        await self.page.click('[data-capture-dog="billie"]')
        self.assertEqual(await self.page.input_value('#observation'), '<textarea> literal text & accents é')

    async def test_old_dictation_callbacks_cannot_change_another_dogs_draft(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('#record-audio')
        await self.page.evaluate("window.oldRecognition = testRecognition; oldRecognition.emit('TEST MUSE — Billie drank water', true)")
        await self.page.click('[data-capture-dog="charlie"]')
        await self.page.click('#record-audio')
        await self.page.evaluate("testRecognition.emit('TEST MUSE — Charlie rested', true)")
        await self.page.evaluate("oldRecognition.onstart(); oldRecognition.emit('WRONG DOG', true); oldRecognition.onerror({error:'not-allowed'}); oldRecognition.onend()")
        self.assertEqual(await self.page.input_value('#observation'), 'TEST MUSE — Charlie rested')
        self.assertTrue(await self.page.is_visible('#listening-badge'))
        self.assertNotIn('denied', await self.page.locator('#transcription-status').text_content())
        await self.page.click('#stop-audio')
        await self.page.click('[data-capture-dog="billie"]')
        self.assertEqual(await self.page.input_value('#observation'), 'TEST MUSE — Billie drank water')
        self.assertEqual(self.console_errors, [])

    async def test_stop_accepts_final_dictation_but_manual_correction_wins(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('#record-audio')
        await self.page.evaluate("window.stoppingRecognition = testRecognition; stoppingRecognition.stop = () => {}; stoppingRecognition.emit('TEST MUSE — drank', false)")
        await self.page.click('#stop-audio')
        await self.page.evaluate("stoppingRecognition.emit('TEST MUSE — drank water', true); stoppingRecognition.onend()")
        self.assertEqual(await self.page.input_value('#observation'), 'TEST MUSE — drank water')
        self.assertFalse(await self.page.is_visible('#listening-badge'))
        await self.page.fill('#observation', '')
        await self.page.click('#record-audio')
        await self.page.evaluate("window.stoppingRecognition = testRecognition; stoppingRecognition.stop = () => {}; stoppingRecognition.emit('TEST MUSE — 10 minutes', false)")
        await self.page.click('#stop-audio')
        await self.page.fill('#observation', 'TEST MUSE — corrected to 15 minutes')
        await self.page.evaluate("stoppingRecognition.emit('TEST MUSE — 10 minutes', true); stoppingRecognition.onend()")
        self.assertEqual(await self.page.input_value('#observation'), 'TEST MUSE — corrected to 15 minutes')
        self.assertEqual(self.console_errors, [])

    async def test_corrected_note_survives_reload_and_leaves_next_days_handoff(self):
        # 23:55 in Paris: UTC conversion would misdate the next-day boundary.
        await self.page.clock.install(time=datetime(2030, 1, 2, 22, 55, tzinfo=timezone.utc))
        await self.page.select_option('#language-picker', 'fr')
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('[data-capture-dog="charlie"]')
        await self.page.fill('#observation', 'TEST MUSE — repos pendant 10 minutes.')
        corrected = 'TEST MUSE — repos pendant 15 minutes.'
        await self.page.fill('#observation', corrected)
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        self.assertEqual(await self.page.locator('h1').text_content(), 'Charlie Rose')
        self.assertEqual(await self.page.locator('.timeline-card p').first.text_content(), corrected)
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="handoff"]')
        await self.page.click('[data-handoff-dog="charlie"]')
        evidence = self.page.locator('.evidence-row').filter(has_text=corrected)
        self.assertEqual(await evidence.count(), 1)
        observation_id = await evidence.get_attribute('data-evidence-id')
        await self.capture_evidence(f'corrected-handoff-{self.api_mode}.png')
        await evidence.click()
        self.assertEqual(await self.page.locator(f'#observation-{observation_id} > p').text_content(), corrected)
        await self.page.click('[data-dog="billie"]')
        self.assertNotIn(corrected, await self.page.locator('.timeline').text_content())
        await self.page.clock.fast_forward(10 * 60 * 1000)
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="handoff"]')
        await self.page.click('[data-handoff-dog="charlie"]')
        await self.capture_evidence(f'next-day-handoff-{self.api_mode}.png')
        self.assertEqual(await self.page.locator('.evidence-row').filter(has_text=corrected).count(), 0)
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator(f'#observation-{observation_id} > p').text_content(), corrected)
        self.assertNotIn('Aujourd’hui', await self.page.locator(f'#observation-{observation_id} time').text_content())
        self.assertEqual(self.console_errors, [])

    async def test_legacy_timestamped_notes_keep_history_without_becoming_today(self):
        await self.page.clock.install(time=datetime(2030, 1, 2, 10, tzinfo=timezone.utc))
        old_id = int(datetime(2030, 1, 1, 10, tzinfo=timezone.utc).timestamp() * 1000)
        observations = {'billie': [
            {'id': old_id, 'text': 'TEST MUSE — yesterday only', 'title': 'Care moment',
             'tags': ['General care'], 'time': '10:00', 'date': 'Today'},
        ], 'charlie': []}
        if self.api_mode:
            status, body, _ = _http(self.port, 'PUT', '/api/observations', {'observations': observations}, self.sid)
            self.assertEqual(status, 200, body)
        else:
            await self.page.evaluate("data => localStorage.setItem('dogcare-observations', JSON.stringify(data))", observations)
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="handoff"]')
        await self.capture_evidence(f'legacy-handoff-{self.api_mode}.png')
        self.assertEqual(await self.page.locator('.evidence-row').count(), 0)
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator(f'#observation-{old_id} > p').text_content(), observations['billie'][0]['text'])
        self.assertNotIn('Today', await self.page.locator(f'#observation-{old_id} time').text_content())

    async def test_audio_file_preserves_inline_recordings(self):
        result = await self.page.evaluate('''async () => {
            const file = await audioFile({url:'data:audio/webm;base64,YQ=='});
            return {type:file.type, text:await file.text(), name:file.name};
        }''')
        self.assertEqual(result, {'type': 'audio/webm', 'text': 'a', 'name': 'dogcare-voice-note.webm'})
        self.assertEqual(self.console_errors, [])

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
            {"id": 0, "text": "Time check", "title": "Time", "tags": [], "time": markup, "date": "Today"},
            {"id": 802, "text": "Date check", "title": "Date", "tags": [], "time": "09:00", "date": markup},
        ], "charlie": []}
        if self.api_mode:
            status, body, _ = _http(self.port, "PUT", "/api/observations", {"observations": observations}, self.sid)
            self.assertEqual(status, 200, body)
        else:
            await self.page.evaluate("data => localStorage.setItem('dogcare-observations', JSON.stringify(data))", observations)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.locator('.activity-row').get_attribute('data-evidence-id'), '0')
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

    async def test_failed_browser_save_keeps_draft_and_retry_persists_once(self):
        original = await self.page.evaluate("localStorage.getItem('dogcare-observations')")
        await self.page.click('.topbar [data-go="capture"]')
        note = 'TEST MUSE — keep this note when storage fails.'
        await self.page.fill('#observation', note)
        await self.page.evaluate('''() => {
            window.originalSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function(key, value) {
                if (key === 'dogcare-observations') throw new DOMException('Full', 'QuotaExceededError');
                return window.originalSetItem.call(this, key, value);
            };
        }''')
        await self.page.click('#save-observation')
        await self.capture_evidence('failed-storage.png')
        self.assertEqual(await self.page.locator('#observation').count(), 1)
        self.assertEqual(await self.page.input_value('#observation'), note)
        self.assertIn('not saved', (await self.page.locator('[role="alert"]').text_content()).lower())
        self.assertEqual(await self.page.evaluate("localStorage.getItem('dogcare-observations')"), original)
        await self.page.evaluate('() => { Storage.prototype.setItem = window.originalSetItem; }')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator('.timeline-card').filter(has_text=note).count(), 1)
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.input_value('#observation'), '')
        self.assertEqual(self.console_errors, [])

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

    async def test_french_default_and_saved_language_survive_reload(self):
        await self.page.evaluate("localStorage.removeItem('dogcare-language')")
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.locator('html').get_attribute('lang'), 'fr')
        self.assertEqual(await self.page.input_value('#language-picker'), 'fr')
        await self.page.select_option('#language-picker', 'en')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.locator('html').get_attribute('lang'), 'en')
        self.assertEqual(await self.page.input_value('#language-picker'), 'en')
        self.assertEqual(self.console_errors, [])

    async def test_static_records_import_once_and_survive_a_fresh_browser(self):
        self.assertTrue(await self.page.evaluate('window.DOGCARE_API === undefined'))
        api_requests = []
        self.page.on('request', lambda request: api_requests.append(request.url)
                     if '/api/' in request.url else None)
        note = 'Billie drank water after her woodland walk.'
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', note)
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.capture_evidence('static-timeline-mobile.png')
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="invite"]')
        await self.page.fill('#invite-name', 'Demo Carer')
        await self.page.fill('#invite-email', 'carer@example.com')
        await self.page.click('#create-invite')
        await self.page.select_option('#language-picker', 'fr')
        await self.page.reload()
        await self.wait_ready()
        local = await self.page.evaluate('''() => Object.fromEntries(
            ['observations', 'invites', 'language'].map(key =>
                [key, localStorage.getItem('dogcare-' + key)]))''')
        self.assertEqual(json.loads(local['observations'])['billie'][0]['text'], note)
        self.assertEqual(json.loads(local['invites'])[0]['name'], 'Demo Carer')
        self.assertEqual(local['language'], 'fr')
        self.assertEqual(api_requests, [])

        # Switch the actual serving handler at the same origin, as when replacing
        # the static launcher with api/server.py. No browser storage is seeded.
        self.static_httpd.RequestHandlerClass = self.server_mod.Handler
        self.addCleanup(setattr, self.static_httpd, 'RequestHandlerClass',
                        partial(QuietStaticHandler, directory=str(ROOT)))
        self.api_mode = True
        await self.context.clear_cookies()
        email = 'migration-owner@example.com'
        response = await self.context.request.post(self.url + '/api/auth/request',
                                                   data={'email': email})
        self.assertEqual(response.status, 200)
        await self.page.goto(_latest_link(self.outbox, email))
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('window.DOGCARE_API'), '/api')
        self.assertEqual(await self.page.locator('html').get_attribute('lang'), 'fr')
        imported = await (await self.context.request.get(self.url + '/api/state')).json()
        self.assertTrue(imported['imported'])
        self.assertEqual(imported['observations']['billie'][0]['text'], note)
        self.assertEqual(imported['invites'][0]['name'], 'Demo Carer')
        self.assertEqual(imported['language'], 'fr')

        account_note = 'Account update: Billie rested calmly after lunch.'
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', account_note)
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="invite"]')
        await self.page.fill('#invite-name', 'Account Carer')
        await self.page.fill('#invite-email', 'account-carer@example.com')
        await self.page.click('#create-invite')
        await self.page.wait_for_function(
            'document.querySelector("#pending-invites").textContent.includes("Account Carer")')
        await self.page.select_option('#language-picker', 'en')
        await self.page.wait_for_function('document.documentElement.lang === "en"')
        saved = await (await self.context.request.get(self.url + '/api/state')).json()
        self.assertEqual(saved['observations']['billie'][0]['text'], account_note)
        self.assertEqual(saved['invites'][0]['name'], 'Account Carer')
        self.assertEqual(saved['language'], 'en')
        for key, value in local.items():
            self.assertEqual(await self.page.evaluate(
                'key => localStorage.getItem("dogcare-" + key)', key), value)

        repeated = await self.context.request.post(self.url + '/api/import', data={
            'observations': json.loads(local['observations']),
            'invites': json.loads(local['invites']), 'language': local['language'],
        }, headers={'X-DogCare-Business': str(saved['business_id']),
                    'If-Match': '"' + str(saved['revision']) + '"'})
        self.assertEqual(repeated.status, 200)
        repeated_state = await repeated.json()
        self.assertTrue(repeated_state.pop('skipped'))
        self.assertEqual(repeated_state, saved)

        fresh = await self.browser.new_context(viewport={'width': 1440, 'height': 1000})
        self.addAsyncCleanup(fresh.close)
        self.page = await fresh.new_page()
        self.page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        self.page.on('console', lambda message: self.console_errors.append(message.text)
                     if message.type == 'error' else None)
        response = await fresh.request.post(self.url + '/api/auth/request', data={'email': email})
        self.assertEqual(response.status, 200)
        await self.page.goto(_latest_link(self.outbox, email))
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('localStorage.length'), 0)
        self.assertEqual(await (await fresh.request.get(self.url + '/api/state')).json(), saved)
        await self.page.click('[data-page="dogs"]')
        self.assertEqual(await self.page.locator('.timeline-card p').first.text_content(), account_note)
        self.assertIn(note, await self.page.locator('#app-content').text_content())
        await self.capture_evidence('account-timeline-fresh-browser.png')
        await self.page.click('.more-toggle')
        await self.page.click('#more-nav [data-page="invite"]')
        self.assertIn('Account Carer', await self.page.locator('#pending-invites').text_content())
        self.assertIn('Demo Carer', await self.page.locator('#pending-invites').text_content())
        await self.capture_evidence('account-invites-fresh-browser.png')
        await self.page.set_viewport_size({'width': 390, 'height': 844})
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="handoff"]')
        self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), 390)
        await self.capture_evidence('account-handoff-mobile.png')
        evidence = self.page.locator('[data-evidence-id]').first
        observation_id = await evidence.get_attribute('data-evidence-id')
        await evidence.click()
        self.assertEqual(await self.page.locator(f'#observation-{observation_id}').count(), 1)
        self.assertEqual(self.console_errors, [])
        with self.server_mod.connection() as connection:
            business = dict(connection.execute(
                'SELECT name, imported, revision FROM business WHERE id=?',
                (saved['business_id'],)).fetchone())
        self.assertEqual(business['name'], 'migration-owner')
        directory = os.environ.get('DOGCARE_EVIDENCE_DIR')
        if directory:
            (Path(directory) / 'migration-persisted-state.json').write_text(json.dumps({
                'origin': self.url, 'local_before_import': local,
                'imported_state': imported, 'account_state_in_fresh_browser': saved,
                'repeat_import_skipped': True, 'business_in_sqlite': business,
                'fresh_browser_local_storage_keys': 0,
            }, indent=2) + '\n', encoding='utf-8')


class AccountRecoveryTest(BrowserFixture):
    async def test_sharing_recording_rejects_expired_and_switched_sessions(self):
        status, body, _ = _http(self.port, 'POST', '/api/blobs',
                               {'type': 'audio/webm', 'data': 'YQ=='}, cookie=self.sid)
        self.assertEqual(status, 200, body)
        src = '/api/blobs/' + body['ref']
        for status in (200, 401, 404):
            with self.subTest(status=status):
                if status == 401:
                    await self.context.clear_cookies()
                elif status == 404:
                    await self.fresh_account()
                async with self.page.expect_response(self.url + src) as response:
                    result = await self.page.evaluate('''async src => {
                        const shares = [];
                        let failures = 0;
                        Object.defineProperty(navigator, 'canShare', {configurable:true, value:() => true});
                        Object.defineProperty(navigator, 'share', {configurable:true, value:async data => {
                            shares.push(await Promise.all((data.files || []).map(async file =>
                                ({type:file.type, text:await file.text()}))));
                        }});
                        await shareObservation({...state.observations.billie[0], audio:{url:src}},
                            () => { failures++; });
                        return {shares, failures};
                    }''', src)
                self.assertEqual((await response.value).status, status)
                if status == 200:
                    self.assertEqual(result, {'shares': [[{'type': 'audio/webm', 'text': 'a'}]], 'failures': 0})
                else:
                    self.assertEqual(result, {'shares': [], 'failures': 1})
                    self.assertEqual(await self.page.locator('#toast').text_content(),
                                     'The share sheet could not open. Use one of the sharing options below.')
        self.assertTrue(all('401' in error or '404' in error for error in self.console_errors), self.console_errors)

    async def test_legacy_unsafe_recording_urls_never_render_fetch_or_block_saves(self):
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
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.fill('#observation', 'A new note after loading legacy recordings')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        expected = [{key: value for key, value in item.items() if key != 'audio'}
                    for item in observations['billie']]
        saved = await self.page.evaluate('state.observations.billie')
        self.assertEqual(saved[0]['text'], 'A new note after loading legacy recordings')
        self.assertEqual(saved[1:], [{**item, 'time': '', 'date': ''} for item in expected])
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
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
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
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.evaluate("audioDraft = {url:'data:audio/webm;base64,YQ==',duration:1}")
        await self.page.fill('#observation', 'Retry this note')
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await self.page.locator('#observation').count(), 1)
        self.assertEqual(await self.page.input_value('#observation'), 'Retry this note')
        self.assertTrue(await self.page.evaluate('Boolean(audioDraft)'))
        self.assertNotIn('Saved to', await self.page.locator('#toast').text_content())
        self.assertEqual(await self.page.evaluate('state.observations.billie.filter(item => item.text === "Retry this note").length'), 0)
        await self.capture_evidence('failed-save-draft-retained-mobile.png')
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
        await self.page.click('[data-dog="charlie"]')
        await self.page.click('#mobile-menu')
        await self.page.click('[data-page="dashboard"]')
        self.assertEqual(await self.page.locator('.activity-list [data-evidence-id]').count(), 0)
        await self.page.click('.activity-list [data-capture-dog="billie"]')
        self.assertEqual(await self.page.locator('.dog-pick.active').get_attribute('data-capture-dog'), 'billie')
        await self.page.fill('#observation', 'First real observation')
        await self.page.click('#save-observation')
        await self.page.evaluate('DogCareAPI.whenSaved()')
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        self.assertEqual(status, 200)
        self.assertEqual(len(state['observations']['billie']), 1)
        self.assertEqual(state['observations']['charlie'], [])
        self.assertEqual(self.console_errors, [])
