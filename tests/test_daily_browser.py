"""Operational booking, summary and document journeys in disposable browser accounts."""
import base64
import threading
from datetime import date, timedelta
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT
from tests.test_tenant_isolation import _http


class DailyBrowserAcceptanceTest(BrowserFixture):
    async def test_document_registration_selects_owner_by_id_without_splitting_bookings(self):
        seeded = await self.page.evaluate('DailyModel.empty()')
        owner = await self.page.evaluate('dogs.billie.owner')
        seeded['clients'] = [{'id': key, 'name': '  ' + owner + '  '} for key in ('first', 'second')]
        await self.seed_daily(seeded)
        for dog_id in ('billie', 'charlie'):
            await self.page.evaluate('(id) => { state.dog=id; }', dog_id)
            await self.prepare_document(choose_owner=False)
            choice = self.page.locator('#document-form [name="clientId"]')
            self.assertEqual(await choice.count(), 1)
            self.assertEqual(await choice.input_value(), '')
            self.assertFalse(await self.page.locator('#document-form').evaluate('el => el.checkValidity()'))
            await choice.select_option('second')
            await self.page.click('#document-form button')
            await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual(saved['clients'], seeded['clients'])
        self.assertEqual([(d['id'], d['clientId']) for d in saved['dogs']], [('billie', 'second'), ('charlie', 'second')])
        for dog_id in ('billie', 'charlie'):
            await self.route('schedule')
            await self.page.click('#new-booking')
            await self.page.select_option('#booking-form [name="dogId"]', dog_id)
            self.assertTrue(await self.page.locator('#booking-form [name="clientId"]').is_disabled())
            await self.page.fill('#booking-form [name="start"]', '2026-10-05')
            await self.page.fill('#booking-form [name="end"]', '2026-10-05')
            await self.submit_booking()
        rows = await self.page.evaluate("DailyModel.monthlySummary(DailyUI.snapshot(), '2026-10')")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['clientId'], 'second')
        self.assertEqual(rows[0]['bookingCount'], 2)
        saved = await self.snapshot()
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_document_owner_choice_and_literal_fields_survive_failed_save(self):
        await self.prepare_document(choose_owner=False)
        choice = self.page.locator('#document-form [name="clientId"]')
        self.assertEqual(await choice.count(), 1)
        self.assertEqual(await self.page.input_value('#document-form [name="client"]'), await self.page.evaluate('dogs.billie.owner'))
        for locale in ('fr', 'it', 'de', 'es', 'en'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            for width, height in ((390, 844), (1024, 768), (1440, 900)):
                await self.page.set_viewport_size({'width': width, 'height': height})
                await choice.focus()
                self.assertTrue(await choice.evaluate('el => el === document.activeElement'))
                self.assertGreaterEqual((await choice.bounding_box())['height'], 44)
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.prepare_document()
        label, owner = '  Literal proof  ', '  Explicit new owner  '
        await choice.select_option(':new')
        await self.page.fill('#document-form [name="client"]', owner)
        await self.page.fill('#document-form [name="label"]', label)
        await self.page.evaluate('''() => {
            window.originalRead=File.prototype.arrayBuffer;
            File.prototype.arrayBuffer=()=>Promise.reject(Error('Unreadable fixture'));
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('#document-form .daily-error:not([hidden])')
        self.assertEqual(await self.page.input_value('#document-form [name="client"]'), owner)
        self.assertEqual(await self.page.input_value('#document-form [name="label"]'), label)
        self.assertEqual(await self.page.locator('#document-form [name="file"]').evaluate('el => el.files[0].name'), 'proof.pdf')
        await self.page.evaluate('() => { File.prototype.arrayBuffer=window.originalRead; }')
        await self.page.evaluate('''() => {
            if(window.DogCareAPI){window.originalSave=DogCareAPI.saveDocument;DogCareAPI.saveDocument=async()=>false;}
            else{window.originalSave=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='dogcare-daily-v1')throw Error('Storage unavailable');return originalSave.call(this,key,value);};}
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#document-form .daily-error').is_visible())
        self.assertEqual(await choice.input_value(), ':new')
        self.assertEqual(await self.page.input_value('#document-form [name="client"]'), owner)
        self.assertEqual(await self.page.input_value('#document-form [name="label"]'), label)
        self.assertEqual(await self.page.locator('#document-form [name="file"]').evaluate('el => el.files[0].name'), 'proof.pdf')
        await self.page.evaluate('''() => {
            if(window.DogCareAPI)DogCareAPI.saveDocument=window.originalSave;
            else Storage.prototype.setItem=window.originalSave;
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual(len(saved['clients']), 1)
        self.assertEqual(saved['clients'][0]['name'], owner)
        self.assertEqual(saved['documents'][0]['label'], label)
        self.assertEqual(await choice.count(), 0)
        self.assertEqual(self.console_errors, [])

    async def test_document_upload_preserves_explicitly_unknown_registered_owner(self):
        seeded = await self.page.evaluate('DailyModel.empty()')
        seeded['dogs'] = [{'id': 'billie', 'name': '  Known dog  ', 'clientId': None}]
        await self.seed_daily(seeded)
        await self.prepare_document()
        self.assertEqual(await self.page.locator('#document-form [name="clientId"]').count(), 0)
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual(saved['dogs'], seeded['dogs'])
        self.assertEqual(saved['clients'], [])
        self.assertEqual(self.console_errors, [])

    async def test_booking_selects_existing_owner_by_id_and_keeps_literal_names(self):
        seeded = await self.page.evaluate('DailyModel.empty()')
        seeded['clients'] = [{'id': 'first', 'name': 'Shared owner'},
                             {'id': 'second', 'name': 'Shared owner'},
                             {'id': 'padded', 'name': '  Padded owner  '}]
        seeded['dogs'] = [{'id': 'ownerless', 'name': '  Registered dog  ', 'clientId': None}]
        await self.seed_daily(seeded)
        for dog_id, client_id in [('ownerless', 'second'), (':new', 'padded')]:
            await self.new_booking(service='day', start='2026-10-05', end='2026-10-05')
            await self.page.select_option('#booking-form [name="dogId"]', dog_id)
            if await self.page.locator('#booking-form select[name="clientId"]').count():
                await self.page.select_option('#booking-form [name="clientId"]', client_id)
            else:
                await self.page.fill('#booking-form [name="client"]', next(c['name'] for c in seeded['clients'] if c['id'] == client_id))
            if dog_id == ':new':
                await self.page.fill('#booking-form [name="dogName"]', '  New dog  ')
            await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['clients'], seeded['clients'])
        self.assertEqual([(d['name'], d['clientId']) for d in saved['dogs']],
                         [('  Registered dog  ', 'second'), ('  New dog  ', 'padded')])
        rows = await self.page.evaluate("DailyModel.monthlySummary(DailyUI.snapshot(), '2026-10')")
        self.assertEqual({r['clientId'] for r in rows}, {'second', 'padded'})
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.new_booking(new_dog=True)
        await self.page.select_option('#booking-form [name="clientId"]', ':new')
        await self.page.fill('#booking-form [name="client"]', '  Shared owner  ')
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['clients'][-1]['name'], '  Shared owner  ')
        self.assertEqual(len(saved['clients']), 4)
        self.assertEqual(self.console_errors, [])

    async def test_add_dog_visible_from_current_profile(self):
        await self.page.select_option('#language-picker', 'fr')
        await self.route('dogs')
        await self.capture_evidence(f'add-dog-profile-before-{self.api_mode}.png', full_page=False)
        button = self.page.get_by_role('button', name='＋ Ajouter un chien', exact=True)
        self.assertEqual(await button.count(), 1, 'Chiens must offer registration directly on the current profile')
        self.assertTrue(await button.is_visible())
        await button.click()
        self.assertTrue(await self.page.locator('#dog-form').is_visible())

    async def test_add_dog_save_reload_duplicate_names_and_booking_without_placeholder_owner(self):
        before = await self.seed_same_named_clients()
        finance = await self.page.evaluate('FinanceStore.snapshot()')
        await self.route('dogs')
        await self.page.click('#new-dog')
        name = ' Today <Luna> 🐕 '
        await self.page.fill('#dog-form [name="dogName"]', name)
        await self.page.evaluate("() => { const f=document.querySelector('#dog-form'); f.requestSubmit(); f.requestSubmit(); }")
        await self.page.wait_for_selector('#dog-form', state='detached')
        saved = await self.snapshot()
        self.assertEqual(saved['clients'], before['clients'])
        self.assertEqual(saved['bookings'], before['bookings'])
        self.assertEqual(len(saved['dogs']), len(before['dogs']) + 1)
        first = saved['dogs'][-1]
        self.assertEqual(first['name'], name)
        self.assertIsNone(first['clientId'])
        self.assertEqual(await self.page.evaluate('state.dog'), first['id'])
        self.assertEqual(await self.page.text_content('.profile-hero h2'), name)
        await self.page.click('#new-dog')
        await self.page.fill('#dog-form [name="dogName"]', name)
        await self.page.select_option('#dog-form [name="clientId"]', 'client-second')
        await self.page.click('#dog-form [type="submit"]')
        await self.page.wait_for_selector('#dog-form', state='detached')
        saved = await self.snapshot()
        second = saved['dogs'][-1]
        self.assertNotEqual(second['id'], first['id'])
        self.assertEqual(second['clientId'], 'client-second')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(await self.page.evaluate('FinanceStore.snapshot()'), finance)
        await self.route('dogs')
        await self.page.click('#dog-list-toggle')
        self.assertEqual(await self.page.locator('[data-select-profile]').count(), 6)
        await self.page.click(f'[data-select-profile="{first["id"]}"]')
        self.assertEqual(await self.page.text_content('.profile-hero h2'), name)
        await self.route('capture')
        self.assertEqual(await self.page.text_content(f'[data-capture-dog="{first["id"]}"] strong'), name)
        await self.new_booking(service='walk', start='2026-10-05', end='2026-10-05')
        await self.page.select_option('#booking-form [name="dogId"]', first['id'])
        self.assertFalse(await self.page.locator('#booking-form [name="client"]').evaluate('(el) => el.readOnly'))
        await self.page.fill('#booking-form [name="client"]', 'Recorded owner')
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(len(saved['dogs']), 4)
        self.assertIsNotNone(next(d for d in saved['dogs'] if d['id'] == first['id'])['clientId'])
        self.assertEqual(self.console_errors, [])

    async def test_add_dog_cancel_failure_retry_and_literal_draft_across_locales(self):
        await self.route('dogs')
        before = await self.snapshot()
        await self.page.click('#new-dog')
        await self.page.fill('#dog-form [name="dogName"]', 'Unsaved dog')
        await self.page.click('#cancel-dog')
        self.assertEqual(await self.snapshot(), before)
        self.assertEqual(await self.page.evaluate('document.activeElement.id'), 'new-dog')
        await self.page.click('#new-dog')
        await self.page.fill('#dog-form [name="dogName"]', 'Today')
        await self.page.select_option('#dog-form [name="clientId"]', ':new')
        await self.page.fill('#dog-form [name="clientName"]', ' Yesterday ')
        for locale in ('fr', 'de', 'it', 'es', 'en'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            self.assertEqual(await self.page.input_value('#dog-form [name="dogName"]'), 'Today')
            self.assertEqual(await self.page.input_value('#dog-form [name="clientName"]'), ' Yesterday ')
        if self.api_mode:
            await self.page.route('**/api/daily', lambda route: route.fulfill(status=503, content_type='application/json', body='{"ok":false}'))
        else:
            await self.page.evaluate("""() => { window.savedSetItem=Storage.prototype.setItem;
              Storage.prototype.setItem=function(k,v){if(k==='dogcare-daily-v1')throw new DOMException('Full','QuotaExceededError');return window.savedSetItem.call(this,k,v);}; }""")
        await self.page.click('#dog-form [type="submit"]')
        await self.page.wait_for_selector('#dog-form .daily-error:not([hidden])')
        self.assertEqual(await self.snapshot(), before)
        await self.route('dashboard')
        await self.route('dogs')
        self.assertEqual(await self.page.input_value('#dog-form [name="dogName"]'), 'Today')
        self.assertTrue(await self.page.locator('#dog-form .daily-error').is_visible())
        if self.api_mode:
            await self.page.unroute('**/api/daily')
            self.console_errors[:] = [e for e in self.console_errors if '503' not in e]
        else:
            await self.page.evaluate('() => { Storage.prototype.setItem=window.savedSetItem; }')
        await self.page.click('#dog-form [type="submit"]')
        await self.page.wait_for_selector('#dog-form', state='detached')
        saved=await self.snapshot()
        self.assertEqual(saved['dogs'][-1]['name'], 'Today')
        self.assertEqual(saved['clients'][-1]['name'], ' Yesterday ')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_add_dog_empty_directory_keyboard_and_responsive_locales(self):
        await self.page.evaluate("() => { for(const id of Object.keys(dogs))delete dogs[id]; state.dog=''; }")
        await self.route('dogs')
        self.assertTrue(await self.page.locator('#new-dog').is_visible())
        self.assertEqual(await self.page.locator('[data-select-profile]').count(), 0)
        await self.page.locator('#new-dog').focus()
        await self.page.keyboard.press('Enter')
        self.assertEqual(await self.page.evaluate('document.activeElement.name'), 'dogName')
        for locale in ('fr', 'en', 'de', 'it', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            for width, height in ((390, 844), (1024, 768), (1440, 900)):
                await self.page.set_viewport_size({'width': width, 'height': height})
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                for selector in ('#new-dog', '#dog-list-toggle', '#dog-form [type="submit"]', '#cancel-dog'):
                    box=await self.page.locator(selector).bounding_box()
                    self.assertGreaterEqual(box['height'],44)
                if locale=='fr':await self.capture_evidence(f'add-dog-empty-form-fr-{width}-{self.api_mode}.png')
        await self.page.fill('#dog-form [name="dogName"]', 'First registered dog')
        await self.page.click('#dog-form [type="submit"]')
        await self.page.wait_for_selector('#dog-form', state='detached')
        self.assertEqual(await self.page.inner_text('.profile-hero h2'), 'First registered dog')
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')
        await self.capture_evidence(f'add-dog-saved-profile-{self.api_mode}.png', full_page=False)
        self.assertEqual(self.console_errors, [])

    async def test_contributor_document_labels_and_dog_names_stay_literal(self):
        await self.new_booking(new_dog=True)
        await self.page.fill('#booking-form [name="dogName"]', 'Today')
        await self.submit_booking()
        daily = await self.snapshot()
        dog = next(d for d in daily['dogs'] if d['name'] == 'Today')
        await self.route('dashboard')
        await self.page.click(f'[data-dog="{dog["id"]}"]')
        await self.page.fill('#document-form [name="label"]', 'Today')
        await self.page.set_input_files('#document-form [name="file"]', {
            'name': 'today.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.7\nfixture'})
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-document-id]')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            self.assertEqual(await self.page.inner_text('#page-title'), 'Today')
            self.assertEqual(await self.page.inner_text(f'[data-dog="{dog["id"]}"] strong'), 'Today')
            self.assertEqual(await self.page.inner_text('.profile-hero h2'), 'Today')
            self.assertEqual(await self.page.inner_text('[data-document-id] > strong'), 'Today')
            await self.route('dashboard')
            self.assertEqual(await self.page.inner_text(f'[data-dog="{dog["id"]}"] .dog-name'), 'Today')
            await self.route('capture')
            self.assertEqual(await self.page.inner_text(f'[data-capture-dog="{dog["id"]}"] strong'), 'Today')
            await self.route('schedule')
            await self.page.click('#new-booking')
            self.assertEqual(await self.page.inner_text(f'#booking-form [name="dogId"] option[value="{dog["id"]}"]'), 'Today')
            await self.page.click('#cancel-booking')
            await self.route('dashboard')
            await self.page.click(f'[data-dog="{dog["id"]}"]')
        await self.page.reload()
        await self.wait_ready()
        await self.route('dashboard')
        await self.page.click(f'[data-dog="{dog["id"]}"]')
        self.assertEqual(await self.page.inner_text('[data-document-id] > strong'), 'Today')
        self.assertEqual(self.console_errors, [])

    async def asyncSetUp(self):
        self.sid = self.login(f"daily-{self._testMethodName}@example.com")
        await super().asyncSetUp()

    async def route(self, route):
        await self.open_route(f'{route}')
        await self.page.wait_for_function('!savePending')
        if route == 'business':
            await self.page.click('[data-finance-tab="rates"]')

    async def snapshot(self):
        return await self.page.evaluate("window.DogCareAPI ? DogCareAPI.getDaily() : JSON.parse(localStorage.getItem('dogcare-daily-v1'))")

    async def new_booking(self, service='night', start='2026-10-30', end='2026-11-02', new_dog=False):
        await self.route('schedule')
        await self.page.click('#new-booking')
        self.assertFalse(await self.page.locator('#new-booking').is_visible())
        if new_dog:
            await self.page.select_option('#booking-form [name="dogId"]', label='Add a dog')
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

    async def prepare_document(self, choose_owner=True):
        await self.route('dogs')
        if choose_owner and await self.page.locator('#document-form [name="clientId"]').count():
            await self.page.select_option('#document-form [name="clientId"]', ':new')
        await self.page.fill('#document-form [name="label"]', 'Original proof')
        await self.page.fill('#document-form [name="renewal"]', '2027-10-05')
        await self.page.set_input_files('#document-form [name="file"]', {
            'name': 'proof.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.7\nfixture'})

    async def seed_daily(self, daily):
        self.assertTrue(await self.page.evaluate('''async daily => {
            DailyModel.validateDaily(daily);
            if (window.DogCareAPI) return DogCareAPI.saveDaily(daily);
            localStorage.setItem('dogcare-daily-v1', JSON.stringify(daily));
            return true;
        }''', daily))
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), daily)

    async def seed_same_named_clients(self):
        daily = await self.page.evaluate('DailyModel.empty()')
        daily['clients'] = [{'id': 'client-first', 'name': 'Fixture Client'},
                            {'id': 'client-second', 'name': 'Fixture Client'}]
        daily['dogs'] = [{'id': 'dog-first', 'name': 'First Pup', 'clientId': 'client-first'},
                         {'id': 'dog-second', 'name': 'Second Pup', 'clientId': 'client-second'}]
        daily['bookings'] = [{'id': 'first-booking', 'dogId': 'dog-first', 'service': 'day',
                              'start': '2026-10-30', 'end': '2026-10-30',
                              'unitMinor': 1800, 'currency': 'CHF'}]
        await self.seed_daily(daily)
        return daily

    async def test_saved_locales_keep_daily_and_knowledge_views_readable(self):
        daily = await self.page.evaluate('DailyModel.empty()')
        daily['clients'] = [{'id': 'locale-client', 'name': 'Fixture Client'}]
        daily['dogs'] = [{'id': 'billie', 'name': 'Fixture Pup', 'clientId': 'locale-client'}]
        daily['rates']['day'] = 1250
        daily['bookings'] = [{'id': 'locale-booking', 'dogId': 'billie', 'service': 'day',
                              'start': '2026-10-05', 'end': '2026-10-06',
                              'unitMinor': 1250, 'currency': 'CHF'}]
        await self.seed_daily(daily)
        await self.prepare_document()
        await self.page.fill('#document-form [name="renewal"]', '2026-01-01')
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-document-id]')
        await self.page.wait_for_function('!savePending')
        saved = await self.snapshot()
        writes = []
        self.page.on('request', lambda request: writes.append(request.url)
                     if request.method in ('POST', 'PUT', 'DELETE', 'PATCH') else None)
        for preference, locale in (('en_US', 'en'), ('zz', 'en'), ('fr', 'fr'), ('en', 'en'),
                                   ('it', 'it'), ('de', 'de'), ('es', 'es'), ('de-CH', 'de-CH')):
            with self.subTest(preference=preference):
                self.assertTrue(await self.page.evaluate('''async language => {
                    if (window.DogCareAPI) return DogCareAPI.saveLanguage(language);
                    localStorage.setItem('dogcare-language', language);
                    return true;
                }''', preference))
                writes.clear()
                await self.page.reload()
                await self.wait_ready()
                expected = await self.page.evaluate('''locale => {
                    const date = value => new Intl.DateTimeFormat(locale,
                        {dateStyle:'medium',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));
                    const money = value => new Intl.NumberFormat(locale, {style:'currency',
                        currency:'CHF',currencyDisplay:'code',minimumFractionDigits:2,
                        maximumFractionDigits:2}).format(value);
                    const language = code => new Intl.DisplayNames([locale],{type:'language'}).of(code);
                    const guide = KnowledgeContent.guides.find(g=>g.id==='dents');
                    return {due:date('2026-01-01'),start:date('2026-10-05'),end:date('2026-10-06'),
                        unit:money(12.5),total:money(25),extension:money(37.5),
                        checked:date(KnowledgeContent.checked),
                        sources:guide.sources.map(id=>language(KnowledgeContent.sources.find(s=>s.id===id).language)),
                        videos:KnowledgeContent.videos.map(v=>`${v.provider} · ${language(v.language)} · ${v.duration}`)};
                }''', locale)
                due = self.page.locator('[data-document-dog="billie"]')
                self.assertIn(expected['due'], await due.inner_text())
                await due.click()
                self.assertIn(expected['due'], await self.page.locator('.daily-document').inner_text())
                await self.route('schedule')
                await self.page.fill('#daily-month', '2026-10')
                await self.page.locator('#daily-month').dispatch_event('change')
                card = self.page.locator('[data-booking-id="locale-booking"]')
                for value in ('start', 'end', 'total'):
                    self.assertIn(expected[value], await card.text_content())
                await card.locator('[data-edit-booking]').click()
                for value in ('unit', 'total'):
                    self.assertIn(expected[value], await self.page.locator('#booking-quote').text_content())
                await self.page.fill('#booking-form [name="end"]', '2026-10-07')
                self.assertIn(expected['extension'], await self.page.locator('#booking-quote').text_content())
                await self.route('business')
                self.assertIn(expected['total'], await self.page.locator('.daily-summary').text_content())
                self.assertIn(expected['total'], await self.page.locator('.daily-total').text_content())
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                await self.route('health')
                await self.page.click('[data-guide="dents"]')
                self.assertIn(expected['checked'], await self.page.locator('.knowledge-detail > .daily-help').text_content())
                self.assertEqual(await self.page.locator('.knowledge-sources small').all_text_contents(), expected['sources'])
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                await self.page.click('#knowledge-back')
                await self.page.click('[data-knowledge-filter="videos"]')
                self.assertEqual(await self.page.locator('.knowledge-video p').all_text_contents(), expected['videos'])
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertEqual(await self.snapshot(), saved)
                self.assertEqual(await self.page.evaluate('state.language'), preference)
                if self.api_mode:
                    status, snapshot, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
                    self.assertEqual(status, 200)
                    self.assertEqual(snapshot['language'], preference)
                else:
                    self.assertEqual(await self.page.evaluate("localStorage.getItem('dogcare-language')"), preference)
                self.assertEqual(writes, [])
                self.assertEqual(self.console_errors, [])
                self.assertEqual(self.page_errors, [])

    async def test_invalid_registration_name_does_not_block_existing_dog_booking(self):
        daily = await self.page.evaluate('DailyModel.empty()')
        daily['clients'] = [{'id': 'existing-client', 'name': 'Fixture Client'}]
        daily['dogs'] = [{'id': 'new', 'name': 'Existing Pup', 'clientId': 'existing-client'}]
        await self.seed_daily(daily)
        await self.new_booking(new_dog=True)
        name = self.page.locator('#booking-form [name="dogName"]')
        await name.fill('🐕' * 121)
        self.assertFalse(await self.page.locator('#booking-form').evaluate('el => el.checkValidity()'))
        for _ in range(2):
            await self.page.select_option('#booking-form [name="dogId"]', 'new')
            self.assertFalse(await self.page.locator('#new-dog-field').is_visible())
            self.assertTrue(await self.page.locator('#booking-form').evaluate('el => el.checkValidity()'))
            self.assertTrue(await name.is_disabled())
            await self.page.select_option('#booking-form [name="dogId"]', label='Add a dog')
            self.assertTrue(await name.is_enabled())
            self.assertEqual(await name.input_value(), '🐕' * 121)
            self.assertFalse(await self.page.locator('#booking-form').evaluate('el => el.checkValidity()'))
        await self.page.select_option('#booking-form [name="dogId"]', 'new')
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['dogs'], daily['dogs'])
        self.assertEqual(saved['clients'], daily['clients'])
        self.assertEqual(len(saved['bookings']), 1)
        self.assertEqual(saved['bookings'][0]['dogId'], 'new')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(self.console_errors, [])

    async def test_document_upload_counts_unicode_filename_code_points(self):
        filename = 'F' * 175 + '🐕.pdf'
        label = 'L' * 119 + '🐕'
        pdf = b'%PDF-1.7\nUnicode upload fixture'
        await self.prepare_document()
        before = await self.snapshot()
        await self.page.fill('#document-form [name="label"]', label + 'X')
        self.assertEqual(await self.page.input_value('#document-form [name="label"]'), label + 'X')
        self.assertFalse(await self.page.locator('#document-form').evaluate('el => el.checkValidity()'))
        await self.page.click('#document-form button')
        await self.page.wait_for_function('!savePending')
        self.assertEqual(await self.snapshot(), before)
        await self.page.fill('#document-form [name="label"]', label)
        self.assertEqual(await self.page.input_value('#document-form [name="label"]'), label)
        for too_long in ('F' + filename, 'F' * 177 + '.pdf'):
            with self.subTest(filename=too_long):
                await self.page.set_input_files('#document-form [name="file"]', {
                    'name': too_long, 'mimeType': 'application/pdf', 'buffer': pdf})
                await self.page.click('#document-form button')
                await self.page.wait_for_function('!savePending')
                error = self.page.locator('#document-form .daily-error')
                self.assertTrue(await error.is_visible())
                self.assertEqual(await error.inner_text(), await self.page.evaluate('DailyUI.text("invalidFile")'))
                self.assertEqual(await self.snapshot(), before)
                self.assertEqual(await self.page.input_value('#document-form [name="label"]'), label)
                self.assertEqual(await self.page.input_value('#document-form [name="renewal"]'), '2027-10-05')
                self.assertEqual(await self.page.locator('#document-form [name="file"]').evaluate('el => el.files[0].name'), too_long)
        await self.page.set_input_files('#document-form [name="file"]', {
            'name': filename, 'mimeType': 'application/pdf', 'buffer': pdf})
        await self.page.click('#document-form button')
        await self.page.wait_for_function('!savePending')
        saved = await self.snapshot()
        self.assertTrue(saved and saved['documents'], 'The 180-code-point filename was rejected during upload')
        self.assertEqual(len(saved['documents']), 1)
        document = saved['documents'][0]
        self.assertEqual(document['name'], filename)
        self.assertEqual(document['label'], label)
        self.assertEqual(document['renewal'], '2027-10-05')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('dogs')
        async with self.page.expect_download() as download_event:
            await self.page.click(f'[data-open-document="{document["id"]}"]')
        download = await download_event.value
        self.assertEqual(download.suggested_filename, filename)
        self.assertEqual(Path(await download.path()).read_bytes(), pdf)
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(self.console_errors, [])

    async def test_registration_counts_unicode_name_code_points(self):
        client_name, dog_name = 'C' * 117 + '\u2028\u2029🐕', '🐕' * 120
        await self.new_booking(new_dog=True)
        before = await self.snapshot()
        for field, value in (('client', client_name), ('dogName', dog_name)):
            await self.page.fill(f'#booking-form [name="{field}"]', value)
            self.assertEqual(await self.page.input_value(f'#booking-form [name="{field}"]'), value)
        self.assertTrue(await self.page.locator('#booking-form').evaluate('el => el.checkValidity()'))
        for field, value in (('client', client_name), ('dogName', dog_name)):
            with self.subTest(field=field):
                too_long = value + 'X'
                await self.page.fill(f'#booking-form [name="{field}"]', too_long)
                self.assertEqual(await self.page.input_value(f'#booking-form [name="{field}"]'), too_long)
                self.assertFalse(await self.page.locator('#booking-form').evaluate('el => el.checkValidity()'))
                await self.page.click('#booking-form [type="submit"]')
                await self.page.wait_for_function('!savePending')
                self.assertEqual(await self.snapshot(), before)
                await self.page.fill(f'#booking-form [name="{field}"]', value)
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['clients'][0]['name'], client_name)
        self.assertEqual(saved['dogs'][0]['name'], dog_name)
        self.assertEqual(saved['dogs'][0]['clientId'], saved['clients'][0]['id'])
        self.assertEqual(saved['bookings'][0]['dogId'], saved['dogs'][0]['id'])
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_unicode_boundary_records_stay_visible_and_writable_after_reload(self):
        client_name, dog_name = 'C' * 119 + '🐕', 'D' * 119 + '🐕'
        label, filename = 'L' * 119 + '🐕', 'F' * 175 + '🐕.pdf'
        pdf = b'%PDF-1.7\nUnicode boundary fixture'
        daily = await self.page.evaluate('DailyModel.empty()')
        daily['clients'] = [{'id': 'unicode-client', 'name': client_name}]
        daily['dogs'] = [{'id': 'unicode-dog', 'name': dog_name, 'clientId': 'unicode-client'}]
        daily['bookings'] = [{'id': 'unicode-booking', 'dogId': 'unicode-dog', 'service': 'night',
                              'start': '2026-10-30', 'end': '2026-11-02',
                              'unitMinor': 1250, 'currency': 'CHF'}]
        document = {'dogId': 'unicode-dog', 'label': label, 'renewal': '', 'name': filename,
                    'type': 'application/pdf', 'data': base64.b64encode(pdf).decode()}
        if self.api_mode:
            status, body, _ = _http(self.port, 'PUT', '/api/daily', {'daily': daily}, self.sid)
            self.assertEqual(status, 200, body)
            status, body, _ = _http(self.port, 'POST', '/api/documents', document, self.sid)
            self.assertEqual(status, 200, body)
            daily = body['daily']
        else:
            daily['documents'] = [{**document, 'id': 'unicode-document'}]
            await self.page.evaluate("daily => localStorage.setItem('dogcare-daily-v1', JSON.stringify(daily))", daily)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), daily)
        await self.route('schedule')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        card = self.page.locator('[data-booking-id="unicode-booking"]')
        self.assertEqual(await card.count(), 1)
        self.assertEqual(await card.locator('strong').inner_text(), f'{dog_name} · {client_name}')
        await card.locator('[data-edit-booking]').click()
        self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), client_name)
        await self.page.fill('#booking-form [name="end"]', '2026-11-03')
        await self.submit_booking()
        daily['bookings'][0]['end'] = '2026-11-03'
        self.assertEqual(await self.snapshot(), daily)
        await self.page.reload()
        await self.wait_ready()
        await self.route('dogs')
        await self.page.click('[data-dog="unicode-dog"]')
        doc_id = daily['documents'][0]['id']
        doc = self.page.locator(f'[data-document-id="{doc_id}"]')
        self.assertEqual(await doc.locator('strong').inner_text(), label)
        async with self.page.expect_download() as download_event:
            await doc.locator('[data-open-document]').click()
        download = await download_event.value
        self.assertEqual(download.suggested_filename, filename)
        self.assertEqual(Path(await download.path()).read_bytes(), pdf)
        await doc.locator('summary').click()
        await doc.locator('[name="renewal"]').fill('2027-10-05')
        await doc.locator('[data-renewal] button').click()
        await self.page.wait_for_function('!savePending')
        daily['documents'][0]['renewal'] = '2027-10-05'
        self.assertEqual(await self.snapshot(), daily)
        await self.prepare_document()
        await self.page.click('#document-form button')
        await self.page.wait_for_function("document.querySelectorAll('[data-open-document]').length === 2 && !savePending")
        saved = await self.snapshot()
        self.assertEqual({**saved, 'documents': saved['documents'][:1]}, daily)
        self.assertEqual(saved['documents'][1]['dogId'], 'unicode-dog')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('business')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertIn(client_name, await self.page.locator('.daily-summary').inner_text())
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.capture_evidence(f'daily-unicode-boundary-{self.api_mode}.png')
        self.assertEqual(self.console_errors, [])

    async def test_currency_hundredths_in_quotes_extensions_bookings_and_summaries(self):
        seeded = await self.page.evaluate('DailyModel.empty()')
        seeded['rates'] = {'currency': 'JPY', 'walk': None, 'day': 0, 'night': 1250}
        seeded['clients'] = [{'id': 'currency-client', 'name': 'Existing Client'}]
        seeded['dogs'] = [{'id': 'currency-dog', 'name': 'Existing Pup', 'clientId': 'currency-client'}]
        seeded['bookings'] = [{'id': 'kwd-booking', 'dogId': 'currency-dog', 'service': 'day',
                               'start': '2026-10-30', 'end': '2026-10-30',
                               'unitMinor': 1250, 'currency': 'KWD'}]
        await self.seed_daily(seeded)
        await self.new_booking(start='2026-10-30', end='2026-11-01')
        await self.page.select_option('#booking-form [name="dogId"]', 'currency-dog')
        self.assertEqual(await self.page.input_value('#booking-form [name="unitMinor"]'), '12.50')
        self.assertRegex(await self.page.locator('#booking-quote > strong').inner_text(), r'JPY\s+25\.00(?!\d)')
        self.assertRegex(await self.page.locator('#booking-quote > p').inner_text(), r'JPY\s+12\.50(?!\d)')
        await self.submit_booking()
        saved = await self.snapshot()
        booking = saved['bookings'][1]
        self.assertEqual(booking['unitMinor'], 1250)
        self.assertEqual(booking['currency'], 'JPY')
        self.assertEqual(saved['bookings'][0], seeded['bookings'][0])
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('schedule')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        card = self.page.locator(f'[data-booking-id="{booking["id"]}"]')
        self.assertRegex(await card.inner_text(), r'JPY\s+25\.00(?!\d)')
        await card.locator('[data-edit-booking]').click()
        await self.page.fill('#booking-form [name="end"]', '2026-11-02')
        extension = await self.page.locator('#booking-quote > p').nth(1).inner_text()
        self.assertRegex(extension, r'\+1 units.*JPY\s+12\.50(?!\d)')
        self.assertRegex(extension, r'JPY\s+37\.50(?!\d)')
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.capture_evidence(f'daily-currency-hundredths-{self.api_mode}.png')
        await self.submit_booking()
        saved['bookings'][1]['end'] = '2026-11-02'
        self.assertEqual(await self.snapshot(), saved)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('business')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            with self.subTest(locale=locale):
                await self.page.select_option('#language-picker', locale)
                await self.page.wait_for_function('!savePending')
                for currency, amount in (('JPY', '25[.,]00'), ('KWD', '12[.,]50')):
                    row = self.page.locator('.daily-summary article').filter(has_text=currency)
                    self.assertRegex(await row.inner_text(), rf'{amount}(?!\d)')
                    total = self.page.locator('.daily-total').filter(has_text=currency)
                    self.assertRegex(await total.inner_text(), rf'{amount}(?!\d)')
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.page.select_option('#language-picker', 'en')
        await self.page.wait_for_function('!savePending')
        await self.page.fill('#daily-month', '2026-11')
        await self.page.locator('#daily-month').dispatch_event('change')
        self.assertRegex(await self.page.locator('.daily-summary').inner_text(), r'JPY\s+12\.50(?!\d)')
        self.assertRegex(await self.page.locator('.daily-total').inner_text(), r'JPY\s+12\.50(?!\d)')
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_same_named_clients_preserve_registered_dog_booking_relationship(self):
        seeded = await self.seed_same_named_clients()
        await self.new_booking()
        await self.page.select_option('#booking-form [name="dogId"]', 'dog-second')
        self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), 'Fixture Client')
        self.assertTrue(await self.page.locator('#booking-form [name="client"]').evaluate('el => el.readOnly'))
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['clients'], seeded['clients'])
        self.assertEqual(saved['dogs'], seeded['dogs'])
        self.assertEqual(saved['bookings'][0], seeded['bookings'][0])
        self.assertEqual(len(saved['bookings']), 2)
        booking = saved['bookings'][1]
        self.assertEqual(booking['dogId'], 'dog-second')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('schedule')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        await self.page.click(f'[data-edit-booking="{booking["id"]}"]')
        await self.page.fill('#booking-form [name="end"]', '2026-11-03')
        await self.submit_booking()
        booking['end'] = '2026-11-03'
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_same_named_clients_preserve_registered_dog_document_relationship(self):
        seeded = await self.seed_same_named_clients()
        await self.route('dogs')
        await self.page.click('[data-dog="dog-second"]')
        await self.prepare_document()
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual({**saved, 'documents': []}, seeded)
        self.assertEqual(len(saved['documents']), 1)
        self.assertEqual(saved['documents'][0]['dogId'], 'dog-second')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        await self.route('dogs')
        await self.page.click('[data-dog="dog-first"]')
        self.assertEqual(await self.page.locator('[data-open-document]').count(), 0)
        await self.page.click('[data-dog="dog-second"]')
        self.assertIn('Original proof', await self.page.locator('.daily-document').inner_text())
        async with self.page.expect_download() as download_event:
            await self.page.click('[data-open-document]')
        download = await download_event.value
        self.assertEqual(Path(await download.path()).read_bytes(), b'%PDF-1.7\nfixture')
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.capture_evidence(f'daily-same-named-clients-{self.api_mode}.png', full_page=False)
        self.assertEqual(self.console_errors, [])

    async def test_loaded_currency_survives_rate_edit_reload_and_new_booking(self):
        seeded = await self.page.evaluate('DailyModel.empty()')
        seeded['rates'] = {'currency': 'CAD', 'walk': None, 'day': 0, 'night': 2500}
        seeded['clients'] = [{'id': 'currency-client', 'name': 'Existing Client'}]
        seeded['dogs'] = [{'id': 'currency-dog', 'name': 'Existing Pup', 'clientId': 'currency-client'}]
        seeded['bookings'] = [{'id': 'currency-booking', 'dogId': 'currency-dog', 'service': 'night',
                               'start': '2026-10-30', 'end': '2026-11-02',
                               'unitMinor': 1800, 'currency': 'CHF'}]
        self.assertTrue(await self.page.evaluate('''async daily => {
            DailyModel.validateDaily(daily);
            if (window.DogCareAPI) return DogCareAPI.saveDaily(daily);
            localStorage.setItem('dogcare-daily-v1', JSON.stringify(daily));
            return true;
        }''', seeded))
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), seeded)
        await self.route('business')
        self.assertEqual(await self.page.input_value('#rates-form [name="currency"]'), 'CAD')
        self.assertEqual(await self.page.locator('#rates-form [name="currency"] option').all_text_contents(),
                         ['CHF', 'EUR', 'GBP', 'USD', 'CAD'])
        for service, value in (('walk', ''), ('day', '0.00'), ('night', '25.00')):
            self.assertEqual(await self.page.input_value(f'#rates-form [name="{service}"]'), value)
        await self.page.fill('#rates-form [name="night"]', '31.25')
        await self.page.click('#rates-form button')
        await self.page.wait_for_function("document.querySelector('#rates-saved').textContent === 'Saved' && !savePending")
        seeded['rates']['night'] = 3125
        self.assertEqual(await self.snapshot(), seeded)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), seeded)
        await self.route('business')
        self.assertEqual(await self.page.input_value('#rates-form [name="currency"]'), 'CAD')
        self.assertEqual(await self.page.input_value('#rates-form [name="night"]'), '31.25')
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        await self.capture_evidence(f'daily-loaded-currency-{self.api_mode}.png')
        await self.new_booking(new_dog=True)
        self.assertEqual(await self.page.input_value('#booking-form [name="unitMinor"]'), '31.25')
        self.assertIn('CAD', await self.page.locator('#booking-quote').inner_text())
        await self.submit_booking()
        saved = await self.snapshot()
        self.assertEqual(saved['rates'], seeded['rates'])
        self.assertEqual(saved['bookings'][0], seeded['bookings'][0])
        self.assertEqual(len(saved['bookings']), 2)
        self.assertEqual(saved['bookings'][1]['currency'], 'CAD')
        self.assertEqual(saved['bookings'][1]['unitMinor'], 3125)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    async def test_rates_confirmation_clears_on_edits(self):
        await self.rates('25.00')
        await self.page.fill('#rates-form [name="night"]', '30.00')
        self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
        self.assertEqual((await self.snapshot())['rates']['night'], 2500)
        await self.page.click('#rates-form button')
        await self.page.wait_for_function("document.querySelector('#rates-saved').textContent === 'Saved' && !savePending")
        await self.page.select_option('#rates-form [name="currency"]', 'EUR')
        self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
        self.assertEqual((await self.snapshot())['rates']['currency'], 'CHF')
        self.assertEqual(self.console_errors, [])

    async def test_rates_confirmation_clears_before_failed_submission(self):
        await self.rates('25.00')
        saved = await self.snapshot()
        await self.page.evaluate('''() => {
            if (window.DogCareAPI) {
                DogCareAPI.saveDaily = () => new Promise(resolve => { window.failSave = () => resolve(false); });
            } else {
                const original = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key, value) {
                    if (key === 'dogcare-daily-v1') {
                        window.confirmationAtWrite = document.querySelector('#rates-saved').textContent;
                        throw new DOMException('Full', 'QuotaExceededError');
                    }
                    return original.call(this, key, value);
                };
            }
        }''')
        await self.page.click('#rates-form button')
        if self.api_mode:
            await self.page.wait_for_function('!!window.failSave')
            self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
            await self.page.evaluate('window.failSave()')
        else:
            await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
            self.assertEqual(await self.page.evaluate('window.confirmationAtWrite'), '')
        await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
        self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
        self.assertEqual(await self.page.input_value('#rates-form [name="night"]'), '25.00')
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_rates_confirmation_clears_before_validation_failure(self):
        await self.rates('25.00')
        saved = await self.snapshot()
        await self.page.evaluate("document.querySelector('#rates-form').elements.night.value = 'invalid'")
        await self.page.click('#rates-form button')
        await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
        self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
        self.assertEqual(await self.page.input_value('#rates-form [name="night"]'), 'invalid')
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_literal_new_dog_id_preserves_booking_and_note_relationships(self):
        dog = {'id': 'new', 'name': 'Existing Pup', 'clientId': 'existing-client'}
        client = {'id': 'existing-client', 'name': 'Fixture Client'}
        if self.api_mode:
            status, _, _ = _http(self.port, 'POST', '/api/dogs',
                                {'slug': dog['id'], 'name': dog['name']}, self.sid)
            self.assertEqual(status, 200)
        else:
            await self.page.evaluate('''({dog, client}) => {
                const daily = DailyModel.empty();
                daily.dogs.push(dog);
                daily.clients.push(client);
                DailyModel.validateDaily(daily);
                localStorage.setItem('dogcare-daily-v1', JSON.stringify(daily));
            }''', {'dog': dog, 'client': client})
        await self.page.reload()
        await self.wait_ready()
        await self.route('capture')
        await self.page.click('[data-capture-dog="new"]')
        await self.page.fill('#observation', 'Existing pup rested after the walk.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        notes = await self.page.evaluate('state.observations')

        await self.route('dogs')
        await self.page.click('[data-dog="billie"]')
        await self.new_booking()
        await self.page.select_option('#booking-form [name="dogId"]', 'billie')
        await self.page.select_option('#booking-form [name="dogId"]', 'new')
        self.assertFalse(await self.page.locator('#new-dog-field').is_visible())
        self.assertFalse(await self.page.locator('[name="dogName"]').evaluate('el => el.required'))
        if self.api_mode:
            await self.page.fill('#booking-form [name="client"]', client['name'])
        else:
            self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), client['name'])
            self.assertTrue(await self.page.locator('[name="client"]').evaluate('el => el.readOnly'))
        await self.submit_booking()
        first = await self.snapshot()
        self.assertEqual(len(first['dogs']), 1)
        self.assertEqual(first['dogs'][0], {**dog, 'clientId': first['clients'][0]['id']})
        self.assertEqual(first['clients'], [{**client, 'id': first['dogs'][0]['clientId']}])
        self.assertEqual(first['bookings'][0]['dogId'], 'new')
        if not self.api_mode:
            self.assertEqual(first['dogs'], [dog])
            self.assertEqual(first['clients'], [client])

        await self.new_booking(new_dog=True)
        self.assertTrue(await self.page.locator('#new-dog-field').is_visible())
        self.assertTrue(await self.page.locator('[name="dogName"]').evaluate('el => el.required'))
        self.assertTrue(await self.page.evaluate('''() => {
            const daily = DailyModel.empty();
            daily.clients.push({id: 'client', name: 'Client'});
            daily.dogs.push({id: document.querySelector('[name="dogId"]').value,
                name: 'Dog', clientId: 'client'});
            try { DailyModel.validateDaily(daily); return false; } catch { return true; }
        }'''))
        await self.page.select_option('#booking-form [name="clientId"]', first['clients'][0]['id'])
        await self.submit_booking()
        created = await self.snapshot()
        self.assertEqual(len(created['dogs']), 2)
        self.assertEqual(created['dogs'][0], first['dogs'][0])
        self.assertNotEqual(created['dogs'][1]['id'], 'new')
        self.assertEqual(created['bookings'][0], first['bookings'][0])
        self.assertEqual(created['bookings'][1]['dogId'], created['dogs'][1]['id'])
        self.assertEqual(created['clients'], first['clients'])

        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), created)
        await self.route('schedule')
        await self.page.fill('#daily-month', '2026-10')
        await self.page.locator('#daily-month').dispatch_event('change')
        await self.page.click(f'[data-edit-booking="{first["bookings"][0]["id"]}"]')
        self.assertEqual(await self.page.input_value('#booking-form [name="dogId"]'), 'new')
        self.assertFalse(await self.page.locator('#new-dog-field').is_visible())
        self.assertEqual(await self.page.input_value('#booking-form [name="client"]'), client['name'])
        await self.page.fill('#booking-form [name="end"]', '2026-11-03')
        self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), 390)
        await self.capture_evidence(f'daily-literal-new-dog-{self.api_mode}.png')
        await self.submit_booking()
        await self.page.reload()
        await self.wait_ready()
        created['bookings'][0]['end'] = '2026-11-03'
        self.assertEqual(await self.snapshot(), created)
        saved_notes = await self.page.evaluate('state.observations')
        self.assertEqual({key: saved_notes[key] for key in notes}, notes)
        self.assertEqual(saved_notes[created['dogs'][1]['id']], [])
        self.assertEqual(self.console_errors, [])

    async def test_document_read_locks_navigation_and_snapshots_owner_and_form(self):
        await self.prepare_document()
        await self.page.evaluate('''() => {
            const read = File.prototype.arrayBuffer;
            window.fileReads = 0;
            File.prototype.arrayBuffer = function() {
                window.fileReads++;
                return new Promise(resolve => { window.finishFileRead = () => resolve(read.call(this)); });
            };
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_function('!!window.finishFileRead')
        locked = await self.page.evaluate('''() => ({
            pending: savePending, inert: document.querySelector('.app-shell').inert,
            disabled: document.querySelector('#document-form button').disabled
        })''')
        await self.page.evaluate('''() => {
            const form = document.querySelector('#document-form');
            form.requestSubmit();
            form.elements.label.value = 'Changed during read';
            form.elements.renewal.value = '2029-01-01';
            navigate('capture');
            state.dog = 'charlie';
            window.finishFileRead();
        }''')
        await self.page.wait_for_function('''() => {
            const daily = window.DogCareAPI ? DogCareAPI.getDaily() : JSON.parse(localStorage.getItem('dogcare-daily-v1'));
            return daily?.documents.length > 0 && !savePending;
        }''')
        document = (await self.snapshot())['documents'][0]
        self.assertEqual(document['dogId'], 'billie')
        self.assertEqual(document['label'], 'Original proof')
        self.assertEqual(document['renewal'], '2027-10-05')
        self.assertEqual(locked, {'pending': True, 'inert': True, 'disabled': True})
        self.assertEqual(await self.page.evaluate('window.fileReads'), 1)
        self.assertEqual(len((await self.snapshot())['documents']), 1)
        self.assertEqual(self.console_errors, [])

    async def test_document_failure_releases_guard_and_keeps_retryable_form(self):
        await self.prepare_document()
        await self.page.evaluate('''() => {
            window.originalRead = File.prototype.arrayBuffer;
            File.prototype.arrayBuffer = () => Promise.reject(new Error('Unreadable fixture'));
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('#document-form .daily-error:not([hidden])')
        self.assertFalse(await self.page.evaluate('savePending || document.querySelector(".app-shell").inert'))
        self.assertEqual(await self.page.input_value('#document-form [name="label"]'), 'Original proof')
        self.assertFalse(await self.page.locator('#document-form button').is_disabled())
        await self.page.evaluate('() => { File.prototype.arrayBuffer = window.originalRead; }')
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        self.assertEqual(len((await self.snapshot())['documents']), 1)

    async def test_upload_stays_guarded_through_registration_and_document_save(self):
        if not self.api_mode:
            self.skipTest('Account registration and upload requests')
        await self.prepare_document()
        await self.page.evaluate('''() => {
            for (const method of ['saveDaily', 'saveDocument']) {
                const original = DogCareAPI[method];
                DogCareAPI[method] = async (...args) => {
                    const saved = await original(...args);
                    await new Promise(resolve => { window['finish_' + method] = resolve; });
                    return saved;
                };
            }
        }''')
        await self.page.click('#document-form button')
        for method in ('saveDaily', 'saveDocument'):
            await self.page.wait_for_function('(method) => !!window["finish_" + method]', arg=method)
            self.assertTrue(await self.page.evaluate('savePending && document.querySelector(".app-shell").inert'))
            await self.page.evaluate('''() => {
                document.querySelector('#document-form').requestSubmit();
                navigate('capture');
            }''')
            self.assertEqual(await self.page.evaluate('state.page'), 'dogs')
            await self.page.evaluate('(method) => window["finish_" + method]()', method)
        await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        self.assertEqual(len(saved['dogs']), 1)
        self.assertEqual(len(saved['documents']), 1)
        self.assertEqual(saved['documents'][0]['dogId'], 'billie')
        self.assertEqual(self.console_errors, [])

    async def test_registered_dogs_keep_notes_and_routes_after_sample_reset(self):
        await self.new_booking(new_dog=True)
        await self.submit_booking()
        noted = (await self.snapshot())['dogs'][0]['id']
        await self.new_booking(new_dog=True)
        await self.page.fill('#booking-form [name="dogName"]', 'Empty Pup')
        await self.submit_booking()
        empty = (await self.snapshot())['dogs'][1]['id']
        for dog_id in (noted, 'billie'):
            await self.route('capture')
            await self.page.click(f'[data-capture-dog="{dog_id}"]')
            await self.page.fill('#observation', 'Saved real note for ' + dog_id)
            await self.page.click('#save-observation')
            await self.page.wait_for_selector('.timeline-card')
        await self.page.evaluate('''async () => {
            state.observations.billie = state.observations.billie.filter(note => note.id !== 1);
            state.observations.billie.push({id: 1, time: '10:00', date: localDay(),
                title: 'Stored arrival fact', text: 'Owner recorded arrival and consent.', tags: []});
            await saveObservations();
        }''')
        await self.page.reload()
        await self.wait_ready()
        records = await self.snapshot()
        before = await self.page.evaluate('structuredClone(state.observations)')
        await self.route('settings')
        if self.api_mode:
            self.assertEqual(await self.page.locator('#reset-demo').count(),0)
            await self.route('dashboard')
        else:
            await self.page.click('#reset-demo')
            await self.page.wait_for_function('state.page === "dashboard" && !savePending')
        self.assertEqual(await self.snapshot(), records)
        after = await self.page.evaluate('state.observations')
        self.assertEqual(after.get(noted), before[noted])
        self.assertEqual(after.get(empty), [])
        self.assertIn(before['billie'][0], after['billie'])
        self.assertIn(before['billie'][-1], after['billie'])
        self.assertEqual(len({note['id'] for note in after['billie']}), len(after['billie']))
        await self.route('handoff')
        await self.page.click('[data-evidence-id="1"]')
        self.assertEqual(await self.page.locator('#observation-1').count(), 1)
        self.assertIn('Owner recorded arrival and consent.', await self.page.locator('#observation-1').inner_text())
        for dog_id in (empty, noted):
            await self.route('dogs')
            await self.page.click(f'[data-dog="{dog_id}"]')
            for route in ('dogs', 'handoff', 'story', 'capture'):
                await self.route(route)
                self.assertEqual(await self.page.evaluate('state.page'), route)
            await self.page.fill('#observation', 'After reset ' + dog_id)
            await self.page.click('#save-observation')
            await self.page.wait_for_function('state.page === "dogs" && !savePending')
            self.assertIn('After reset ' + dog_id, await self.page.locator('.timeline').inner_text())
        await self.page.reload()
        await self.wait_ready()
        final = await self.page.evaluate('state.observations')
        self.assertEqual(final[noted][1:], before[noted])
        self.assertIn(before['billie'][0], final['billie'])
        self.assertEqual(await self.snapshot(), records)
        self.assertEqual(self.console_errors, [])

    async def test_registered_profiles_have_no_invented_arrival_or_consent(self):
        await self.new_booking(new_dog=True, start='2099-10-30', end='2099-11-02')
        await self.submit_booking()
        dog_id = (await self.snapshot())['dogs'][0]['id']
        await self.page.reload()
        await self.wait_ready()
        await self.route('dogs')
        await self.page.click(f'[data-dog="{dog_id}"]')
        for locale in ('en', 'fr', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            hero = await self.page.locator('.profile-hero').inner_text()
            for label in ('Checked in', 'Consent on file'):
                self.assertNotIn((await self.page.evaluate('(label) => t(label)', label)).lower(), hero.lower())
        await self.page.select_option('#language-picker', 'en')
        await self.page.wait_for_function('!savePending')
        await self.page.click('[data-dog="billie"]')
        self.assertIn('Sample', await self.page.locator('.timeline').inner_text())
        self.assertNotIn('Consent on file', await self.page.locator('.profile-hero').inner_text())

    async def test_additional_dogs_fit_care_pickers_at_all_sizes(self):
        for index in range(3):
            await self.new_booking(new_dog=True)
            await self.page.fill('#booking-form [name="dogName"]', 'Registered' + 'longname' * 10 + str(index))
            await self.submit_booking()
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')
        for width, height in ((390, 844), (1024, 768), (1440, 900)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            for route in ('capture', 'dogs', 'story'):
                await self.route(route)
                self.assertEqual(await self.page.locator('.dog-pick').count(), 5)
                self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
                for button in await self.page.locator('.dog-pick').all():
                    box = await button.bounding_box()
                    self.assertGreaterEqual(box['width'], 44)
                    self.assertGreaterEqual(box['height'], 44)
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], width)
                    self.assertTrue(await button.evaluate('el => el.scrollWidth <= el.clientWidth'))
                await self.capture_evidence(f'daily-dog-pickers-{route}-{width}-{self.api_mode}.png')
        self.assertEqual(self.console_errors, [])

    async def test_long_dog_and_client_names_wrap_across_care_routes(self):
        dog_name, client_name = 'W' * 120, 'M' * 120
        await self.new_booking(new_dog=True)
        await self.page.fill('#booking-form [name="dogName"]', dog_name)
        await self.page.fill('#booking-form [name="client"]', client_name)
        await self.submit_booking()
        saved = await self.snapshot()
        dog_id = saved['dogs'][0]['id']
        await self.route('capture')
        await self.page.click(f'[data-capture-dog="{dog_id}"]')
        await self.page.fill('#observation', 'Rested after the walk.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        await self.route('dogs')
        await self.page.click(f'[data-dog="{dog_id}"]')
        self.assertEqual(await self.page.locator('.profile-hero h2').inner_text(), dog_name)
        self.assertIn(client_name, await self.page.locator('.profile-hero p').inner_text())
        failures = []
        for width, height in ((390, 844), (768, 1024), (1024, 768), (1440, 900)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            for locale in ('fr', 'en', 'it', 'de', 'es'):
                await self.page.select_option('#language-picker', locale)
                await self.page.wait_for_function('!savePending')
                for route in ('dashboard', 'dogs', 'capture', 'handoff', 'story', 'schedule', 'business'):
                    await self.route(route)
                    await self.page.evaluate('document.fonts.ready')
                    overflow = await self.page.evaluate('''() => {
                        const selectors = '#page-title, .dog-meta, .profile-hero, .page-title-row, '
                            + '.handoff-card-head, .story-body, #save-observation, .daily-record';
                        return [...document.querySelectorAll(selectors)].filter(el => {
                            const box = el.getBoundingClientRect();
                            return box.left < 0 || box.right > innerWidth + 1 || el.scrollWidth > el.clientWidth + 1;
                        }).map(el => el.id || el.className);
                    }''')
                    if await self.page.evaluate('document.documentElement.scrollWidth') > width:
                        overflow.append('page')
                    if overflow:
                        failures.append((width, locale, route, overflow))
                    if locale == 'fr' and width in (390, 1024) and route in ('dashboard', 'dogs', 'handoff', 'story'):
                        await self.capture_evidence(f'daily-long-names-{route}-{width}-{self.api_mode}.png')
                    active = self.page.locator(f'[data-page="{route}"]')
                    self.assertEqual(await active.get_attribute('aria-current'), 'page')
                    if await active.is_visible():
                        self.assertGreaterEqual((await active.bounding_box())['height'], 44)
                    if route == 'capture':
                        button = self.page.locator('#save-observation')
                        self.assertIn(dog_name, await button.inner_text())
                        self.assertGreaterEqual((await button.bounding_box())['height'], 44)
                        await button.focus()
                        self.assertTrue(await button.evaluate('el => el === document.activeElement'))
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(failures, [])
        self.assertEqual(self.console_errors, [])

    async def assert_recovered_care_profile(self, dog_id, name, note):
        await self.route('dashboard')
        card = self.page.locator(f'.dog-card[data-dog="{dog_id}"]')
        self.assertEqual(await card.count(), 1)
        self.assertEqual(await card.locator('.dog-name').inner_text(), name)
        await card.click()
        self.assertEqual(await self.page.locator('#page-title').inner_text(), name)
        self.assertIn(note['text'], await self.page.locator('.timeline').inner_text())
        profile = await self.page.evaluate('(id) => dogs[id]', dog_id)
        self.assertEqual(profile['owner'], '')
        self.assertEqual(profile['health'], 'Add current health and medication instructions.')
        self.assertEqual(profile['vets'], [])
        self.assertEqual(await self.page.locator('.profile-hero .mini-tags').count(), 0)
        for route, attribute in (('dogs', 'dog'), ('capture', 'capture-dog'),
                                 ('handoff', 'handoff-dog'), ('story', 'story-dog')):
            await self.route(route)
            await self.page.click(f'[data-{attribute}="billie"]')
            await self.page.click(f'[data-{attribute}="{dog_id}"]')
            self.assertEqual(await self.page.evaluate('state.dog'), dog_id)
            if route == 'handoff':
                await self.page.click(f'[data-evidence-id="{note["id"]}"]')
                self.assertIn(note['text'], await self.page.locator(f'#observation-{note["id"]}').inner_text())
            if route == 'story':
                self.assertIn(note['text'], await self.page.locator('.story-copy').inner_text())

    async def test_account_dog_identities_remain_selectable_without_daily_records(self):
        if not self.api_mode:
            self.skipTest('Account dog identities')
        dog_id, name = 'Dog_1', 'Account Pup'
        status, _, _ = _http(self.port, 'POST', '/api/dogs', {'slug': dog_id, 'name': name}, self.sid)
        self.assertEqual(status, 200)
        await self.page.reload()
        await self.wait_ready()
        await self.route('capture')
        self.assertEqual(await self.page.locator(f'[data-capture-dog="{dog_id}"]').count(), 1)
        await self.page.click(f'[data-capture-dog="{dog_id}"]')
        await self.page.fill('#observation', 'Account dog rested calmly.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        note = await self.page.evaluate('(id) => state.observations[id][0]', dog_id)
        await self.page.reload()
        await self.wait_ready()
        await self.assert_recovered_care_profile(dog_id, name, note)
        self.assertEqual((await self.snapshot())['dogs'], [])
        async def corrupt_daily(route):
            response = await route.fetch()
            payload = await response.json()
            payload['daily'] = {'version': 99}
            await route.fulfill(response=response, json=payload)
        await self.page.route('**/api/state', corrupt_daily)
        await self.page.reload()
        await self.wait_ready()
        self.assertTrue(await self.page.locator('.daily-error').is_visible())
        await self.assert_recovered_care_profile(dog_id, name, note)
        self.assertEqual(self.console_errors, [])

    async def test_stale_document_snapshot_requires_reload_and_retains_draft(self):
        if not self.api_mode:
            self.skipTest('Account revision recovery')
        await self.prepare_document()
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        await self.route('business')
        await self.page.fill('#rates-form [name="day"]', '42.00')
        status, uploaded, _ = _http(self.port, 'POST', '/api/documents', {
            'dogId': 'billie', 'label': 'Other tab', 'renewal': '', 'name': 'other.pdf',
            'type': 'application/pdf', 'data': 'JVBERi0xLjcK'}, self.sid)
        self.assertEqual(status, 200, uploaded)
        writes = []
        self.page.on('request', lambda request: writes.append(request) if request.url.endswith('/api/daily') else None)
        await self.page.click('#rates-form button')
        await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
        self.assertIn('reload', (await self.page.locator('#toast').inner_text()).lower())
        self.assertEqual(await self.page.input_value('#rates-form [name="day"]'), '42.00')
        await self.page.click('#rates-form button')
        await self.page.wait_for_function('!savePending')
        self.assertEqual(len(writes), 1)
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.sid)[1], uploaded)
        self.assertTrue(any('409' in error for error in self.console_errors))
        self.console_errors[:] = [error for error in self.console_errors if '409' not in error]
        self.assertEqual(self.console_errors, [])

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
        await self.page.select_option('#document-form [name="clientId"]', ':new')
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

    async def open_tab(self, route):
        page = await self.context.new_page()
        page.set_default_timeout(10000)
        page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        page.on('console', lambda message: self.console_errors.append(message.text) if message.type == 'error' else None)
        await page.goto(self.url)
        await page.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
        await self.open_route(f'{route}', page=page)
        if route == 'business':
            await page.click('[data-finance-tab="rates"]')
        return page

    async def assert_stale_rates_preserve_records(self, record):
        await self.rates('25.00')
        other = await self.open_tab('business')
        await other.fill('#rates-form [name="day"]', '42.00')
        if record == 'booking':
            await self.new_booking(new_dog=True)
            await self.submit_booking()
        else:
            await self.prepare_document()
            await self.page.click('#document-form button')
            await self.page.wait_for_selector('[data-open-document]')
        saved = await self.snapshot()
        for _ in range(2):
            await other.click('#rates-form button')
            await other.wait_for_function('!savePending')
            self.assertEqual(await self.snapshot(), saved)
            self.assertTrue(await other.locator('#rates-form .daily-error').is_visible())
            self.assertIn('reload', (await other.locator('#rates-form .daily-error').inner_text()).lower())
            self.assertEqual(await other.input_value('#rates-form [name="day"]'), '42.00')
            self.assertEqual(await other.locator('#rates-saved').inner_text(), '')
        await other.reload()
        await other.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
        await self.open_route('business', page=other)
        await other.click('[data-finance-tab="rates"]')
        await other.fill('#rates-form [name="day"]', '42.00')
        await other.click('#rates-form button')
        await other.wait_for_function("document.querySelector('#rates-saved').textContent === 'Saved' && !savePending")
        saved['rates']['day'] = 4200
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_stale_rates_preserve_other_tabs_booking(self):
        await self.assert_stale_rates_preserve_records('booking')

    async def test_stale_rates_preserve_other_tabs_document(self):
        await self.assert_stale_rates_preserve_records('document')

    async def save_other_tabs_rates(self):
        other = await self.open_tab('business')
        await other.fill('#rates-form [name="day"]', '42.00')
        await other.click('#rates-form button')
        await other.wait_for_function("document.querySelector('#rates-saved').textContent === 'Saved' && !savePending")
        return await self.snapshot()

    async def assert_conflict_preserves_form(self, form, saved, values):
        await self.page.wait_for_selector(f'{form} .daily-error:not([hidden])')
        await self.page.wait_for_function('!savePending')
        self.assertEqual(await self.snapshot(), saved)
        self.assertIn('reload', (await self.page.locator(f'{form} .daily-error').inner_text()).lower())
        for name, value in values.items():
            self.assertEqual(await self.page.input_value(f'{form} [name="{name}"]'), value)
        self.assertFalse(await self.page.locator(f'{form} button').first.is_disabled())
        self.assertFalse(await self.page.evaluate('document.querySelector(".app-shell").inert'))
        self.assertEqual(self.console_errors, [])

    async def test_stale_booking_preserves_other_tabs_rates_and_draft(self):
        await self.new_booking(new_dog=True)
        saved = await self.save_other_tabs_rates()
        await self.page.click('#booking-form [type="submit"]')
        await self.assert_conflict_preserves_form('#booking-form', saved, {
            'dogName': 'Fixture Pup', 'client': 'Fixture Client',
            'start': '2026-10-30', 'end': '2026-11-02',
        })

    async def test_document_checks_for_conflicts_after_reading_file(self):
        await self.prepare_document()
        await self.page.evaluate('''() => {
            const original = File.prototype.arrayBuffer;
            File.prototype.arrayBuffer = function() {
                return new Promise(resolve => { window.finishRead = () => resolve(original.call(this)); });
            };
        }''')
        await self.page.click('#document-form button')
        await self.page.wait_for_function('!!window.finishRead && savePending')
        saved = await self.save_other_tabs_rates()
        await self.page.evaluate('window.finishRead()')
        await self.assert_conflict_preserves_form('#document-form', saved, {
            'label': 'Original proof', 'renewal': '2027-10-05',
        })
        self.assertEqual(await self.page.locator('#document-form [name="file"]').evaluate('el => el.files[0].name'), 'proof.pdf')

    async def test_stale_renewal_preserves_other_tabs_rates_and_draft(self):
        await self.prepare_document()
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        await self.page.click('.daily-document summary')
        await self.page.fill('[data-renewal] [name="renewal"]', '2029-01-01')
        saved = await self.save_other_tabs_rates()
        await self.page.click('[data-renewal] button')
        await self.assert_conflict_preserves_form('[data-renewal]', saved, {'renewal': '2029-01-01'})

    async def test_simultaneous_booking_and_rates_saves_reject_one_snapshot(self):
        await self.new_booking(new_dog=True)
        other = await self.open_tab('business')
        await other.fill('#rates-form [name="day"]', '42.00')
        await other.evaluate('''() => {
            navigator.locks.request('dogcare-daily-v1', () => new Promise(resolve => {
                window.releaseWrite = resolve;
            }));
        }''')
        await other.wait_for_function('!!window.releaseWrite')
        await self.page.evaluate("document.querySelector('#booking-form').requestSubmit()")
        await other.evaluate("document.querySelector('#rates-form').requestSubmit()")
        self.assertTrue(await self.page.evaluate('savePending'))
        self.assertTrue(await other.evaluate('savePending'))
        self.assertIsNone(await self.snapshot())
        await other.evaluate('window.releaseWrite()')
        await self.page.wait_for_function('!savePending')
        await other.wait_for_function('!savePending')
        saved = await self.snapshot()
        self.assertEqual(len(saved['bookings']), 1)
        self.assertIsNone(saved['rates']['day'])
        self.assertEqual(await self.page.locator('#booking-form').count(), 0)
        self.assertTrue(await other.locator('#rates-form .daily-error').is_visible())
        self.assertEqual(await other.locator('#rates-saved').inner_text(), '')
        self.assertEqual(await other.input_value('#rates-form [name="day"]'), '42.00')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_missing_browser_lock_support_retains_records_and_draft(self):
        await self.rates('25.00')
        saved = await self.snapshot()
        await self.page.evaluate("Object.defineProperty(navigator, 'locks', {value: undefined})")
        await self.page.fill('#rates-form [name="night"]', '30.00')
        await self.page.click('#rates-form button')
        await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(await self.page.input_value('#rates-form [name="night"]'), '30.00')
        self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
        self.assertIn('HTTPS', await self.page.locator('#rates-form .daily-error').inner_text())
        self.assertEqual(self.console_errors, [])

    async def test_stale_save_recovery_is_localized_without_overflow(self):
        saved = await self.save_other_tabs_rates()
        for width, height in ((390, 844), (1024, 768), (1440, 900)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            for locale, prefix in (('fr', 'Non enregistré.'), ('en', 'Not saved.'),
                                   ('it', 'Non salvato.'), ('de', 'Nicht gespeichert.'),
                                   ('es', 'No guardado.')):
                await self.page.select_option('#language-picker', locale)
                await self.route('business')
                await self.page.fill('#rates-form [name="day"]', '31.00')
                await self.page.click('#rates-form button')
                await self.page.wait_for_selector('#rates-form .daily-error:not([hidden])')
                self.assertTrue((await self.page.locator('#rates-form .daily-error').inner_text()).startswith(prefix))
                self.assertEqual(await self.page.input_value('#rates-form [name="day"]'), '31.00')
                self.assertEqual(await self.page.locator('#rates-saved').inner_text(), '')
                self.assertEqual(await self.snapshot(), saved)
                self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
                if locale == 'fr':
                    await self.capture_evidence(f'daily-stale-rates-fr-{width}.png')
        self.assertEqual(self.console_errors, [])

    async def test_registered_dog_notes_survive_static_to_account_import(self):
        await self.new_booking(new_dog=True)
        await self.submit_booking()
        dog_id = (await self.snapshot())['dogs'][0]['id']
        await self.route('capture')
        await self.page.click(f'[data-capture-dog="{dog_id}"]')
        await self.page.fill('#observation', 'Imported pup drank water after the walk.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        note = await self.page.evaluate('(id) => state.observations[id][0]', dog_id)
        self.assertIsNone(note.pop('audio'))
        await self.prepare_document()
        await self.page.click('#document-form button')
        await self.page.wait_for_selector('[data-open-document]')
        local = await self.page.evaluate('Object.fromEntries(Object.entries(localStorage))')
        self.static_httpd.RequestHandlerClass = self.server_mod.Handler
        self.addCleanup(setattr, self.static_httpd, 'RequestHandlerClass',
                        partial(QuietStaticHandler, directory=str(ROOT)))
        self.api_mode = True
        self.sid = self.login('registered-import@example.com')
        await self.context.add_cookies([{'name': 'dc_s', 'value': self.sid, 'url': self.url, 'httpOnly': True}])
        await self.page.reload()
        await self.wait_ready()
        imported = _http(self.port, 'GET', '/api/state', cookie=self.sid)[1]
        self.assertTrue(imported['imported'])
        self.assertEqual(imported['observations'][dog_id], [note])
        self.assertEqual(imported['daily'], await self.page.evaluate('DailyModel.empty()'))
        identity = next(dog for dog in imported['dogs'] if dog['slug'] == dog_id)
        await self.assert_recovered_care_profile(dog_id, identity['name'], note)
        await self.route('capture')
        await self.page.fill('#observation', 'Account follow-up for the imported pup.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        saved = _http(self.port, 'GET', '/api/state', cookie=self.sid)[1]
        self.assertEqual(saved['observations'][dog_id][1:], [note])
        self.assertEqual(saved['dogs'], imported['dogs'])
        self.assertEqual(saved['daily'], imported['daily'])
        for key, value in local.items():
            self.assertEqual(await self.page.evaluate('key => localStorage.getItem(key)', key), value)
        fresh = await self.browser.new_context(viewport={'width': 390, 'height': 844}, timezone_id='Europe/Paris')
        self.addAsyncCleanup(fresh.close)
        await fresh.add_cookies([{'name': 'dc_s', 'value': self.sid, 'url': self.url, 'httpOnly': True}])
        self.page = await fresh.new_page()
        self.page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        self.page.on('console', lambda message: self.console_errors.append(message.text) if message.type == 'error' else None)
        await self.page.goto(self.url)
        await self.wait_ready()
        await self.assert_recovered_care_profile(dog_id, identity['name'], saved['observations'][dog_id][0])
        self.assertEqual(await self.page.evaluate('localStorage.length'), 0)
        self.assertEqual(await self.page.evaluate('(id) => state.observations[id]', dog_id), saved['observations'][dog_id])
        self.assertEqual(self.console_errors, [])

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
