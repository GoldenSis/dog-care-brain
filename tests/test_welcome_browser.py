"""Public choices → real client request → owner quote, isolated synthetic accounts."""
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import _http, _latest_link


class WelcomeJourneyTest(BrowserFixture):
    async def asyncSetUp(self):
        prefix=uuid.uuid4().hex
        self.sid=self.login(prefix+'-owner@example.com')
        self.client_email=prefix+'-family@example.com'
        daily={'version':1,'clients':[{'id':'family','name':'Synthetic family'},{'id':'other','name':'Other synthetic family'}],
               'dogs':[{'id':'nino','name':'Nino','clientId':'family'},{'id':'pablo','name':'Private Pablo','clientId':'other'}],
               'bookings':[],'rates':{'currency':'CHF','day':None,'night':None,'walk':None},'documents':[]}
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':daily},cookie=self.sid)[0],200)
        self.assertEqual(_http(self.port,'POST','/api/portal/members',{'email':self.client_email,'role':'client','clientId':'family'},cookie=self.sid)[0],200)
        await super().asyncSetUp()
        await self.page.select_option('#language-picker','fr')
        await self.page.wait_for_function('!savePending')

    async def test_each_service_survives_signin_request_reload_and_owner_decision(self):
        await self.context.clear_cookies()
        await self.page.goto(self.url)
        await self.page.wait_for_selector('#public-welcome')
        api=[]
        self.page.on('request',lambda r:api.append(urlparse(r.url).path) if '/api/' in r.url else None)
        await self.page.evaluate('document.fonts.ready')
        self.assertTrue(await self.page.evaluate("Array.from(document.fonts).some(f=>f.family==='DM Sans' && f.status==='loaded')"))
        descriptions=[]
        for service in ('day','night','walk'):
            await self.page.click(f'[data-service="{service}"]')
            descriptions.append(await self.page.locator('#service-detail').inner_text())
            self.assertEqual(await self.page.get_attribute(f'[data-service="{service}"]','aria-pressed'),'true')
        self.assertEqual(len(set(descriptions)),3)
        self.assertIn('déjà accueillis',descriptions[2])
        self.assertFalse(any(path in api for path in ('/api/state','/api/daily','/api/finance')))
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'),width)
            await self.capture_evidence(f'welcome-services-{width}.png',full_page=False)
        for service in ('day','night','walk'):
            await self.page.click(f'[data-service="{service}"]')
            await self.page.click('[data-request]')
            await self.page.fill('#access-email',self.client_email)
            await self.page.click('#access-form button')
            await self.page.wait_for_function("document.querySelector('#access-result').textContent.includes('Aucun e-mail')")
            link=_latest_link(self.outbox,self.client_email)
            self.assertIn('service='+service,link)
            # A new tab has no sessionStorage: the personal link must retain intent.
            client=await self.context.new_page()
            await client.goto(link)
            await client.wait_for_selector('#client-request-form')
            self.assertEqual(await client.input_value('#client-request-form [name=service]'),service)
            self.assertNotIn('Private Pablo',await client.locator('body').inner_text())
            form=client.locator('#client-request-form')
            await form.locator('[name=start]').fill('2026-11-04')
            await form.locator('[name=end]').fill('2026-11-05' if service=='night' else '2026-11-04')
            await client.wait_for_selector('#request-estimate .quoted-total')
            self.assertIn('Total à convenir',await client.inner_text('#request-estimate'))
            await form.locator('[name=note]').fill('Synthetic '+service+' request')
            await form.locator('button').click()
            await client.wait_for_function('!savePending && DogCareAPI.getPortal().requests.length > 0')
            await client.reload()
            await client.wait_for_selector('#client-request-form')
            requests=await client.evaluate('DogCareAPI.getPortal().requests')
            saved=next(r for r in requests if r['service']==service)
            self.assertEqual(saved['status'],'requested')
            self.assertIn('À confirmer',await client.inner_text('#app-content'))
            self.assertEqual(await client.locator('[data-page=business]:visible').count(),0)
            self.assertEqual(await client.locator('[data-page=health]:visible').count(),0)
            await client.close()
            await self.context.clear_cookies()
            await self.page.goto(self.url)
            await self.page.wait_for_selector('#public-welcome')
        await self.context.add_cookies([{'name':'dc_s','value':self.sid,'url':self.url,'httpOnly':True}])
        await self.page.goto(self.url)
        await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-decision=accepted]').count(),3)
        ident=await self.page.locator('[data-decision=accepted]').first.get_attribute('data-request-id')
        await self.page.click(f'[data-request-id="{ident}"][data-decision=accepted]')
        await self.page.wait_for_function('!savePending && DogCareAPI.getDaily().bookings.length === 1')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(len(await self.page.evaluate('DogCareAPI.getDaily().bookings')),1)
        await self.capture_evidence('owner-real-requests.png',full_page=False)

    async def test_owner_extra_edit_reload_and_client_total(self):
        cookie=self.login(self.client_email)
        status,saved,_=_http(self.port,'POST','/api/portal/requests',{'dogId':'nino','service':'day','start':'2026-11-04','end':'2026-11-05','note':'Synthetic priced request'},cookie=cookie)
        self.assertEqual(status,200,saved)
        ident=saved['portal']['requests'][0]['id']
        await self.page.reload();await self.wait_ready()
        panel=self.page.locator(f'[data-quote="{ident}"]')
        await panel.locator('summary').click()
        # These amounts exist only in the isolated test, never in public preview rates.
        base=panel.locator('.base-price-form')
        await base.locator('[name=unitMinor]').fill('12,25')
        await base.locator('button').click()
        await self.page.wait_for_function('!savePending')
        await panel.locator('summary').click()
        extra=panel.locator('.extra-form')
        await extra.locator('[name=label]').fill('Synthetic optional pickup')
        await extra.locator('[name=unitMinor]').fill('2,50')
        await extra.locator('[name=quantity]').fill('2')
        await extra.locator('[name=reusable]').check()
        self.assertIn('5,00',await extra.locator('output').inner_text())
        await extra.locator('button').click();await self.page.wait_for_function('!savePending')
        await self.page.reload();await self.wait_ready()
        q=await self.page.evaluate('(id)=>DogCareAPI.getPortal().quotes[id]',ident)
        self.assertEqual(q['totalMinor'],2950)
        await panel.locator('summary').click()
        await panel.locator('[data-edit-extra]').click()
        await extra.locator('[name=quantity]').fill('3')
        await extra.locator('button').click();await self.page.wait_for_function('!savePending')
        self.assertEqual((await self.page.evaluate('(id)=>DogCareAPI.getPortal().quotes[id]',ident))['totalMinor'],3200)
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'),width)
            await self.page.wait_for_function("!document.querySelector('#toast').classList.contains('show')")
            if not await panel.locator('.extra-form').is_visible():
                await panel.locator('summary').click()
            if os.environ.get('DOGCARE_EVIDENCE_DIR'):
                await panel.locator('..').screenshot(path=str(Path(os.environ['DOGCARE_EVIDENCE_DIR'])/f'owner-real-extras-{width}.png'),animations='disabled')
        await self.page.click(f'[data-request-id="{ident}"][data-decision=accepted]')
        await self.page.wait_for_function('!savePending && DogCareAPI.getDaily().bookings.length === 1')
        await self.open_route('business')
        await self.page.click('#finance-new-sale')
        await self.page.click('#finance-booking')
        await self.page.select_option('#finance-booking + select',ident)
        self.assertEqual(await self.page.input_value('[name="unit-0"]'),'12.25')
        self.assertEqual(await self.page.input_value('[name="description-1"]'),'Synthetic optional pickup')
        self.assertEqual(await self.page.input_value('[name="quantity-1"]'),'3')
        self.assertIn('32,00',await self.page.inner_text('#finance-total'))
        await self.page.click('#finance-form button[value=draft]')
        await self.page.wait_for_function('!savePending')
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name':'dc_s','value':cookie,'url':self.url,'httpOnly':True}])
        await self.page.goto(self.url+'/?service=day');await self.wait_ready()
        self.assertIn('Synthetic optional pickup',await self.page.inner_text('#app-content'))
        self.assertIn('32,00',await self.page.inner_text('#app-content'))
        self.assertEqual(await self.page.locator('.extra-form').count(),0)
        self.assertIsNone(await self.page.evaluate('DogCareAPI.getFinance()'))
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'),width)
            if os.environ.get('DOGCARE_EVIDENCE_DIR'):
                await self.page.locator('.portal-card').last.screenshot(path=str(Path(os.environ['DOGCARE_EVIDENCE_DIR'])/f'client-real-quote-{width}.png'),animations='disabled')

    async def test_public_price_load_keeps_signin_draft_and_shows_real_configured_unit(self):
        import asyncio
        release=asyncio.Event()
        async def prices(route):
            await release.wait()
            await route.fulfill(json={'ok':True,'rates':{'day':1234,'night':None,'walk':0,'currency':'EUR'}})
        await self.context.clear_cookies()
        await self.page.route('**/api/public/services',prices)
        await self.page.goto(self.url)
        await self.page.wait_for_selector('[data-request]')
        await self.page.click('[data-request]')
        await self.page.fill('#access-email','draft@example.com')
        release.set()
        await self.page.wait_for_function("document.querySelector('#service-detail strong').textContent.includes('12,34')")
        self.assertEqual(await self.page.input_value('#access-email'),'draft@example.com')
        self.assertTrue(await self.page.locator('.welcome-dialog').is_visible())
        await self.page.click('.welcome-close')
        self.assertIn('par journée',await self.page.inner_text('#service-detail'))
        await self.page.click('[data-service=walk]')
        self.assertIn('0,00',await self.page.inner_text('#service-detail'))
        self.assertIn('par balade',await self.page.inner_text('#service-detail'))
        await self.page.click('[data-service=night]')
        self.assertIn('Tarif à convenir',await self.page.inner_text('#service-detail'))

    async def test_uninvited_visitor_has_truthful_contact_route_without_account_or_message(self):
        await self.context.clear_cookies()
        await self.context.grant_permissions(['clipboard-read','clipboard-write'])
        await self.page.goto(self.url)
        await self.page.wait_for_selector('[data-service=night]')
        self.assertEqual((await self.context.request.get(self.url+'/app.js')).status,401)
        self.assertEqual(await self.page.locator('[data-page=business]').count(),0)
        await self.page.click('[data-service=night]')
        await self.page.click('[data-request]')
        self.assertTrue(await self.page.locator('.first-contact').evaluate('(e)=>e.open'))
        self.assertIn('Une nuit',await self.page.input_value('#contact-draft'))
        self.assertEqual(await self.page.locator('.first-contact a').get_attribute('href'),'https://www.instagram.com/bus_destoutous/')
        await self.page.click('#copy-contact')
        self.assertEqual(await self.page.evaluate('navigator.clipboard.readText()'),await self.page.input_value('#contact-draft'))
        self.assertIn('Message copié',await self.page.inner_text('#contact-result'))
        unknown='uninvited-'+uuid.uuid4().hex+'@example.com'
        with self.server_mod.connection() as connection:
            before=connection.execute('SELECT count(*) FROM user').fetchone()[0]
            tokens=connection.execute('SELECT count(*) FROM magic').fetchone()[0]
        # Isolated SMTP configuration boundary; no external transport is invoked.
        with patch('login_delivery.configuration',return_value={'mode':'smtp','origin':'https://dogs.example.com'}),patch('login_delivery.send') as send:
            await self.page.fill('#access-email',unknown)
            await self.page.click('#access-form button')
            await self.page.wait_for_function("document.querySelector('#access-result').textContent.includes('Si votre accès est enregistré')")
            self.assertNotIn('a été envoyé',await self.page.inner_text('#access-result'))
            send.assert_not_called()
        with self.server_mod.connection() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM user').fetchone()[0],before)
            self.assertEqual(connection.execute('SELECT count(*) FROM magic').fetchone()[0],tokens)
        self.assertFalse(list(Path(self.outbox).glob('*'+unknown+'*')))
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'),width)
            await self.page.locator('.welcome-dialog').evaluate('(e)=>e.scrollTop=0')
            await self.capture_evidence(f'first-visit-contact-{width}.png',full_page=False)
        self.assertEqual(self.console_errors,[])

    async def test_muse_uses_registered_dogs_and_saved_planning_and_phone_tabs_fit(self):
        await self.open_route('assistant')
        briefing=await self.page.inner_text('#assistant-thread')
        self.assertIn('Nino',briefing)
        self.assertIn('Private Pablo',briefing)
        self.assertNotIn('12 h 30',briefing)
        self.assertIn('0 réservation',briefing)
        daily=await self.page.evaluate('DogCareAPI.getDaily()')
        today=await self.page.evaluate('localDay()')
        daily['bookings']=[{'id':'today-real','dogId':'nino','service':'day','start':today,'end':today,'unitMinor':None,'currency':'CHF'}]
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':daily},cookie=self.sid)[0],200)
        await self.page.reload();await self.wait_ready();await self.open_route('assistant')
        self.assertIn('1 réservation',await self.page.inner_text('#assistant-thread'))
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            await self.capture_evidence(f'muse-real-records-{width}.png',full_page=False)
        await self.open_route('business')
        for button in await self.page.locator('.finance-tabs button').all():
            box=await button.bounding_box()
            self.assertLessEqual(box['x']+box['width'],390)
        await self.capture_evidence('accounting-wrapped-tabs-390.png',full_page=False)
        response=await self.context.request.get(self.url+'/app.js')
        source=await response.text()
        for residue in ('Arnaud Chrétien','+41223615540','Clinique Artémis','Evening medication','Joint supplement'):
            self.assertNotIn(residue,source)

    async def test_new_empty_owner_opens_in_french_without_sample_story(self):
        email='empty-'+uuid.uuid4().hex+'@example.com'
        with patch.dict(os.environ,{'DC_ALLOW_DEMO_SIGNUP':'0'}):
            with self.server_mod.connection() as connection:
                self.server_mod.ensure_account(connection,email)
            cookie=self.login(email)
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name':'dc_s','value':cookie,'url':self.url,'httpOnly':True}])
        await self.page.goto(self.url)
        await self.wait_ready()
        self.assertEqual(await self.page.input_value('#language-picker'),'fr')
        self.assertNotIn('Billie',await self.page.inner_text('#app-content'))
        await self.open_route('settings')
        self.assertEqual(await self.page.locator('#reset-demo').count(),0)
        self.assertNotIn('démonstration',await self.page.inner_text('#app-content'))
        await self.open_route('invite')
        self.assertEqual(await self.page.locator('#create-invite').count(),0)
        self.assertEqual(await self.page.locator('#member-form').count(),1)
        await self.open_route('assistant')
        self.assertIn('Aucun chien enregistré',await self.page.inner_text('#assistant-thread'))
        self.assertNotIn('Billie',await self.page.inner_text('#assistant-thread'))
        self.assertNotIn('12 h 30',await self.page.inner_text('#assistant-thread'))
        await self.page.select_option('#language-picker','it')
        await self.page.wait_for_function('!savePending')
        await self.page.reload();await self.wait_ready()
        self.assertEqual(await self.page.input_value('#language-picker'),'it')

    async def test_owner_grants_family_access_in_ui_and_client_opens_own_dogs(self):
        email='granted-'+uuid.uuid4().hex+'@example.com'
        await self.open_route('invite')
        self.assertEqual(await self.page.locator('#create-invite').count(),0)
        await self.page.fill('#member-form [name=email]',email)
        await self.page.select_option('#member-form [name=clientId]','family')
        await self.page.click('#member-form button')
        await self.page.wait_for_function('(email)=>!savePending && DogCareAPI.getPortal().members.some(m=>m.email===email)',arg=email)
        await self.page.reload();await self.wait_ready();await self.open_route('invite')
        self.assertIn(email,await self.page.inner_text('#member-list'))
        for width in (1440,390):
            await self.page.set_viewport_size({'width':width,'height':900})
            await self.capture_evidence(f'owner-real-access-{width}.png',full_page=True)
        await self.open_route('settings')
        self.assertEqual(await self.page.locator('#reset-demo').count(),0)
        await self.capture_evidence('owner-real-settings-390.png',full_page=False)
        await self.context.clear_cookies()
        await self.page.goto(self.url+'/?service=walk')
        await self.page.click('[data-request]')
        await self.page.fill('#access-email',email)
        await self.page.click('#access-form button')
        await self.page.wait_for_function("document.querySelector('#access-result').textContent.includes('Aucun e-mail')")
        await self.page.goto(_latest_link(self.outbox,email))
        await self.page.wait_for_selector('#client-request-form')
        self.assertEqual(await self.page.input_value('#client-request-form [name=service]'),'walk')
        self.assertEqual(await self.page.locator('#client-request-form [name=dogId] option').all_text_contents(),['Nino'])
        self.assertNotIn('Private Pablo',await self.page.inner_text('#app-content'))
