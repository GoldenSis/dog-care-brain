import uuid

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import _http


class BillingBrowserTest(BrowserFixture):
    async def asyncSetUp(self):
        self.sid = self.login('billing-' + uuid.uuid4().hex + '@example.test')
        await super().asyncSetUp()

    def seed(self, bookings=None):
        daily = {'version': 1, 'clients': [{'id': 'first', 'name': 'Original family'}, {'id': 'second', 'name': 'Current family'}],
                 'dogs': [{'id': 'synthetic-dog', 'name': 'Synthetic dog', 'clientId': 'first'}],
                 'bookings': bookings or [], 'rates': {'currency': 'CHF', 'day': 2500, 'night': None, 'walk': None}, 'documents': []}
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': daily}, cookie=self.sid)
        self.assertEqual(status, 200, state)
        return state['daily']

    async def test_reassigned_dog_keeps_historical_invoice_and_monthly_family(self):
        daily = self.seed([{'id': 'historical', 'dogId': 'synthetic-dog', 'service': 'day', 'start': '2026-10-06',
                            'end': '2026-10-07', 'unitMinor': 1234, 'currency': 'CHF'}])
        daily['dogs'][0]['clientId'] = 'second'
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': daily}, cookie=self.sid)
        self.assertEqual(status, 200, state)
        await self.page.reload()
        await self.wait_ready()
        await self.open_route('schedule')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertIn('Original family', await self.page.locator('[data-booking-id="historical"]').inner_text())
        await self.open_route('business')
        await self.page.click('[data-finance-tab="rates"]')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        summary = await self.page.locator('.daily-summary').inner_text()
        self.assertIn('Original family', summary)
        self.assertNotIn('Current family', summary)
        await self.page.click('#finance-new-sale')
        await self.page.click('#finance-booking')
        await self.page.locator('#finance-booking + select').select_option('historical')
        self.assertEqual(await self.page.input_value('[name="party"]'), 'Original family')
        self.assertEqual(await self.page.input_value('[name="unit-0"]'), '12.34')
        self.assertEqual(await self.page.input_value('[name="quantity-0"]'), '2')
        for width in (390, 1440):
            await self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            await self.capture_evidence(f'billing-historical-family-{width}.png')
        await self.page.click('#finance-form button[value="draft"]')
        await self.page.wait_for_function('!savePending && FinanceStore.snapshot().entries.length === 1')
        await self.page.reload()
        await self.wait_ready()
        entry = await self.page.evaluate('FinanceStore.snapshot().entries[0]')
        self.assertEqual(entry['party'], 'Original family')
        self.assertEqual(entry['lines'][0]['unitMinor'], 1234)
        self.assertEqual(self.console_errors, [])

    async def test_carer_creates_priced_and_unknown_bookings_with_readonly_rates(self):
        self.seed()
        email = 'carer-' + uuid.uuid4().hex + '@example.com'
        status, state, _ = _http(self.port, 'POST', '/api/portal/members',
                                 {'email': email, 'role': 'trusted-carer', 'clientId': None}, cookie=self.sid)
        self.assertEqual(status, 200, state)
        sid = self.login(email)
        _http(self.port, 'PUT', '/api/prefs', {'language': 'en'}, cookie=sid)
        await self.context.add_cookies([{'name': 'dc_s', 'value': sid, 'url': self.url, 'httpOnly': True}])
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('DogCareAPI.getUser().role'), 'trusted-carer')
        for service, value, expected in [('day', '25.00', 2500), ('walk', '', None)]:
            await self.open_route('schedule')
            self.assertEqual(await self.page.locator('[data-finance-rates]').count(), 0)
            await self.page.click('#new-booking')
            await self.page.select_option('#booking-form [name="dogId"]', 'synthetic-dog')
            await self.page.select_option('#booking-form [name="service"]', service)
            amount = self.page.locator('#booking-form [name="unitMinor"]')
            self.assertEqual(await amount.input_value(), value)
            self.assertTrue(await amount.evaluate('el => el.readOnly'))
            await self.page.fill('#booking-form [name="start"]', '2026-10-08')
            await self.page.fill('#booking-form [name="end"]', '2026-10-08')
            for width in (390, 1440):
                await self.page.set_viewport_size({'width': width, 'height': 900})
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                await self.capture_evidence(f'carer-booking-{service}-{width}.png')
            async with self.page.expect_request(lambda request: request.method == 'PUT' and request.url.endswith('/api/daily')) as pending:
                await self.page.click('#booking-form [type="submit"]')
            request = await pending.value
            sent = next(b for b in request.post_data_json['daily']['bookings'] if b['service'] == service)
            self.assertIsNone(sent['unitMinor'])
            await self.page.wait_for_selector('#booking-form', state='detached')
            await self.page.reload()
            await self.wait_ready()
            saved = await self.page.evaluate('(service) => DogCareAPI.getDaily().bookings.find(b=>b.service===service)', service)
            self.assertEqual(saved['unitMinor'], expected)
            self.assertEqual(saved['dogId'], 'synthetic-dog')
            await self.open_route('schedule')
            await self.page.fill('#daily-month', '2026-10')
            await self.page.locator('#daily-month').dispatch_event('change')
            await self.page.click(f'[data-edit-booking="{saved["id"]}"]')
            self.assertTrue(await self.page.locator('#booking-form [name="service"]').is_disabled())
            self.assertTrue(await self.page.locator('#booking-form [name="dogId"]').is_disabled())
            await self.page.fill('#booking-form [name="end"]', '2026-10-09')
            await self.page.click('#booking-form [type="submit"]')
            await self.page.wait_for_selector('#booking-form', state='detached')
            extended = await self.page.evaluate('(id)=>DogCareAPI.getDaily().bookings.find(b=>b.id===id)', saved['id'])
            self.assertEqual(extended, {**saved, 'end': '2026-10-09'})
        self.assertEqual(self.console_errors, [])
