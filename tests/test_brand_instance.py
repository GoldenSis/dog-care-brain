"""A second instance carries its own brand; the default stays Le Bus des Toutous."""
import base64
import os
from pathlib import Path
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import _http

ROOT = Path(__file__).resolve().parents[1]
NICOLAS = {'DC_BRAND_NAME': 'nicolasdelalaissedogcare', 'DC_BRAND_OWNER': 'Nicolas',
           'DC_BRAND_INSTAGRAM': 'nicolasdelalaisse', 'DC_BRAND_MARK': 'sun',
           'DC_BRAND_PRIMARY': '#F6B40E', 'DC_BRAND_DARK': '#85340A', 'DC_BRAND_SECONDARY': '#74ACDF'}
# The shipped La Laisse configuration: short header, dog mark and per-instance content file.
LALAISSE = {'DC_BRAND_NAME': 'La Laisse Dog Walker', 'DC_BRAND_SHORT': 'La Laisse', 'DC_BRAND_OWNER': 'Nicolás',
            'DC_BRAND_TAGLINE': 'Promenades canines · Batignolles · depuis 2011', 'DC_BRAND_INSTAGRAM': 'lalaisse.dogwalker',
            'DC_BRAND_MARK': 'dog', 'DC_BRAND_CONTENT': str(ROOT / 'deploy/dogcare-nicolas.content.json'),
            'DC_BRAND_PRIMARY': '#F6B40E', 'DC_BRAND_DARK': '#1A1A1A', 'DC_BRAND_SECONDARY': '#1A1A1A'}


class BrandInstanceTest(BrowserFixture):
    async def test_handoff_keeps_saved_dog_name(self):
        with patch.dict(os.environ, NICOLAS):
            await self.page.reload()
            await self.wait_ready()
            await self.open_route('dogs')
            await self.page.click('#new-dog')
            name = 'Adine-Sophie & @bus_destoutous'
            await self.page.fill('#dog-form [name="dogName"]', name)
            await self.page.click('#dog-form [type="submit"]')
            await self.page.wait_for_selector('#dog-form', state='detached')
            await self.open_route('handoff')
            await self.page.click('[data-audience="owner"]')
            self.assertEqual(await self.page.locator('#page-title').text_content(), name + ' · Owner')
            self.assertEqual(self.console_errors, [])
            self.assertEqual(self.page_errors, [])

    async def test_records_keep_translation_without_rebranding(self):
        with patch.dict(os.environ, NICOLAS):
            await self.page.reload()
            await self.wait_ready()
            note = 'Adine-Sophie administered medication at Le Bus des Toutous. @bus_destoutous'
            await self.open_route('capture')
            await self.page.fill('#observation', note)
            await self.page.click('#save-observation')
            await self.page.wait_for_function("state.page === 'dogs' && !savePending")
            self.assertEqual(await self.page.locator('.timeline-card > p').first.text_content(), note)
            notes = ['Hello, Adine-Sophie.', 'All good', note]
            self.assertTrue(await self.page.evaluate('''async notes => {
                const records = notes.map((text, i) => ({
                    id: Date.now() + i, date: localDay(), time: '12:00',
                    title: text, text, tags: [['Nutrition'], ['Activity'], ['Adine-Sophie']][i]
                }));
                return saveObservations({...state.observations, [state.dog]: records});
            }''', notes))
            await self.page.reload()
            await self.wait_ready()
            for locale in ('en', 'fr', 'it', 'de', 'es'):
                with self.subTest(locale=locale):
                    await self.page.select_option('#language-picker', locale)
                    await self.page.wait_for_function('!savePending')
                    displayed = await self.page.evaluate('notes => notes.map(text => translations[state.language]?.[text] || text)', notes)
                    await self.open_route('dashboard')
                    self.assertEqual(await self.page.locator('.activity-preview').text_content(), displayed[0])
                    self.assertEqual(await self.page.locator('.activity-copy strong').first.text_content(), displayed[0])
                    await self.open_route('dogs')
                    self.assertEqual(await self.page.locator('.timeline-card > p').all_text_contents(), displayed)
                    self.assertEqual(await self.page.locator('.timeline-top h4').all_text_contents(), displayed)
                    self.assertEqual(await self.page.locator('.timeline-card .mini-tags').last.text_content(), 'Adine-Sophie')
                    self.assertEqual(await self.page.evaluate('state.observations[state.dog].map(o => shareText(o).split("\\n\\n")[1])'), displayed)
                    await self.open_route('handoff')
                    highlights = await self.page.locator('.highlight-list').text_content()
                    for text in displayed:
                        self.assertIn(text, highlights)
                    self.assertEqual(await self.page.locator('.evidence-row small').all_text_contents(), displayed)
                    self.assertEqual(await self.page.locator('.evidence-row strong').all_text_contents(), displayed)
                    await self.open_route('story')
                    self.assertEqual((await self.page.locator('.story-copy').text_content()).strip(), displayed[0])
                    self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            self.assertEqual(await self.page.evaluate('state.observations[state.dog].map(o => o.text)'), notes)
            self.assertEqual(await self.page.evaluate('state.observations[state.dog].map(o => o.title)'), notes)
            self.assertEqual(self.console_errors, [])
            self.assertEqual(self.page_errors, [])

    async def test_generated_titles_localize_without_changing_saved_titles(self):
        for brand in ({key: '' for key in NICOLAS}, NICOLAS):
            with self.subTest(brand=brand['DC_BRAND_NAME']), patch.dict(os.environ, brand):
                await self.page.reload()
                await self.wait_ready()
                await self.page.select_option('#language-picker', 'fr')
                await self.page.wait_for_function('!savePending')
                await self.open_route('capture')
                await self.page.fill('#observation', 'Une belle journée.')
                await self.page.click('#save-observation')
                await self.page.wait_for_function("state.page === 'dogs' && !savePending")
                self.assertEqual(await self.page.locator('.timeline-top h4').first.text_content(), 'Moment du quotidien')
                await self.page.reload()
                await self.wait_ready()
                for locale, title in (('en', 'Care moment'), ('fr', 'Moment du quotidien'),
                                      ('it', 'Momento di cura'), ('de', 'Pflegemoment'), ('es', 'Momento de cuidado')):
                    with self.subTest(locale=locale):
                        await self.page.select_option('#language-picker', locale)
                        await self.page.wait_for_function('!savePending')
                        await self.open_route('dashboard')
                        self.assertEqual(await self.page.locator('.activity-copy strong').first.text_content(), title)
                        await self.open_route('dogs')
                        self.assertEqual(await self.page.locator('.timeline-top h4').first.text_content(), title)
                        await self.open_route('handoff')
                        self.assertEqual(await self.page.locator('.evidence-row strong').first.text_content(), title)
                        self.assertEqual(await self.page.evaluate('state.observations[state.dog][0].title'), 'Care moment')
                        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertEqual(self.console_errors, [])
                self.assertEqual(self.page_errors, [])

    async def test_assistant_heading_uses_owner_in_every_locale(self):
        with patch.dict(os.environ, NICOLAS):
            await self.page.reload()
            await self.wait_ready()
            await self.open_route('assistant')
            for locale, prefix in (('en', 'FOR'), ('fr', 'POUR'), ('it', 'PER'), ('de', 'FÜR'), ('es', 'PARA')):
                with self.subTest(locale=locale):
                    await self.page.select_option('#language-picker', locale)
                    await self.page.wait_for_function('!savePending')
                    self.assertEqual(await self.page.locator('.muse-kicker').text_content(), f'MUSE {prefix} NICOLAS')
                    copy = await self.page.evaluate('''() => JSON.stringify([
                        [...new Set(Object.values(translations).flatMap(copy => Object.keys(copy)))].map(key => t(key)),
                        assistantCopy[state.language], PortalCopy[state.language],
                        DailyCopy[state.language], FinanceCopy[state.language],
                        MediaCopy[state.language], KnowledgeCopy[state.language], BaladesCopy[state.language]
                    ])''')
                    self.assertNotRegex(copy, '(?i)adine|bus_destoutous')
                    self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                    await self.page.click('#public-home')
                    self.assertNotRegex(await self.page.locator('#public-welcome').inner_text(), '(?i)adine|bus_destoutous')
                    await self.page.evaluate('navigate("assistant")')
            self.assertEqual(self.console_errors, [])
            self.assertEqual(self.page_errors, [])

    async def test_assistant_owner_fallback_and_html_characters(self):
        for owner in ('', 'Nicolas <&> $&'):
            with self.subTest(owner=owner), patch.dict(os.environ, {**NICOLAS, 'DC_BRAND_OWNER': owner}):
                await self.page.reload()
                await self.wait_ready()
                await self.open_route('assistant')
                expected = owner or NICOLAS['DC_BRAND_NAME']
                self.assertEqual(await self.page.locator('.muse-kicker').text_content(), 'MUSE FOR ' + expected.upper())
                self.assertEqual(await self.page.evaluate('assistantText().heroHeading'), f'Good morning, {expected}.')
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    async def test_default_brand_is_served_unchanged(self):
        with patch.dict(os.environ, {}):
            for name in NICOLAS:
                os.environ.pop(name, None)
            await self._default_unchanged()

    async def _default_unchanged(self):
        for path in ('/welcome.css', '/workspace.css', '/welcome.js', '/app.js'):
            with self.subTest(path=path):
                self.assertEqual(_raw(self.port, path, self.sid), (ROOT / path[1:]).read_bytes())
        html = _raw(self.port, '/', self.sid).decode()
        self.assertNotIn('DOGCARE_BRAND', html)
        self.assertIn('<title>Le Bus des Toutous — Muse</title>', html)
        self.assertEqual(_raw(self.port, '/assets/photos/good-company.jpg', self.sid)[:2], b'\xff\xd8')
        await self.page.reload(); await self.wait_ready()
        await self.capture_evidence('brand-default-dashboard-390.png')
        await self.context.clear_cookies(); await self.page.goto(self.url); await self.page.wait_for_selector('#public-welcome')
        await self.capture_evidence('brand-default-public-390.png')

    async def test_custom_brand_hides_adine_gallery_and_photos(self):
        with patch.dict(os.environ, NICOLAS):
            seen = []
            self.page.on('request', lambda r: seen.append(r.url) if '/assets/photos/' in r.url or '/assets/films/' in r.url else None)
            await self.page.reload(); await self.wait_ready()
            self.assertEqual(await self.page.title(), 'nicolasdelalaissedogcare — Muse')
            await self.capture_evidence('brand-nicolas-dashboard-390.png')
            await self.open_route('gallery')
            await self.capture_evidence('brand-nicolas-gallery-390.png')
            self.assertEqual(await self.page.locator('.journal-film, .club-journal, video.day-film').count(), 0)
            text = await self.page.locator('body').inner_text()
            await self.context.clear_cookies(); await self.page.goto(self.url); await self.page.wait_for_selector('#public-welcome')
            await self.capture_evidence('brand-nicolas-public-390.png')
            text += await self.page.locator('body').inner_text() + await self.page.content()
            for private in ('Adine', 'Bus des Toutous', 'bus_destoutous'):
                self.assertNotIn(private, text)
            self.assertIn('nicolasdelalaisse', text)
            self.assertEqual(seen, [])
            self.assertEqual(_http(self.port, 'GET', '/assets/films/a-day-with-adine.mp4')[0], 404)
            self.assertEqual(await self.page.evaluate("getComputedStyle(document.querySelector('#public-welcome .primary')).backgroundColor"), 'rgb(246, 180, 14)')
            self.assertEqual(self.page_errors, [])

    async def test_instance_content_drives_welcome_contact_and_requests(self):
        with patch.dict(os.environ, LALAISSE):
            os.environ.pop('DC_BRAND_LOGO', None)
            await self.page.reload(); await self.wait_ready()
            self.assertEqual(await self.page.title(), 'La Laisse Dog Walker — Muse')
            self.assertEqual((await self.page.locator('.utility-brand').inner_text()).strip(), 'La Laisse')
            self.assertEqual(await self.page.locator('.workspace-mark path[fill-rule]').count(), 1)
            self.assertEqual(_http(self.port, 'GET', '/brand/logo')[0], 404)
            await self.open_route('gallery')
            self.assertIn('add them to each dog', await self.page.locator('.page-title-row p').inner_text())
            await self.context.clear_cookies(); await self.page.goto(self.url); await self.page.wait_for_selector('#public-welcome')
            welcome = self.page.locator('#public-welcome')
            brand = self.page.locator('.welcome-brand')
            self.assertEqual((await brand.inner_text()).strip(), 'La Laisse')
            self.assertLess((await brand.bounding_box())['height'], 45)
            self.assertEqual(await self.page.locator('.welcome-choices strong').all_text_contents(),
                             ['Balade en meute en forêt', 'Promenade en ville', 'Je viens chercher et je ramène votre chien chez vous'])
            for key in ('walk', 'city', 'pickup'):
                await self.page.click(f'[data-service="{key}"]')
                self.assertEqual(await self.page.locator('#service-detail strong').inner_text(), 'Tarif à convenir')
            text = await welcome.inner_text()
            self.assertIn('Paris 17e, Neuilly et Levallois-Perret', text)
            self.assertIn('Patagonie argentine', text)
            self.assertNotRegex(text, r'(?i)adine|bus_destoutous|12[,.]00|€')
            self.assertEqual(await self.page.get_attribute('#welcome-contact a[href^="tel:"]', 'href'), 'tel:0602144876')
            self.assertEqual(await self.page.get_attribute('#welcome-contact a[href*="instagram"]', 'href'), 'https://www.instagram.com/lalaisse.dogwalker/')
            self.assertEqual(await self.page.get_attribute('#welcome-contact a[href^="https://g.page"]', 'href'), 'https://g.page/r/Cbnwe0jE8JgEEBM/review')
            self.assertEqual(await self.page.get_attribute('#welcome-contact a[href^="mailto:"]', 'href'), 'mailto:contact@lalaisse.dog')
            self.assertIn('Dibaq Sense', await self.page.locator('.welcome-shop').inner_text())
            self.assertEqual(await self.page.get_attribute('.welcome-header nav a[href="#welcome-contact"]', 'href'), '#welcome-contact')
            await self.page.click('[data-request]')
            self.assertEqual(await self.page.evaluate("sessionStorage.getItem('dogcare-request-service')"), 'walk')
            self.assertIn('Je viens chercher', await self.page.locator('#contact-draft').input_value())
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            self.assertEqual(await self.page.evaluate("getComputedStyle(document.querySelector('#public-welcome .primary')).color"), 'rgb(26, 26, 26)')
            self.assertEqual(self.console_errors, [])

    async def test_logo_file_replaces_mark_and_bad_content_falls_back(self):
        logo = Path(self.tmp) / 'logo.png'
        logo.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))
        broken = Path(self.tmp) / 'broken.json'
        broken.write_text('{"services": [{"id": "x", "label": "Nuit", "request": "sleepover"}], "contact": {"phone": "<b>", "email": "a@b", "reviews": "javascript:alert(1)"}}')
        with patch.dict(os.environ, {**LALAISSE, 'DC_BRAND_LOGO': str(logo), 'DC_BRAND_CONTENT': str(broken)}):
            self.assertEqual(_raw(self.port, '/brand/logo', self.sid), logo.read_bytes())
            await self.context.clear_cookies(); await self.page.goto(self.url); await self.page.wait_for_selector('#public-welcome')
            self.assertEqual(await self.page.get_attribute('.welcome-brand img', 'src'), '/brand/logo')
            self.assertEqual(await self.page.locator('[data-service]').evaluate_all('b => b.map(x => x.dataset.service)'), ['day', 'night', 'walk'])
            self.assertEqual(await self.page.locator('#welcome-contact').count(), 0)
        with patch.dict(os.environ, {'DC_BRAND_NAME': '', 'DC_BRAND_LOGO': str(logo)}):
            self.assertEqual(_http(self.port, 'GET', '/brand/logo')[0], 404)


def _raw(port, path, cookie):
    import http.client
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    connection.request('GET', path, headers={'Cookie': 'dc_s=' + cookie})
    return connection.getresponse().read()
