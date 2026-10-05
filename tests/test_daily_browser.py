"""Operational booking, summary and document journeys in disposable browser accounts."""
import threading
from datetime import date, timedelta
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT
from tests.test_tenant_isolation import _http


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

    async def prepare_document(self):
        await self.route('dogs')
        await self.page.fill('#document-form [name="label"]', 'Original proof')
        await self.page.fill('#document-form [name="renewal"]', '2027-10-05')
        await self.page.set_input_files('#document-form [name="file"]', {
            'name': 'proof.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.7\nfixture'})

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
                    active = self.page.locator(f'#main-nav [data-page="{route}"]')
                    self.assertEqual(await active.get_attribute('aria-current'), 'page')
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
        await page.click(f'#main-nav [data-page="{route}"]')
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
        await other.click('#main-nav [data-page="business"]')
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
