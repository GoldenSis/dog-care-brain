"""Owner chooses individual records; a professional sees only that selection."""
import asyncio
import uuid

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import _http, _latest_link
from tests.test_media_api import png_fixture, upload_raw


class ProfessionalJourneyTest(BrowserFixture):
    async def asyncSetUp(self):
        self.sid = self.login(uuid.uuid4().hex + '-owner@example.com')
        self.professional_email = 'specialiste-' + uuid.uuid4().hex[:8] + '@example.com'
        current = {'version': 1, 'clients': [{'id': 'a', 'name': 'Private family A'}, {'id': 'b', 'name': 'Private family B'}],
                   'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'a'}, {'id': 'pablo', 'name': 'Pablo', 'clientId': 'b'}],
                   'bookings': [], 'rates': {'currency': 'CHF', 'day': None, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': current}, cookie=self.sid)[0], 200)
        await super().asyncSetUp()
        notes = {'nino': [{'id': 1, 'title': 'Promenade du matin', 'text': 'Nino a marché tranquillement au parc.', 'date': '2026-10-08'},
                          {'id': 2, 'title': 'Note interne non partagée', 'text': 'Rappel privé pour Adine-Sophie.'}],
                 'pablo': [{'id': 3, 'title': 'Note de Pablo', 'text': 'Information privée pour une autre famille.'}]}
        self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': notes}, cookie=self.sid)[0], 200)
        status, media = upload_raw(self.port, self.sid, png_fixture(width=360, height=200))
        self.assertEqual(status, 200)
        self.media_id = media['uploadedId']
        await self.page.reload()
        await self.wait_ready()
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')

    async def capture_widths(self, stem):
        await self.page.wait_for_function("!document.querySelector('#toast.show')")
        for width in (1440, 390):
            await self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
            await self.capture_evidence(f'{stem}-{width}.png')

    async def test_capture_and_photo_appear_in_selection_without_reload(self):
        await self.page.click('.topbar [data-go="capture"]')
        await self.page.click('[data-capture-dog="nino"]')
        note = 'Nouvelle note enregistrée avant le partage.'
        await self.page.fill('#observation', note)
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.click('.topbar [data-go="capture"]')
        draft = 'Brouillon privé à garder pendant la sélection.'
        await self.page.fill('#observation', draft)
        await self.open_route('dogs')
        await self.page.locator('[data-media-upload="nino"]').first.set_input_files({
            'name': 'nouvelle-photo.png', 'mimeType': 'image/png', 'buffer': png_fixture(),
        })
        await self.page.wait_for_function("DogCareAPI.getMedia().items.some(m => m.name === 'nouvelle-photo.png')")
        await self.open_route('invite')
        form = self.page.locator('#professional-form')
        await form.wait_for()
        with self.subTest(record='capture'):
            self.assertIn(note, await form.inner_text())
        with self.subTest(record='photo'):
            self.assertIn('nouvelle-photo.png', await form.inner_text())
        await form.locator('[name=dogIds][value=nino]').check()
        await form.locator('[name=email]').fill(self.professional_email)
        for label in (note, 'nouvelle-photo.png'):
            await form.locator('.professional-record').filter(has_text=label).locator('input').check()
        await form.locator('button.primary').click()
        await self.page.wait_for_function('!savePending && DogCareAPI.getPortal().professionals.length === 1')
        await form.wait_for()
        self.assertEqual(await self.page.evaluate('DogCareAPI.getPortal().professionals[0].recordKeys.length'), 2)
        await self.capture_widths('professional-new-records')
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.input_value('#observation'), draft)
        self.assertEqual(self.console_errors, [])

    async def test_selection_refresh_failure_and_late_completion_preserve_drafts(self):
        await self.page.click('.topbar [data-go="capture"]')
        draft = 'Brouillon gardé pendant le chargement.'
        await self.page.fill('#observation', draft)
        entered, release = asyncio.Event(), asyncio.Event()
        self.addCleanup(release.set)
        attempts = 0

        async def refresh(route):
            nonlocal attempts
            attempts += 1
            response = await route.fetch()
            payload = await response.json()
            if attempts != 2:
                entered.set()
                await release.wait()
            if attempts == 1:
                payload['revision'] += 1
            await route.fulfill(response=response, json=payload)

        await self.page.route('**/api/state', refresh)
        await self.open_route('invite')
        await asyncio.wait_for(entered.wait(), 5)
        self.assertEqual(await self.page.locator('#professional-form').count(), 0)
        member_email = self.page.locator('#member-form [name=email]')
        await member_email.fill('pending-family@example.com')
        release.set()
        await self.page.locator('#professional-access [role=alert]').wait_for()
        self.assertEqual(await member_email.input_value(), 'pending-family@example.com')
        await self.page.locator('#professional-access button').click()
        await self.page.locator('#professional-form').wait_for()
        self.assertEqual(await member_email.input_value(), 'pending-family@example.com')
        await self.page.click('.topbar [data-go="capture"]')
        self.assertEqual(await self.page.input_value('#observation'), draft)
        entered.clear(); release.clear()
        await self.open_route('invite')
        await asyncio.wait_for(entered.wait(), 5)
        await self.page.click('.topbar [data-go="capture"]')
        release.set()
        await self.page.evaluate('DogCareAPI.whenSaved()')
        self.assertEqual(await self.page.locator('#professional-form').count(), 0)
        self.assertEqual(await self.page.input_value('#observation'), draft)
        self.assertEqual(self.console_errors, [])

    async def test_shared_content_stays_literal_in_french(self):
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        state['daily']['dogs'][0]['name'] = 'Food'
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': state['daily']}, cookie=self.sid)[0], 200)
        notes = {'nino': [{'id': 1, 'title': 'Food', 'text': 'Food', 'date': '2026-10-08'}]}
        self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': notes}, cookie=self.sid)[0], 200)
        status, media = upload_raw(self.port, self.sid, png_fixture(), headers={'X-DogCare-Filename': 'Food'})
        self.assertEqual(status, 200)
        media_key = 'media:' + media['uploadedId']
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        key = next(r['key'] for r in state['portal']['shareCatalog'] if r['kind'] == 'note')
        self.assertEqual(_http(self.port, 'POST', '/api/portal/professionals', {
            'email': self.professional_email, 'dogIds': ['nino'], 'recordKeys': [key, media_key],
        }, cookie=self.sid)[0], 200)
        await self.page.reload(); await self.wait_ready(); await self.open_route('invite')
        form = self.page.locator('#professional-form')
        await form.wait_for()
        with self.subTest(view='owner dog'):
            self.assertEqual((await form.locator('legend label').first.inner_text()).strip(), 'Food')
        with self.subTest(view='owner label'):
            self.assertEqual(await form.locator('.professional-record > span').first.evaluate('(e) => e.firstChild.textContent'), 'Food')
        with self.subTest(view='owner media label'):
            record = form.locator('.professional-record').filter(has=self.page.locator(f'[value="{media_key}"]'))
            self.assertEqual((await record.inner_text()).splitlines(), ['Food', 'Photos et vidéos'])
        await self.page.locator('.professional-members summary').click()
        with self.subTest(view='saved version'):
            self.assertEqual((await self.page.locator('.professional-members .portal-message').first.inner_text()).split(), ['Food', 'Food'])
            self.assertEqual((await self.page.locator('.professional-members .portal-message').last.inner_text()).split(), ['Food', 'Consulter'])
        self.assertEqual(await self.page.locator('.professional-members summary').inner_text(), 'Version partagée')
        await self.context.clear_cookies()
        self.assertEqual(_http(self.port, 'POST', '/api/auth/access', {'email': self.professional_email})[0], 200)
        await self.page.goto(_latest_link(self.outbox, self.professional_email))
        await self.page.wait_for_selector('.professional-dog')
        for selector in ('h2', 'h3', '.portal-message'):
            with self.subTest(view='professional', field=selector):
                self.assertEqual(await self.page.locator('.professional-dog ' + selector).all_text_contents(), ['Food'] * (2 if selector == 'h3' else 1))
        self.assertEqual(await self.page.locator('#page-title').inner_text(), 'Dossiers partagés')
        self.assertEqual(await self.page.locator('.professional-dog a[download]').inner_text(), 'Télécharger')
        await self.capture_widths('professional-literal-records')
        self.assertEqual(self.console_errors, [])

    async def test_owner_selection_professional_login_and_revocation(self):
        await self.open_route('invite')
        form = self.page.locator('#professional-form')
        await form.locator('[name=email]').fill(self.professional_email)
        self.assertTrue(await form.locator('[name=recordKeys]').first.is_disabled())
        await form.locator('[name=dogIds][value=nino]').check()
        await form.locator('[name=recordKeys][value^="note:nino:1:"]').check()
        await form.locator(f'[name=recordKeys][value="media:{self.media_id}"]').check()
        await form.locator('button.primary').click()
        await self.page.wait_for_function('!savePending && DogCareAPI.getPortal().professionals.length === 1')
        await self.page.reload(); await self.wait_ready(); await self.open_route('invite')
        await self.page.locator('[data-edit-professional]').click()
        self.assertTrue(await form.locator('[name=dogIds][value=nino]').is_checked())
        self.assertFalse(await form.locator('[name=dogIds][value=pablo]').is_checked())
        self.assertEqual(await form.locator('[name=recordKeys]:checked').count(), 2)
        await self.page.locator('.professional-members summary').click()
        self.assertIn('Nino a marché', await self.page.locator('.professional-members').inner_text())
        await self.capture_widths('professional-owner-selection')
        _, owner, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        member_id = owner['portal']['professionals'][0]['id']
        # The invitee requests their own link. Isolated development outbox only.
        await self.context.clear_cookies()
        await self.page.goto(self.url)
        self.assertEqual(_http(self.port, 'POST', '/api/auth/access', {'email': self.professional_email})[0], 200)
        await self.page.goto(_latest_link(self.outbox, self.professional_email))
        await self.page.wait_for_selector('.professional-dog')
        body = await self.page.locator('body').inner_text()
        for absent in ('Pablo', 'Note interne', 'Private family', 'Rappel privé', 'Comptabilité'):
            self.assertNotIn(absent, body)
        self.assertIn('Nino a marché tranquillement', body)
        self.assertFalse(await self.page.locator('#workspace-tools').is_visible())
        self.assertEqual(await self.page.locator('#main-nav button:visible').count(), 1)
        self.assertEqual(await self.page.locator('#app-content input[type=file]').count(), 0)
        await self.page.wait_for_function("document.querySelector('.professional-media').naturalWidth > 0")
        await self.capture_widths('professional-selected-records')
        await self.page.reload()
        await self.page.wait_for_selector('.professional-dog')
        self.assertEqual(_http(self.port, 'POST', '/api/portal/revoke', {'userId': member_id}, cookie=self.sid)[0], 200)
        await self.page.reload()
        await self.page.wait_for_selector('#public-welcome')
        self.assertFalse(await self.page.locator('.professional-dog').count())
        self.assertEqual(self.console_errors, [])
