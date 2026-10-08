"""Real accounts retain actual dogs without manufacturing demo records."""
import uuid
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import ApiServerTestCase, _http


def empty_owner(fixture):
    email = uuid.uuid4().hex + '-empty@example.com'
    with patch.dict('os.environ', {'DC_ALLOW_DEMO_SIGNUP': '0'}):
        with fixture.server_mod.connection() as connection:
            fixture.server_mod.ensure_account(connection, email)
    return fixture.login(email)


class ObservationRegistryTest(ApiServerTestCase):
    def test_empty_unknown_observation_keys_never_create_dogs(self):
        cookie = empty_owner(self)
        _, registered, _ = _http(self.port, 'POST', '/api/dogs',
                                  {'slug': 'registered', 'name': 'Actual registered dog'}, cookie=cookie)
        self.assertTrue(registered['ok'])
        notes = {'billie': [], 'charlie': [], 'registered': [],
                 'legacy-dog': [{'id': 123, 'text': 'Actual saved legacy note'}]}
        status, saved, _ = _http(self.port, 'PUT', '/api/observations', {'observations': notes}, cookie=cookie)
        self.assertEqual(status, 200, saved)
        self.assertEqual({dog['slug'] for dog in saved['dogs']}, {'registered', 'legacy-dog'})
        self.assertEqual(saved['observations']['registered'], [])
        self.assertEqual(saved['observations']['legacy-dog'][0]['text'], 'Actual saved legacy note')


class AccountRegistryJourneyTest(BrowserFixture):
    async def test_empty_account_registration_note_reload_and_muse_have_only_actual_dog(self):
        self.sid = empty_owner(self)
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name': 'dc_s', 'value': self.sid, 'url': self.url, 'httpOnly': True}])
        await self.page.goto(self.url)
        await self.wait_ready()
        self.assertEqual(await self.page.evaluate('Object.keys(dogs)'), [])
        await self.open_route('dogs')
        await self.page.click('#new-dog')
        await self.page.fill('#dog-form [name=dogName]', 'Audit Pup')
        await self.page.select_option('#dog-form [name=clientId]', ':new')
        await self.page.fill('#dog-form [name=clientName]', 'Synthetic audit family')
        await self.page.click('#dog-form button[type=submit]')
        await self.page.wait_for_function('!savePending && DogCareAPI.getDaily().dogs.length === 1')
        dog_id = await self.page.evaluate('DogCareAPI.getDaily().dogs[0].id')
        await self.open_route('capture')
        await self.page.fill('#observation', 'Audit Pup enjoyed a quiet walk.')
        await self.page.click('#save-observation')
        await self.page.wait_for_selector('.timeline-card')
        await self.page.reload()
        await self.wait_ready()
        actual = await self.page.evaluate('({dogs:DogCareAPI.getDogs(), observations:DogCareAPI.getObservations(), profiles:Object.keys(dogs)})')
        self.assertEqual([dog['slug'] for dog in actual['dogs']], [dog_id])
        self.assertEqual(actual['profiles'], [dog_id])
        self.assertEqual(list(actual['observations']), [dog_id])
        self.assertEqual(len(actual['observations'][dog_id]), 1)
        await self.open_route('assistant')
        briefing = await self.page.locator('#assistant-thread').inner_text()
        self.assertIn('Audit Pup : 1', briefing)
        self.assertNotIn('Billie', briefing)
        self.assertNotIn('Charlie', briefing)
        for width in (1440, 390):
            await self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
            await self.capture_evidence(f'actual-account-muse-{width}.png')
        self.assertEqual(self.console_errors, [])
