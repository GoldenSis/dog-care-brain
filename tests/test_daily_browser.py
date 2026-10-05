"""Operational booking, summary and document journeys in disposable browser accounts."""
import threading
from datetime import date, timedelta
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT


class DailyBrowserAcceptanceTest(BrowserFixture):
    async def asyncSetUp(self):
        self.sid = self.login(f"daily-{self._testMethodName}@example.com")
        await super().asyncSetUp()

    async def route(self, route):
        await self.page.click(f'#main-nav [data-page="{route}"]')
        await self.page.wait_for_function('!savePending')

    async def snapshot(self):
        return await self.page.evaluate("window.DogCareAPI ? DogCareAPI.getDaily() : JSON.parse(localStorage.getItem('dogcare-daily-v1'))")

    async def new_booking(self, service='night', start='2026-10-30', end='2026-11-02', new_dog=False):
        await self.route('schedule')
        await self.page.click('#new-booking')
        self.assertFalse(await self.page.locator('#new-booking').is_visible())
        if new_dog:
            await self.page.select_option('#booking-form [name="dogId"]', 'new')
            await self.page.fill('#booking-form [name="dogName"]', 'Fixture Pup')
        await self.page.fill('#booking-form [name="client"]', 'Fixture Client')
        await self.page.select_option('#booking-form [name="service"]', service)
        await self.page.fill('#booking-form [name="start"]', start)
        await self.page.fill('#booking-form [name="end"]', end)

    async def submit_booking(self):
        await self.page.click('#booking-form [type="submit"]')
        await self.page.wait_for_selector('#booking-form', state='detached')
        await self.page.wait_for_function('!savePending')

    async def rates(self, night):
        await self.route('business')
        await self.page.fill('#rates-form [name="night"]', night)
        await self.page.click('#rates-form button')
        await self.page.wait_for_function("document.querySelector('#rates-saved').textContent.length > 0 && !savePending")

    async def test_booking_reload_extension_and_monthly_actual_totals(self):
        await self.rates('25.00')
        await self.new_booking(new_dog=True)
        self.assertIn('75.00', await self.page.locator('#booking-quote').inner_text())
        await self.submit_booking()
        original = await self.snapshot()
        self.assertEqual(len(original['clients']), 1)
        self.assertEqual(len(original['dogs']), 1)
        self.assertEqual(original['bookings'][0]['unitMinor'], 2500)
        await self.page.reload()
        await self.wait_ready()
        await self.rates('40.00')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertIn('50.00', await self.page.locator('.daily-summary').inner_text())
        await self.page.fill('#daily-month', '2026-11')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertIn('25.00', await self.page.locator('.daily-summary').inner_text())
        await self.route('schedule')
        await self.page.click('[data-edit-booking]')
        await self.page.fill('#booking-form [name="end"]', '2026-11-05')
        quote = await self.page.locator('#booking-quote').inner_text()
        self.assertIn('75.00', quote)
        self.assertIn('150.00', quote)
        await self.submit_booking()
        updated = await self.snapshot()
        self.assertEqual(updated['bookings'][0]['unitMinor'], 2500)
        self.assertEqual(updated['bookings'][0]['end'], '2026-11-05')
        await self.page.click('#new-booking')
        await self.page.select_option('#booking-form [name="dogId"]', original['dogs'][0]['id'])
        self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), 'Fixture Client')
        self.assertTrue(await self.page.locator('#booking-form [name="client"]').evaluate('el=>el.readOnly'))
        await self.page.select_option('#booking-form [name="service"]', 'walk')
        await self.page.fill('#booking-form [name="start"]', '2026-11-06')
        await self.page.fill('#booking-form [name="end"]', '2026-11-06')
        self.assertIn('not specified', (await self.page.locator('#booking-quote').inner_text()).lower())
        await self.submit_booking()
        final = await self.snapshot()
        self.assertEqual(len(final['dogs']), 1)
        self.assertEqual(len(final['clients']), 1)
        self.assertIsNone(final['bookings'][1]['unitMinor'])
        await self.route('business')
        await self.page.fill('#daily-month', '2026-11')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertIn('100.00', await self.page.locator('.daily-total').inner_text())
        self.assertIn('without a price', (await self.page.locator('.daily-summary').inner_text()).lower())
        unknown_row = self.page.locator('.daily-summary article').filter(has_text='Walk')
        self.assertIn('not specified', (await unknown_row.inner_text()).lower())
        self.assertNotIn('0.00', await unknown_row.inner_text())
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')
        await self.capture_evidence(f'daily-summary-{self.api_mode}.png', full_page=False)
        await self.page.select_option('#language-picker', 'en')
        await self.page.wait_for_function('!savePending')
        await self.page.fill('#rates-form [name="walk"]', '45.00')
        await self.page.click('#rates-form button')
        await self.page.wait_for_function("document.querySelector('#rates-saved').textContent.length > 0 && !savePending")
        self.assertIsNone((await self.snapshot())['bookings'][1]['unitMinor'])
        await self.route('schedule')
        await self.page.click(f'[data-edit-booking="{final["bookings"][1]["id"]}"]')
        self.assertEqual(await self.page.input_value('#booking-form [name="unitMinor"]'), '')
        await self.page.fill('#booking-form [name="unitMinor"]', '12.50')
        self.assertIn('12.50', await self.page.locator('#booking-quote').inner_text())
        await self.submit_booking()
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual((await self.snapshot())['bookings'][1]['unitMinor'], 1250)
        self.assertEqual(self.console_errors, [])

    async def test_document_reload_download_and_explicit_renewal_followup(self):
        await self.route('dogs')
        pdf = b'%PDF-1.7\nSynthetic vaccination proof fixture\n%%EOF'
        await self.page.fill('#document-form [name="label"]', 'Fixture vaccination proof')
        await self.page.set_input_files('#document-form [name="file"]',
                                       {'name': 'fixture-proof.pdf', 'mimeType': 'application/pdf', 'buffer': pdf})
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual(saved['documents'][0]['renewal'], '')
        await self.page.reload()
        await self.wait_ready()
        await self.route('dogs')
        async with self.page.expect_download() as download_event:
            await self.page.click('[data-open-document]')
        download = await download_event.value
        self.assertEqual(Path(await download.path()).read_bytes(), pdf)
        self.assertEqual(download.suggested_filename, 'fixture-proof.pdf')
        await self.page.click('.daily-document summary')
        renewal = (date.today() + timedelta(days=7)).isoformat()
        await self.page.fill('[data-renewal] [name="renewal"]', renewal)
        await self.page.click('[data-renewal] button')
        await self.page.wait_for_function('!savePending')
        await self.route('dashboard')
        self.assertIn('Fixture vaccination proof', await self.page.locator('.daily-followups').inner_text())
        await self.page.click('[data-document-dog]')
        self.assertEqual(await self.page.evaluate('state.page'), 'dogs')
        self.assertEqual((await self.snapshot())['documents'][0]['renewal'], renewal)
        await self.capture_evidence(f'daily-documents-{self.api_mode}.png', full_page=False)
        self.assertEqual(self.console_errors, [])

    async def test_failed_booking_save_retains_form_and_retry_persists_once(self):
        await self.new_booking(service='day', start='2026-10-05', end='2026-10-05')
        if self.api_mode:
            await self.page.route('**/api/daily', lambda route: route.fulfill(
                status=503, content_type='application/json', body='{"ok":false}'))
        else:
            await self.page.evaluate('''() => {
                window.originalSetItem = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key, value) {
                    if (key === 'dogcare-daily-v1') throw new DOMException('Full', 'QuotaExceededError');
                    return window.originalSetItem.call(this, key, value);
                };
            }''')
        await self.page.click('#booking-form [type="submit"]')
        await self.page.wait_for_selector('#booking-form .daily-error:not([hidden])')
        self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), 'Fixture Client')
        self.assertEqual(await self.page.input_value('#booking-form [name="start"]'), '2026-10-05')
        before = await self.snapshot()
        self.assertFalse(before and before['bookings'])
        if self.api_mode:
            await self.page.unroute('**/api/daily')
            self.assertTrue(any('503' in error for error in self.console_errors))
            self.console_errors[:] = [error for error in self.console_errors if '503' not in error]
        else:
            await self.page.evaluate('() => { Storage.prototype.setItem = window.originalSetItem; }')
        await self.submit_booking()
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(len((await self.snapshot())['bookings']), 1)
        self.assertEqual(self.console_errors, [])

    async def test_daily_forms_locales_sizes_focus_and_touch_targets(self):
        for width, height in ((390, 844), (1024, 768), (1440, 900)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            for locale in ('fr', 'en', 'it', 'de', 'es'):
                await self.page.select_option('#language-picker', locale)
                await self.page.wait_for_function("l=>document.documentElement.lang===l&&!savePending", arg=locale)
                for route, form in (('schedule', '#booking-form'), ('business', '#rates-form'), ('dogs', '#document-form')):
                    await self.route(route)
                    if route == 'schedule':
                        await self.page.locator('#new-booking').focus()
                        await self.page.keyboard.press('Enter')
                        self.assertEqual(await self.page.evaluate('document.activeElement.tagName'), 'H2')
                    self.assertGreater(len(await self.page.locator('#page-title').inner_text()), 0)
                    self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
                    for control in await self.page.locator(f'{form} input:visible, {form} select:visible, {form} button:visible').all():
                        box = await control.bounding_box()
                        self.assertGreaterEqual(box['height'], 44)
                        self.assertGreaterEqual(box['width'], 44)
            await self.page.select_option('#language-picker', 'fr')
            await self.page.wait_for_function('!savePending')
            await self.route('schedule')
            await self.page.click('#new-booking')
            await self.capture_evidence(f'daily-planning-{width}-{self.api_mode}.png', full_page=False)
        self.assertEqual(self.console_errors, [])

    async def test_corrupt_daily_records_do_not_replace_data_or_break_notes(self):
        if self.api_mode:
            async def corrupted(route):
                response = await route.fetch()
                payload = await response.json()
                payload['daily'] = {'version': 99}
                await route.fulfill(response=response, json=payload)
            await self.page.route('**/api/state', corrupted)
        else:
            await self.page.evaluate("localStorage.setItem('dogcare-daily-v1','{bad json')")
        await self.page.reload()
        await self.wait_ready()
        self.assertTrue(await self.page.locator('.daily-error').is_visible())
        await self.route('schedule')
        self.assertTrue(await self.page.locator('#new-booking').is_disabled())
        await self.route('capture')
        self.assertTrue(await self.page.locator('#observation').is_visible())
        if not self.api_mode:
            self.assertEqual(await self.page.evaluate("localStorage.getItem('dogcare-daily-v1')"), '{bad json')
        self.assertEqual(self.console_errors, [])

    async def test_saved_dog_and_client_names_remain_text_across_existing_routes(self):
        await self.new_booking(service='walk', start='2026-10-05', end='2026-10-05', new_dog=True)
        name = '<img src=x onerror="window.injected=1">'
        await self.page.fill('#booking-form [name="dogName"]', name)
        await self.page.fill('#booking-form [name="client"]', name)
        await self.submit_booking()
        dog_id = (await self.snapshot())['dogs'][0]['id']
        await self.route('dashboard')
        await self.page.locator(f'.dog-card[data-dog="{dog_id}"]').click()
        self.assertIn(name, await self.page.locator('.profile-hero').inner_text())
        for route in ('capture', 'handoff', 'story', 'business'):
            await self.route(route)
            self.assertFalse(await self.page.evaluate('!!window.injected'))
            self.assertEqual(await self.page.locator('img[src="x"]').count(),0)
        self.assertEqual(self.console_errors, [])


class StaticDailyBrowserAcceptanceTest(DailyBrowserAcceptanceTest):
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
