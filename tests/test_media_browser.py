"""Synthetic private albums and explicit owner publication in real browsers."""
import uuid
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_media_api import png_fixture
from tests.test_tenant_isolation import _http


class MediaJourneyTest(BrowserFixture):
    async def asyncSetUp(self):
        prefix = uuid.uuid4().hex
        self.sid = self.login(prefix + '-media-owner@example.com')
        self.family_email = prefix + '-media-family@example.com'
        daily = {'version': 1, 'clients': [{'id': 'family', 'name': 'Synthetic family'}, {'id': 'other', 'name': 'Other family'}],
                 'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'family'}, {'id': 'pablo', 'name': 'Private Pablo', 'clientId': 'other'}],
                 'bookings': [], 'rates': {'currency': 'CHF', 'day': None, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': daily}, cookie=self.sid)[0], 200)
        self.assertEqual(_http(self.port, 'POST', '/api/portal/members', {'email': self.family_email, 'role': 'client', 'clientId': 'family'}, cookie=self.sid)[0], 200)
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
        environment = patch.dict('os.environ', {'DC_PUBLIC_BUSINESS': str(state['business_id'])})
        environment.start()
        self.addCleanup(environment.stop)
        await super().asyncSetUp()
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')

    async def upload(self, selector, files, count):
        await self.page.locator(selector).set_input_files(files)
        await self.page.wait_for_function('(count) => !savePending && DogCareAPI.getMedia().items.length === count', arg=count)

    async def screenshots(self, stem):
        for width in (1440, 390):
            await self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
            await self.capture_evidence(f'{stem}-{width}.png')

    async def test_owner_preview_public_save_artwork_replace_and_reset(self):
        await self.open_route('settings')
        self.assertEqual(await self.page.locator('#media-hero-preview').get_attribute('src'), 'assets/photos/good-company.jpg')
        async def other_owner_upload(route):
            _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
            response = await self.context.request.post(self.url + '/api/media/upload?purpose=branding', data=png_fixture((80, 80, 80)), headers={
                'Content-Type': 'image/png', 'X-DogCare-Business': str(state['business_id']), 'X-DogCare-Filename': 'Other-owner.png'})
            self.assertTrue(response.ok)
            await route.fulfill(response=await route.fetch())
        await self.page.route('**/api/media/upload?*', other_owner_upload, times=1)
        await self.upload('#media-hero-file', {'name': 'Synthetic duo.png', 'mimeType': 'image/png', 'buffer': png_fixture()}, 2)
        media = await self.page.evaluate('DogCareAPI.getMedia()')
        first = next(item for item in media['items'] if item['name'] == 'Synthetic duo.png')
        self.assertNotEqual(media['items'][0]['id'], first['id'])
        self.assertEqual(await self.page.input_value('#media-hero-choice'), first['id'])
        self.assertIn(first['id'], await self.page.locator('#media-hero-preview').get_attribute('src'))
        self.assertEqual(await self.page.input_value('#media-fit'), 'contain')
        self.assertIsNone((await (await self.context.request.get(self.url + '/api/public/branding')).json())['branding']['hero'])
        self.assertEqual((await self.context.request.get(self.url + '/api/public/media/' + first['id'])).status, 404)
        await self.page.select_option('#media-fit', 'cover')
        await self.page.locator('#media-position').fill('40')
        await self.page.select_option('[data-service-art=day]', 'face:dalmatian')
        await self.page.select_option('[data-service-art=night]', 'media:' + first['id'])
        await self.screenshots('media-owner-preview')
        await self.page.click('#media-brand-save')
        await self.page.wait_for_function('!savePending && DogCareAPI.getMedia().branding.hero !== null')
        await self.page.reload(); await self.wait_ready(); await self.open_route('settings')
        self.assertEqual(await self.page.input_value('#media-position'), '40')
        self.assertEqual(await self.page.input_value('[data-service-art=night]'), 'media:' + first['id'])
        await self.page.click('#public-home')
        await self.page.wait_for_function("document.querySelector('.welcome-photo img').getAttribute('src').startsWith('/api/public/media/')")
        self.assertEqual(await self.page.locator('.welcome-photo img').evaluate('(img)=>img.style.objectPosition'), '50% 40%')
        self.assertEqual(await self.page.locator('[data-service=night] img').count(), 1)
        await self.screenshots('media-public-selected')
        await self.page.reload(); await self.wait_ready(); await self.open_route('settings')
        await self.upload('#media-hero-file', {'name': 'Replacement.png', 'mimeType': 'image/png', 'buffer': png_fixture((25, 100, 160))}, 3)
        self.assertEqual((await (await self.context.request.get(self.url + '/api/public/branding')).json())['branding']['hero']['url'], '/api/public/media/' + first['id'])
        await self.page.select_option('[data-service-art=night]', 'face:pug')
        await self.page.click('#media-brand-save'); await self.page.wait_for_function('!savePending')
        self.assertEqual((await self.context.request.get(self.url + '/api/public/media/' + first['id'])).status, 404)
        await self.page.click('#media-brand-reset'); await self.page.wait_for_function('!savePending')
        self.assertIsNone((await (await self.context.request.get(self.url + '/api/public/branding')).json())['branding']['hero'])
        self.assertEqual(await self.page.locator('#media-hero-preview').get_attribute('src'), 'assets/photos/good-company.jpg')
        self.assertEqual(self.console_errors, [])

    async def test_family_multiple_uploads_cover_lightbox_video_download_and_delete(self):
        client_cookie = self.login(self.family_email)
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name': 'dc_s', 'value': client_cookie, 'url': self.url, 'httpOnly': True}])
        await self.page.goto(self.url); await self.wait_ready()
        await self.page.select_option('#language-picker', 'fr'); await self.page.wait_for_function('!savePending')
        self.assertNotIn('Private Pablo', await self.page.locator('#app-content').inner_text())
        self.assertEqual(await self.page.locator('#media-branding-form').count(), 0)
        video = await self.page.evaluate('''async () => {
          const canvas=document.createElement('canvas');canvas.width=96;canvas.height=64;
          const ctx=canvas.getContext('2d');ctx.fillStyle='#f2851e';ctx.fillRect(0,0,96,64);
          const stream=canvas.captureStream(15), recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'}), parts=[];
          recorder.ondataavailable=event=>parts.push(event.data);
          const done=new Promise(resolve=>recorder.onstop=resolve);recorder.start();
          for(let i=0;i<6;i++){ctx.fillStyle=i%2?'#ffffff':'#f2851e';ctx.fillRect(i*12,12,12,24);await new Promise(resolve=>setTimeout(resolve,100));}
          recorder.stop();await done;stream.getTracks().forEach(track=>track.stop());
          return Array.from(new Uint8Array(await new Blob(parts).arrayBuffer()));
        }''')
        first_png = png_fixture()
        await self.upload('[data-media-upload=nino]:not([capture])', [
            {'name': 'First.png', 'mimeType': 'image/png', 'buffer': first_png},
            {'name': 'Second.png', 'mimeType': 'image/png', 'buffer': png_fixture((20, 90, 110))},
            {'name': 'Play.webm', 'mimeType': 'video/webm', 'buffer': bytes(video)},
        ], 3)
        self.assertEqual(await self.page.locator('[data-album=nino] .album-item').count(), 3)
        media = await self.page.evaluate('DogCareAPI.getMedia()')
        first = next(item for item in media['items'] if item['name'] == 'First.png')
        film = next(item for item in media['items'] if item['name'] == 'Play.webm')
        await self.page.click(f'[data-media-cover="{first["id"]}"]')
        await self.page.wait_for_function('!savePending')
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album=nino] .dog-avatar img').get_attribute('src'), first['url'])
        await self.page.wait_for_function("document.querySelector('.media-thumb video').readyState >= 2")
        await self.screenshots('media-family-album')
        await self.page.click(f'[data-media-open="{first["id"]}"]')
        await self.page.wait_for_selector('.media-lightbox[open] img')
        self.assertTrue(await self.page.locator('.media-lightbox img').evaluate('(img)=>img.complete && img.naturalWidth > 0'))
        async with self.page.expect_download() as download_info:
            await self.page.click('.media-lightbox a[download]')
        download = await download_info.value
        self.assertEqual(download.suggested_filename, 'First.png')
        response = await self.context.request.get(self.url + first['url'])
        self.assertEqual(await response.body(), first_png)
        await self.page.click('.media-lightbox button')
        await self.page.click(f'[data-media-open="{film["id"]}"]')
        await self.page.locator('.media-lightbox video').evaluate('(video)=>video.play()')
        await self.page.wait_for_function("document.querySelector('.media-lightbox video').currentTime > 0")
        await self.page.click('.media-lightbox button')
        self.page.once('dialog', lambda dialog: dialog.accept())
        await self.page.click(f'[data-media-delete="{first["id"]}"]')
        await self.page.wait_for_function('!savePending && DogCareAPI.getMedia().items.length === 2')
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album=nino] .album-item').count(), 2)
        self.assertEqual(await self.page.locator('[data-album=nino] .dog-avatar').count(), 0)
        self.assertEqual(self.console_errors, [])

    async def test_phone_compatible_jpeg_webp_and_h264_mp4_decode_and_play(self):
        await self.open_route('dogs')
        await self.page.click('[data-dog=nino]') if await self.page.locator('[data-dog=nino]').count() else None
        fixtures = await self.page.evaluate('''async () => {
          const canvas=document.createElement('canvas');canvas.width=96;canvas.height=64;
          const ctx=canvas.getContext('2d');ctx.fillStyle='#f2851e';ctx.fillRect(0,0,96,64);
          const photos=[];
          for(const type of ['image/jpeg','image/webp']){
            const blob=await new Promise(resolve=>canvas.toBlob(resolve,type));
            photos.push(Array.from(new Uint8Array(await blob.arrayBuffer())));
          }
          const stream=canvas.captureStream(15), recorder=new MediaRecorder(stream,{mimeType:'video/mp4;codecs=avc1.42001E'}), parts=[];
          recorder.ondataavailable=event=>parts.push(event.data);
          const done=new Promise(resolve=>recorder.onstop=resolve);recorder.start();
          for(let i=0;i<6;i++){ctx.fillStyle=i%2?'#ffffff':'#f2851e';ctx.fillRect(i*12,12,12,24);await new Promise(resolve=>setTimeout(resolve,100));}
          recorder.stop();await done;stream.getTracks().forEach(track=>track.stop());
          return [...photos,Array.from(new Uint8Array(await new Blob(parts).arrayBuffer()))];
        }''')
        await self.upload('[data-media-upload=nino]:not([capture])', [
            {'name': 'Phone.jpg', 'mimeType': 'image/jpeg', 'buffer': bytes(fixtures[0])},
            {'name': 'Photo.webp', 'mimeType': 'image/webp', 'buffer': bytes(fixtures[1])},
            {'name': 'Phone.mp4', 'mimeType': 'video/mp4', 'buffer': bytes(fixtures[2])},
        ], 3)
        media = await self.page.evaluate('DogCareAPI.getMedia()')
        await self.page.reload(); await self.wait_ready(); await self.open_route('dogs')
        await self.page.click('[data-dog=nino]') if await self.page.locator('[data-dog=nino]').count() else None
        await self.page.wait_for_function("Array.from(document.querySelectorAll('.media-thumb img')).every(img=>img.complete && img.naturalWidth > 0)")
        await self.page.wait_for_function("document.querySelector('.media-thumb video').readyState >= 2")
        film = next(item for item in media['items'] if item['name'] == 'Phone.mp4')
        await self.page.click(f'[data-media-open="{film["id"]}"]')
        await self.page.locator('.media-lightbox video').evaluate('(video)=>video.play()')
        await self.page.wait_for_function("document.querySelector('.media-lightbox video').currentTime > 0")
        await self.page.click('.media-lightbox button')
        self.assertEqual(self.console_errors, [])

    async def test_existing_care_only_dog_upload_appears_in_profile_and_gallery(self):
        self.assertNotIn('billie', [dog['id'] for dog in await self.page.evaluate('DogCareAPI.getDaily().dogs')])
        await self.open_route('dogs')
        if await self.page.locator('[data-dog=billie]').count():
            await self.page.click('[data-dog=billie]')
        await self.upload('[data-media-upload=billie]:not([capture])', {'name': 'Legacy synthetic.png', 'mimeType': 'image/png', 'buffer': png_fixture()}, 1)
        await self.open_route('gallery')
        self.assertEqual(await self.page.locator('[data-album=billie] .album-item').count(), 1)
        await self.page.reload(); await self.wait_ready(); await self.open_route('gallery')
        self.assertEqual(await self.page.locator('[data-album=billie] .album-item').count(), 1)
        self.assertEqual(self.console_errors, [])

    async def test_failed_upload_preserves_album_and_recovers_controls(self):
        await self.open_route('dogs')
        await self.page.click('[data-dog=nino]') if await self.page.locator('[data-dog=nino]').count() else None
        await self.upload('[data-media-upload=nino]:not([capture])', {'name': 'Kept.png', 'mimeType': 'image/png', 'buffer': png_fixture()}, 1)
        await self.page.route('**/api/media/upload?*', lambda route: route.abort())
        await self.page.locator('[data-media-upload=nino]:not([capture])').set_input_files({'name': 'Interrupted.png', 'mimeType': 'image/png', 'buffer': png_fixture()})
        await self.page.wait_for_selector('.private-album .media-error:not([hidden])')
        await self.page.wait_for_function('!savePending')
        self.assertIn('interrompu', await self.page.locator('.private-album .media-error').inner_text())
        self.assertEqual(await self.page.locator('.private-album .album-item').count(), 1)
        self.assertTrue(await self.page.locator('[data-media-upload=nino]').first.is_enabled())
        await self.page.unroute('**/api/media/upload?*')
        await self.upload('[data-media-upload=nino]:not([capture])', {'name': 'Retry.png', 'mimeType': 'image/png', 'buffer': png_fixture()}, 2)
        self.assertEqual(await self.page.locator('.private-album .album-item').count(), 2)
        self.assertEqual(len(self.console_errors), 1)
        self.assertIn('net::ERR_FAILED', self.console_errors[0])
