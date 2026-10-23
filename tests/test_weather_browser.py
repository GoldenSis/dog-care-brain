"""Weather is optional, shared across staff pages, and isolated from care records."""
import asyncio
import json
import threading
from datetime import datetime, timezone
from functools import partial
from urllib.parse import parse_qs, urlparse

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT
from tests.test_tenant_isolation import _http


class WeatherBrowserTest(BrowserFixture):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        if self.api_mode:
            _http(self.port, 'PUT', '/api/weather-settings',
                  {'weatherSettings': {'location': None, 'heatThreshold': 25}}, cookie=self.sid)
            await self.page.reload()
            await self.wait_ready()
        await self.page.clock.install(time=datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc))
        await self.page.clock.pause_at(datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc))
        self.requests = []
        self.fail_forecast = False
        self.snow_only = False
        self.forecast_requested = asyncio.Event()
        self.forecast_release = None
        await self.page.route('https://geocoding-api.open-meteo.com/**', self.geocode)
        await self.page.route('https://api.open-meteo.com/**', self.forecast)
        await self.page.reload()
        await self.wait_ready()

    async def geocode(self, route):
        self.requests.append(route.request)
        await route.fulfill(json={'results': [{'name': 'Lausanne', 'country': 'Suisse',
                                               'latitude': 46.52, 'longitude': 6.63}]})

    async def forecast(self, route):
        self.requests.append(route.request)
        self.forecast_requested.set()
        if self.forecast_release is not None:
            await self.forecast_release.wait()
        if self.fail_forecast:
            await route.fulfill(status=200, body='invalid forecast')
            return
        start = int(datetime(2026, 10, 22, 22, tzinfo=timezone.utc).timestamp())
        hourly = {'time': [start+i*3600 for i in range(48)],
                  'temperature_2m': [18]*48, 'precipitation_probability': [10]*48,
                  'precipitation': [0]*48, 'weather_code': [0]*48,
                  'uv_index': [2]*48, 'wind_gusts_10m': [12]*48}
        for i in (19, 20):
            hourly['temperature_2m'][i] = 29
            hourly['weather_code'][i] = 95
            hourly['precipitation'][i] = 7
        hourly['uv_index'][22] = None
        if self.snow_only:
            hourly.update(temperature_2m=[-2]*48, precipitation=[5]*48,
                          weather_code=[73]*48, uv_index=[2]*48)
        await route.fulfill(json={'timezone': 'Europe/Zurich', 'hourly': hourly})

    async def configure(self):
        await self.open_route('settings')
        await self.page.fill('#weather-city', 'Lausanne')
        await self.page.click('#weather-search button[type=submit], #weather-search button:not([type])')
        await self.page.click('#weather-results button')
        await self.page.fill('#weather-heat', '27')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        self.assertIn('saved', await self.page.inner_text('#weather-save-status'))

    def forecasts(self):
        return [r for r in self.requests if urlparse(r.url).hostname == 'api.open-meteo.com']

    async def test_settings_shared_forecast_languages_mobile_and_stale_fallback(self):
        await self.open_route('schedule')
        self.assertEqual(self.requests, [])
        await self.configure()
        await self.page.reload()
        await self.wait_ready()
        await self.open_route('settings')
        self.assertEqual(await self.page.input_value('#weather-heat'), '27')
        self.assertIn('Lausanne', await self.page.inner_text('#weather-selected'))
        await self.open_route('schedule')
        await self.page.wait_for_selector('.weather-strip footer')
        self.assertEqual(len(self.forecasts()), 1)
        self.assertIn('Tomorrow', await self.page.inner_text('#walk-weather'))
        self.assertIn('Heat', await self.page.inner_text('#walk-weather'))
        self.assertIn('Thunderstorm', await self.page.inner_text('#walk-weather'))
        self.assertIn('Heavy precipitation', await self.page.inner_text('#walk-weather'))
        self.assertIn('27 °C', await self.page.inner_text('#walk-weather'))
        await self.page.click('.weather-strip summary')
        self.assertGreater(await self.page.locator('.weather-best').count(), 0)
        for language in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', language)
            await self.page.wait_for_function('!savePending')
            for destination in ('schedule', 'balades'):
                await self.open_route(destination)
                await self.page.wait_for_selector('.weather-strip footer')
                for width in (390, 1440):
                    await self.page.set_viewport_size({'width': width, 'height': 844})
                    self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertNotIn('undefined', await self.page.inner_text('#walk-weather'))
        self.assertEqual(len(self.forecasts()), 1)
        request = self.forecasts()[0]
        query = parse_qs(urlparse(request.url).query)
        self.assertEqual(query['timezone'], ['auto'])
        self.assertEqual(query['forecast_days'], ['2'])
        self.assertEqual(query['latitude'], ['46.52'])
        self.assertEqual(query['longitude'], ['6.63'])
        self.assertIsNone(request.post_data)
        headers = await request.all_headers()
        self.assertNotIn('cookie', headers)
        self.assertNotIn('referer', headers)
        self.assertNotIn('dog', request.url.lower())
        await self.page.select_option('#language-picker', 'en')
        await self.page.wait_for_function('!savePending')
        # Failed refresh after reload retains the previous timestamp, suppresses suggestions.
        self.fail_forecast = True
        await self.page.evaluate("""() => {
          for (let i=0;i<localStorage.length;i++) {
            const key=localStorage.key(i); if(!key.startsWith('dogcare-weather-forecast'))continue;
            const saved=JSON.parse(localStorage.getItem(key)); saved.fetchedAt-=3600000;
            localStorage.setItem(key,JSON.stringify(saved));
          }
        }""")
        await self.page.reload()
        await self.wait_ready()
        await self.open_route('schedule')
        await self.page.wait_for_function("document.querySelector('.weather-cached')?.textContent.includes('unavailable')")
        self.assertIn('Forecast received', await self.page.inner_text('#walk-weather'))
        self.assertEqual(await self.page.locator('.weather-best').count(), 0)
        await self.page.click('#new-booking')
        self.assertTrue(await self.page.locator('#booking-form').is_visible())
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    async def test_threshold_save_keeps_pending_and_memory_only_forecast(self):
        await self.configure()
        await self.page.evaluate("""() => {
          const save=Storage.prototype.setItem;
          Storage.prototype.setItem=function(key,value){
            if(key.startsWith('dogcare-weather-forecast'))throw Error('quota');
            return save.call(this,key,value);
          };
        }""")
        self.forecast_release = asyncio.Event()
        await self.open_route('schedule')
        await asyncio.wait_for(self.forecast_requested.wait(), timeout=5)
        await self.open_route('settings')
        await self.page.fill('#weather-heat', '30')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        self.assertIn('saved', await self.page.inner_text('#weather-save-status'))
        await self.open_route('balades')
        await self.open_route('schedule')
        self.forecast_release.set()
        await self.page.wait_for_selector('.weather-strip footer')
        self.assertEqual(len(self.forecasts()), 1)
        self.assertNotIn('Heat', await self.page.inner_text('#walk-weather'))
        await self.open_route('settings')
        await self.page.fill('#weather-heat', '26')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        await self.open_route('balades')
        await self.page.wait_for_selector('.weather-strip footer')
        self.assertEqual(len(self.forecasts()), 1)
        self.assertIn('Heat ≥ 26 °C', await self.page.inner_text('#walk-weather'))
        await self.context.grant_permissions(['geolocation'])
        await self.context.set_geolocation({'latitude': 0, 'longitude': 0})
        await self.open_route('settings')
        await self.page.click('#weather-position')
        await self.page.wait_for_function("document.querySelector('#weather-selected').textContent.includes('(0, 0)')")
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        await self.open_route('schedule')
        await self.page.wait_for_selector('.weather-strip footer')
        self.assertEqual(len(self.forecasts()), 2)
        self.assertEqual(parse_qs(urlparse(self.forecasts()[-1].url).query)['latitude'], ['0'])
        await self.open_route('settings')
        await self.page.click('#weather-clear')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        for destination in ('schedule', 'balades'):
            await self.open_route(destination)
            self.assertEqual(await self.page.locator('.weather-strip footer').count(), 0)
            self.assertTrue(await self.page.locator('[data-weather-settings]').is_visible())
        self.assertEqual(len(self.forecasts()), 2)
        self.assertEqual(self.console_errors, [])

    async def test_threshold_save_keeps_failed_forecast_retry_interval(self):
        await self.configure()
        self.fail_forecast = True
        async with self.page.expect_response('https://api.open-meteo.com/**') as response:
            await self.open_route('schedule')
        self.assertEqual(await (await response.value).text(), 'invalid forecast')
        await self.open_route('settings')
        await self.page.fill('#weather-heat', '30')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        await self.open_route('balades')
        await self.open_route('schedule')
        self.assertEqual(await self.page.inner_text('#walk-weather'), '')
        self.assertEqual(len(self.forecasts()), 1)
        async with self.page.expect_response('https://api.open-meteo.com/**') as response:
            await self.page.clock.fast_forward(60000)
        self.assertEqual(await (await response.value).text(), 'invalid forecast')
        self.assertEqual(len(self.forecasts()), 2)
        self.assertEqual(self.console_errors, [])

    async def test_hourly_repaints_keep_scroll_and_keyboard_focus(self):
        await self.configure()
        for destination in ('schedule', 'balades'):
            await self.open_route(destination)
            await self.page.wait_for_selector('.weather-strip footer')
            await self.page.click('.weather-strip summary')
            for selector in ('.weather-hours', '.weather-strip summary',
                             '.weather-strip footer a:first-of-type',
                             '.weather-strip footer a:last-of-type', '#language-picker'):
                await self.page.locator('.weather-hours').evaluate('(el) => { el.scrollLeft=2150; }')
                await self.page.locator(selector).evaluate('(el) => el.focus({preventScroll:true})')
                before = await self.page.locator('.weather-hours').evaluate('(el) => el.scrollLeft')
                self.assertGreater(before, 0)
                await self.page.clock.fast_forward(60000)
                self.assertAlmostEqual(await self.page.locator('.weather-hours').evaluate('(el) => el.scrollLeft'), before, delta=1)
                self.assertTrue(await self.page.locator(selector).evaluate('(el) => el === document.activeElement'), selector)
                await self.page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                self.assertAlmostEqual(await self.page.locator('.weather-hours').evaluate('(el) => el.scrollLeft'), before, delta=1)
                self.assertTrue(await self.page.locator(selector).evaluate('(el) => el === document.activeElement'), selector)
            self.forecast_requested.clear()
            self.forecast_release = asyncio.Event()
            await self.page.clock.fast_forward(31*60000)
            await asyncio.wait_for(self.forecast_requested.wait(), timeout=5)
            await self.page.locator('.weather-hours').evaluate('(el) => { el.scrollLeft=2150; el.focus({preventScroll:true}); }')
            before = await self.page.locator('.weather-hours').evaluate('(el) => el.scrollLeft')
            self.forecast_release.set()
            await self.page.wait_for_function("!document.querySelector('.weather-cached')")
            self.assertAlmostEqual(await self.page.locator('.weather-hours').evaluate('(el) => el.scrollLeft'), before, delta=1)
            self.assertTrue(await self.page.locator('.weather-hours').evaluate('(el) => el === document.activeElement'))
            self.assertTrue(await self.page.locator('.weather-strip details').evaluate('(el) => el.open'))
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(self.console_errors, [])

    async def test_snow_uses_precipitation_labels_in_every_locale(self):
        await self.configure()
        self.snow_only = True
        labels = {
            'fr': ('Précipitations', 'Probabilité de précipitations', 'Fortes précipitations'),
            'en': ('Precipitation', 'Precipitation probability', 'Heavy precipitation'),
            'it': ('Precipitazioni', 'Probabilità di precipitazioni', 'Precipitazioni intense'),
            'de': ('Niederschlag', 'Niederschlagswahrscheinlichkeit', 'Starker Niederschlag'),
            'es': ('Precipitaciones', 'Probabilidad de precipitaciones', 'Precipitaciones intensas'),
        }
        for language, (amount, probability, warning) in labels.items():
            await self.page.select_option('#language-picker', language)
            await self.page.wait_for_function('!savePending')
            for destination in ('schedule', 'balades'):
                await self.open_route(destination)
                await self.page.wait_for_selector('.weather-strip footer')
                await self.page.click('.weather-strip summary')
                terms = await self.page.locator('.weather-hour').first.locator('dt').all_text_contents()
                self.assertIn(amount, terms)
                self.assertIn(probability, terms)
                self.assertEqual(await self.page.locator('.weather-day .weather-warning').first.inner_text(), warning)
                self.assertEqual(await self.page.locator('.weather-hour .weather-warning').first.inner_text(), warning)
                self.assertEqual(await self.page.locator('.weather-best').count(), 0)
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.assertEqual(len(self.forecasts()), 1)
        self.assertEqual(self.console_errors, [])

    async def test_position_failed_save_retry_and_no_cache_failure(self):
        await self.context.grant_permissions(['geolocation'])
        await self.context.set_geolocation({'latitude': 0, 'longitude': 0})
        await self.open_route('settings')
        await self.page.click('#weather-position')
        await self.page.wait_for_function("document.querySelector('#weather-selected').textContent.includes('(0, 0)')")
        # Save failure must retain chosen location and threshold for retry.
        if self.api_mode:
            await self.page.route('**/api/weather-settings', lambda r: r.fulfill(status=200, json={'ok': False}))
        else:
            await self.page.evaluate("""() => { window.originalWeatherSetItem=Storage.prototype.setItem;
              Storage.prototype.setItem=function(key,value){if(key==='dogcare-weather-settings-v1')throw Error('quota');return originalWeatherSetItem.call(this,key,value);}; }""")
        await self.page.fill('#weather-heat', '28')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        self.assertIn('Not saved', await self.page.inner_text('#weather-save-status'))
        self.assertIn('(0, 0)', await self.page.inner_text('#weather-selected'))
        self.assertEqual(await self.page.input_value('#weather-heat'), '28')
        if self.api_mode:
            await self.page.unroute('**/api/weather-settings')
        else:
            await self.page.evaluate('() => { Storage.prototype.setItem=originalWeatherSetItem; }')
        await self.page.click('#weather-settings-form .primary')
        await self.page.wait_for_function('!savePending')
        self.assertIn('saved', await self.page.inner_text('#weather-save-status'))
        self.fail_forecast = True
        await self.open_route('schedule')
        await self.page.wait_for_function("document.querySelector('#walk-weather')!==null")
        await self.page.click('#new-booking')
        self.assertTrue(await self.page.locator('#booking-form').is_visible())
        self.assertEqual(await self.page.inner_text('#walk-weather'), '')
        self.assertEqual(self.page_errors, [])


class StaticWeatherBrowserTest(WeatherBrowserTest):
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
