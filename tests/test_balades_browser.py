"""Balades on a phone: record with mocked GPS, a tolerated spot, reload, GPX import/export, Planning link."""
import threading
import unittest
from functools import partial
from pathlib import Path

from tests.test_browser_acceptance import ROOT, BrowserFixture, QuietStaticHandler

STYLE = '{"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#efe9dc"}}]}'
GPX = b'''<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
<metadata><name>Boucle des Etangs</name></metadata><wpt lat="48.8031" lon="2.1201"><name>Point d'eau</name></wpt>
<trk><trkseg><trkpt lat="48.8030" lon="2.1200"><time>2026-10-20T08:00:00Z</time></trkpt><trkpt lat="48.8040" lon="2.1210"><time>2026-10-20T08:20:00Z</time></trkpt>
<trkpt lat="48.8050" lon="2.1230"><time>2026-10-20T08:45:00Z</time></trkpt></trkseg></trk></gpx>'''


class BaladesBrowserTest(BrowserFixture):
    launch_args = ('--use-angle=swiftshader', '--enable-unsafe-swiftshader')

    async def no_overflow(self):
        self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), 390)

    async def test_record_spot_reload_import_export_and_link_on_phone(self):
        page = self.page
        await self.context.route('https://tiles.openfreemap.org/**', lambda route: route.fulfill(
            status=200, content_type='application/json', body=STYLE))
        await self.context.grant_permissions(['geolocation'], origin=self.url)
        await self.context.set_geolocation({'latitude': 48.8400, 'longitude': 2.2200, 'accuracy': 5})
        await page.select_option('#language-picker', 'fr')
        await page.wait_for_function("document.documentElement.lang === 'fr' && !savePending")

        # Record a short walk: three fixes about 55 m apart.
        await self.open_route('balades')
        await page.click('[data-b="record"]')
        await page.wait_for_function("document.querySelector('#rec-points')?.textContent === '1'")
        for count, lat in ((2, 48.8405), (3, 48.8410)):
            await self.context.set_geolocation({'latitude': lat, 'longitude': 2.2200, 'accuracy': 5})
            await page.wait_for_function(f"document.querySelector('#rec-points')?.textContent === '{count}'")
        self.assertIn('Gardez l’écran allumé', await page.locator('.balades-warning').text_content())
        await page.wait_for_selector('#balades-map canvas')
        await self.no_overflow()
        await self.capture_evidence(f'balades-recording-{self.api_mode}.png')
        await page.click('[data-b="finish"]')
        await page.fill('#track-form [name=name]', 'Parc de Saint-Cloud')
        await page.locator('#track-form [name=dog]').first.check()
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Parc de Saint-Cloud")')

        # Tap the map to place a tolerated spot with its official rule.
        await page.click('[data-b="add-spot"]')
        box = await page.locator('#balades-map').bounding_box()
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        await page.click('label.balades-type:has([value=tolere])')
        await page.fill('#spot-form [name=note]', 'Chiens calmes sans laisse acceptés tôt le matin')
        await page.fill('#spot-form [name=rule]', 'Laisse obligatoire dans tout le parc')
        await page.click('#spot-form [type=submit]')
        spot = page.locator('.balade-spot')
        await spot.wait_for()
        self.assertIn('Règle officielle', await spot.text_content())
        self.assertIn('Laisse obligatoire dans tout le parc', await spot.text_content())
        await page.wait_for_selector('#balades-map button.balade-tolere[aria-label^="Toléré"]')
        await self.no_overflow()
        await self.capture_evidence(f'balades-track-tolere-{self.api_mode}.png')

        # Reload: the track and its spot persist.
        await page.reload()
        await self.wait_ready()
        await self.open_route('balades')
        await page.click('.balade-row:has-text("Parc de Saint-Cloud") [data-b="open"]')
        self.assertIn('Laisse obligatoire dans tout le parc', await page.locator('.balade-spot').text_content())
        async with page.expect_download() as info:
            await page.click('[data-b="export"]')
        exported = Path(await (await info.value).path()).read_text()
        self.assertEqual(exported.count('<trkpt'), 3)
        self.assertIn('<type>tolere</type>', exported)
        self.assertIn('<cmt>Laisse obligatoire dans tout le parc</cmt>', exported)

        # Import: a malformed file is refused in plain French, a GPX becomes a track with a pause spot.
        await page.click('[data-b="back"]')
        await page.set_input_files('#balades-import', files=[{'name': 'casse.gpx', 'mimeType': 'application/gpx+xml', 'buffer': b'<gpx><trk>'}])
        await page.wait_for_selector('#balades-message[role=alert]:has-text("pas un GPX lisible")')
        await page.set_input_files('#balades-import', files=[{'name': 'etangs.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
        await page.wait_for_selector('#track-form')
        self.assertEqual(await page.input_value('#track-form [name=name]'), 'Boucle des Etangs')
        self.assertEqual(await page.input_value('#track-form [name=date]'), '2026-10-20')
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Boucle des Etangs")')
        self.assertIn('45 min', await page.locator('.balades-track .daily-help').first.text_content())
        self.assertIn("Point d'eau", await page.locator('.balade-spot').text_content())
        await page.click('[data-b="back"]')
        self.assertEqual(await page.locator('.balade-row').count(), 2)
        await self.no_overflow()
        await self.capture_evidence(f'balades-list-{self.api_mode}.png')

        # Planning: a saved walk gets "Ajouter le tracé", then "Voir le tracé".
        await self.open_route('schedule')
        walked = page.locator('#walk-form [name=walked]').first
        dog = await walked.get_attribute('value')
        await walked.check()
        await page.click('#walk-form [type=submit]')
        add = page.locator(f'[data-balade-link="{dog}"]')
        await add.click()
        self.assertEqual(await page.evaluate('state.page'), 'balades')
        await page.click('.balade-row:has-text("Boucle des Etangs") [data-b="link"]')
        await page.wait_for_function("state.page === 'schedule'")
        await page.click(f'#walk-tracks [data-balade-open]')
        await page.wait_for_selector('.balades-track h2:has-text("Boucle des Etangs")')
        self.assertIn('Balades du Planning', await page.locator('.balades-track').text_content())
        await self.no_overflow()
        self.assertEqual(self.console_errors, [])


class StaticBaladesBrowserTest(BaladesBrowserTest):
    api_mode = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_httpd = cls.server_mod.Server(('127.0.0.1', 0), partial(QuietStaticHandler, directory=str(ROOT)))
        cls.static_thread = threading.Thread(target=cls.static_httpd.serve_forever, daemon=True)
        cls.static_thread.start()
        cls.url = f'http://127.0.0.1:{cls.static_httpd.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.static_httpd.shutdown()
        cls.static_httpd.server_close()
        cls.static_thread.join(timeout=2)
        super().tearDownClass()


if __name__ == '__main__':
    unittest.main()
