"""Sourced education and real private drafts in disposable API/static browsers."""
import threading
from functools import partial
from http.server import ThreadingHTTPServer

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT


class KnowledgeBrowserTest(BrowserFixture):
    async def asyncSetUp(self):
        self.sid = self.login(f"knowledge-{self._testMethodName}@example.test")
        await super().asyncSetUp()

    async def open_health(self):
        await self.page.click('#main-nav [data-page="health"]')
        self.assertEqual(await self.page.get_attribute('[data-page="health"]', 'aria-current'), 'page')

    async def fill_experience(self, title='Quiet greeting'):
        await self.open_health()
        await self.page.click('#add-experience')
        await self.page.fill('#experience-form [name="title"]', title)
        await self.page.fill('#experience-form [name="body"]', 'We left space.\nAn observation in this context, not a care rule.')
        await self.page.fill('#experience-form [name="author"]', 'Fixture colleague')
        await self.page.fill('#experience-form [name="url"]', 'https://example.org/experience')
        await self.page.select_option('#experience-form [name="category"]', 'traditional')

    async def submit(self):
        await self.page.click('#experience-form [type="submit"]')
        await self.page.wait_for_function('!savePending')

    async def test_search_guides_videos_locales_and_responsive_navigation(self):
        await self.page.select_option('#language-picker', 'fr')
        for width, height in ((1440, 900), (1024, 768), (390, 844)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.open_health()
            self.assertEqual(await self.page.locator('[data-guide]').count(), 6)
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            self.assertGreaterEqual((await self.page.locator('#add-experience').bounding_box())['height'], 44)
            await self.capture_evidence(f'health-guides-{width}-{self.api_mode}.png', full_page=False)
        await self.page.fill('#knowledge-search', 'dents')
        self.assertEqual(await self.page.locator('[data-guide]').count(), 1)
        await self.page.click('[data-guide="dents"]')
        self.assertEqual(await self.page.locator('[data-video-link]').count(), 2)
        self.assertGreaterEqual(await self.page.locator('.knowledge-sources a').count(), 2)
        await self.capture_evidence(f'health-guide-detail-390-{self.api_mode}.png')
        for code, title in [('en', 'A little dental care every day'), ('it', 'Un po’ di cura dei denti ogni giorno'),
                            ('de', 'Jeden Tag etwas Zahnpflege'), ('es', 'Un poco de cuidado dental cada día'),
                            ('fr', 'Les dents, un peu chaque jour')]:
            await self.page.select_option('#language-picker', code)
            await self.page.wait_for_function('!savePending')
            self.assertEqual(await self.page.locator('.knowledge-detail h2').inner_text(), title)
        await self.context.route('https://www.youtube.com/**', lambda route: route.fulfill(body='Provider link fixture'))
        async with self.page.expect_popup() as popup_info:
            await self.page.locator('[data-video-link]').first.click()
        popup = await popup_info.value
        await popup.wait_for_load_state()
        self.assertEqual(popup.url, 'https://www.youtube.com/watch?v=ETeFcUjmwF8')
        await popup.close()
        await self.page.click('#knowledge-back')
        await self.page.fill('#knowledge-search', '')
        await self.page.click('.knowledge-guide-picker summary')
        await self.page.click('[data-topic="visit"]')
        self.assertEqual(await self.page.locator('[data-guide]').count(), 1)
        self.assertEqual(await self.page.locator('[data-guide]').get_attribute('data-guide'), 'visite-veto')
        await self.page.click('[data-knowledge-filter="traditional"]')
        self.assertEqual(await self.page.locator('[data-private-experience]').count(), 0)
        self.assertEqual(self.console_errors, [])

    async def test_private_experience_save_edit_reload_and_safe_text(self):
        before = await self.page.evaluate('JSON.stringify(state.observations)')
        await self.fill_experience()
        await self.page.set_viewport_size({'width': 390, 'height': 844})
        await self.page.select_option('#language-picker', 'fr')
        self.assertEqual(await self.page.input_value('[name="title"]'), 'Quiet greeting')
        await self.capture_evidence(f'health-private-form-390-{self.api_mode}.png')
        await self.submit()
        await self.page.wait_for_selector('#experience-form', state='detached')
        await self.page.reload()
        await self.wait_ready()
        await self.open_health()
        await self.page.click('[data-knowledge-filter="traditional"]')
        self.assertEqual(await self.page.locator('[data-private-experience]').count(), 1)
        self.assertIn('non relue', await self.page.locator('[data-private-experience]').inner_text())
        await self.page.click('[data-edit-experience]')
        await self.page.fill('[name="body"]', '<img src=x onerror=alert(1)>\nUpdated observation')
        await self.submit()
        await self.page.wait_for_selector('#experience-form', state='detached')
        await self.page.reload()
        await self.wait_ready()
        await self.open_health()
        await self.page.click('[data-private-open]')
        self.assertIn('<img src=x', await self.page.locator('.knowledge-experience-body').inner_text())
        self.assertEqual(await self.page.locator('.knowledge-experience-body img').count(), 0)
        self.assertEqual(await self.page.evaluate('JSON.stringify(state.observations)'), before)
        await self.capture_evidence(f'health-private-detail-390-{self.api_mode}.png')
        self.assertEqual(self.console_errors, [])

    async def test_failed_save_preserves_draft_and_never_claims_saved(self):
        await self.fill_experience()
        if self.api_mode:
            await self.page.route('**/api/knowledge', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
        else:
            await self.page.evaluate('''() => {
                const set = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key,value) {
                    if(key==='dogcare-knowledge-v1')throw new DOMException('Full','QuotaExceededError');
                    return set.call(this,key,value);
                };
            }''')
        await self.submit()
        self.assertTrue(await self.page.locator('#experience-form [role="alert"]').is_visible())
        self.assertEqual(await self.page.input_value('[name="title"]'), 'Quiet greeting')
        self.assertEqual(await self.page.locator('.knowledge-saved').count(), 0)
        await self.page.click('[data-page="dashboard"]')
        await self.open_health()
        self.assertEqual(await self.page.input_value('[name="title"]'), 'Quiet greeting')
        await self.page.reload()
        await self.wait_ready()
        await self.open_health()
        self.assertEqual(await self.page.locator('[data-private-experience]').count(), 0)

    async def test_second_tab_cannot_replace_saved_experience(self):
        other = await self.context.new_page()
        self.addAsyncCleanup(other.close)
        await other.goto(self.url)
        await other.wait_for_selector('#app-content[data-ready="true"]')
        await other.click('[data-page="health"]')
        await other.click('#add-experience')
        await other.fill('[name="title"]', 'Stale second draft')
        await other.fill('[name="body"]', 'This draft must remain available after conflict.')
        await self.fill_experience('Saved first draft')
        await self.submit()
        await self.page.wait_for_selector('#experience-form', state='detached')
        await other.click('#experience-form [type="submit"]')
        await other.wait_for_function('!savePending')
        self.assertTrue(await other.locator('#experience-form [role="alert"]').is_visible())
        self.assertEqual(await other.input_value('[name="title"]'), 'Stale second draft')
        await self.page.reload()
        await self.wait_ready()
        await self.open_health()
        self.assertEqual(await self.page.locator('[data-private-experience]').count(), 1)
        self.assertIn('Saved first draft', await self.page.locator('[data-private-experience]').inner_text())


class StaticKnowledgeBrowserTest(KnowledgeBrowserTest):
    api_mode = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietStaticHandler, directory=str(ROOT)))
        cls.static_thread = threading.Thread(target=cls.static_httpd.serve_forever, daemon=True)
        cls.static_thread.start()
        cls.url = f'http://127.0.0.1:{cls.static_httpd.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.static_httpd.shutdown()
        cls.static_httpd.server_close()
        cls.static_thread.join(timeout=2)
        super().tearDownClass()
