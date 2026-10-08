"""Owner chooses individual records; a professional sees only that selection."""
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
