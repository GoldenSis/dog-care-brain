"""A second instance carries its own brand; the default stays Le Bus des Toutous."""
import os
from pathlib import Path
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_tenant_isolation import _http

ROOT = Path(__file__).resolve().parents[1]
NICOLAS = {'DC_BRAND_NAME': 'nicolasdelalaissedogcare', 'DC_BRAND_OWNER': 'Nicolas',
           'DC_BRAND_INSTAGRAM': 'nicolasdelalaisse', 'DC_BRAND_MARK': 'sun',
           'DC_BRAND_PRIMARY': '#F6B40E', 'DC_BRAND_DARK': '#85340A', 'DC_BRAND_SECONDARY': '#74ACDF'}


class BrandInstanceTest(BrowserFixture):
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


def _raw(port, path, cookie):
    import http.client
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    connection.request('GET', path, headers={'Cookie': 'dc_s=' + cookie})
    return connection.getresponse().read()
