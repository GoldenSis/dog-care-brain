"""Synthetic private albums and explicit owner publication in real browsers."""
import asyncio
from pathlib import Path
import shutil
import tempfile
import uuid
from unittest.mock import patch

from tests.test_browser_acceptance import BrowserFixture
from tests.test_media_api import png_fixture
from tests.test_tenant_isolation import _http
from tests.phone_media_fixtures import make_mov


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
        await self.page.wait_for_function("!document.querySelector('#toast.show')")
        await self.page.evaluate('document.activeElement?.blur()')
        for width in (1440, 390):
            await self.page.set_viewport_size({'width': width, 'height': 900})
            await self.page.mouse.move(0, 0)
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), width)
            await self.capture_evidence(f'{stem}-{width}.png', full_page=not await self.page.locator('.media-lightbox[open]').count())

    async def test_owner_preview_public_save_artwork_replace_and_reset(self):
        await self.open_route('settings')
        self.assertEqual(await self.page.locator('#media-hero-preview').get_attribute('src'), 'assets/photos/good-company.jpg')
        self.assertFalse(await self.page.locator('#media-position').is_visible())
        self.assertEqual(await self.page.locator('.media-settings .media-help').inner_text(), 'Photos jusqu’à 12 Mio.')
        self.assertEqual(await self.page.locator('#media-brand-save').inner_text(), 'Enregistrer sur le site')
        picker = self.page.get_by_label('Changer la photo', exact=True)
        await self.page.keyboard.press('Tab')
        await picker.focus()
        self.assertEqual(await picker.locator('..').evaluate('(label)=>getComputedStyle(label).outlineStyle'), 'solid')
        async with self.page.expect_file_chooser() as chooser_info:
            await self.page.keyboard.press('Enter')
        chooser = await chooser_info.value
        self.assertFalse(chooser.is_multiple())
        synthetic_duo = await self.page.evaluate('''async () => {
          const canvas=document.createElement('canvas');canvas.width=400;canvas.height=240;
          const ctx=canvas.getContext('2d');ctx.fillStyle='#fff3e5';ctx.fillRect(0,0,400,240);
          for(const [x,color] of [[100,'#ca864b'],[300,'#687581']]){
            ctx.fillStyle=color;ctx.beginPath();ctx.ellipse(x,120,52,65,0,0,Math.PI*2);ctx.fill();
            for(const direction of [-1,1]){
              ctx.beginPath();ctx.ellipse(x+direction*48,80,16,43,direction*.4,0,Math.PI*2);ctx.fill();
              ctx.fillStyle='#252525';ctx.beginPath();ctx.arc(x+direction*18,108,5,0,Math.PI*2);ctx.fill();ctx.fillStyle=color;
            }
            ctx.fillStyle='#252525';ctx.beginPath();ctx.arc(x,136,9,0,Math.PI*2);ctx.fill();
          }
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          return Array.from(new Uint8Array(await blob.arrayBuffer()));
        }''')
        async def other_owner_upload(route):
            _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.sid)
            response = await self.context.request.post(self.url + '/api/media/upload?purpose=branding', data=png_fixture((80, 80, 80)), headers={
                'Content-Type': 'image/png', 'X-DogCare-Business': str(state['business_id']), 'X-DogCare-Filename': 'Other-owner.png'})
            self.assertTrue(response.ok)
            await route.fulfill(response=await route.fetch())
        await self.page.route('**/api/media/upload?*', other_owner_upload, times=1)
        await self.upload('#media-hero-file', {'name': 'Synthetic duo.png', 'mimeType': 'image/png', 'buffer': bytes(synthetic_duo)}, 2)
        media = await self.page.evaluate('DogCareAPI.getMedia()')
        first = next(item for item in media['items'] if item['name'] == 'Synthetic duo.png')
        self.assertNotEqual(media['items'][0]['id'], first['id'])
        self.assertEqual(await self.page.input_value('#media-hero-choice'), first['id'])
        self.assertIn(first['id'], await self.page.locator('#media-hero-preview').get_attribute('src'))
        self.assertEqual(await self.page.input_value('#media-fit'), 'contain')
        self.assertEqual(await self.page.locator('#media-fit option:checked').inner_text(), 'Photo entière')
        self.assertFalse(await self.page.locator('#media-position').is_visible())
        self.assertEqual(await self.page.locator('#media-hero-preview').evaluate('(img)=>img.style.objectFit'), 'contain')
        await self.screenshots('media-owner-whole-photo')
        self.assertIsNone((await (await self.context.request.get(self.url + '/api/public/branding')).json())['branding']['hero'])
        self.assertEqual((await self.context.request.get(self.url + '/api/public/media/' + first['id'])).status, 404)
        await self.page.select_option('#media-fit', 'cover')
        self.assertTrue(await self.page.locator('#media-position').is_visible())
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
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
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
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
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
        await self.page.locator('.media-lightbox video').evaluate('(video)=>video.pause()')
        await self.screenshots('media-family-playback')
        await self.page.click('.media-lightbox button')
        self.page.once('dialog', lambda dialog: dialog.accept())
        await self.page.click(f'[data-media-delete="{first["id"]}"]')
        await self.page.wait_for_function('!savePending && DogCareAPI.getMedia().items.length === 2')
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album=nino] .album-item').count(), 2)
        self.assertEqual(await self.page.locator('[data-album=nino] .dog-avatar').count(), 0)
        self.assertEqual(self.console_errors, [])

    async def test_no_demo_family_albums_use_only_actual_registry_after_note_and_reload(self):
        email = uuid.uuid4().hex + '-empty-owner@example.com'
        with patch.dict('os.environ', {'DC_ALLOW_DEMO_SIGNUP': '0'}):
            with self.server_mod.connection() as c:
                self.server_mod.ensure_account(c, email)
        owner = self.login(email)
        _, initial, _ = _http(self.port, 'GET', '/api/state', cookie=owner)
        self.assertEqual(initial['dogs'], [])
        self.assertEqual(initial['observations'], {})
        daily = {'version': 1, 'clients': [{'id': 'family', 'name': 'Synthetic family'}, {'id': 'other', 'name': 'Other family'}],
                 'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'family'}, {'id': 'pablo', 'name': 'Private Pablo', 'clientId': 'other'}],
                 'bookings': [], 'rates': {'currency': 'CHF', 'day': None, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': daily}, cookie=owner)[0], 200)
        family_email = uuid.uuid4().hex + '-only-nino@example.com'
        self.assertEqual(_http(self.port, 'POST', '/api/portal/members', {'email': family_email, 'role': 'client', 'clientId': 'family'}, cookie=owner)[0], 200)
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name': 'dc_s', 'value': owner, 'url': self.url, 'httpOnly': True}])
        await self.page.goto(self.url); await self.wait_ready()
        await self.open_route('capture')
        await self.page.click('[data-capture-dog=nino]')
        await self.page.fill('#observation', 'Note synthétique : Nino a bu après la promenade.')
        await self.page.click('#save-observation')
        await self.page.wait_for_function("!savePending && state.observations.nino?.length===1")
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(set(await self.page.evaluate('Object.keys(state.observations)')), {'nino', 'pablo'})
        await self.open_route('gallery')
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album).sort()'), ['nino', 'pablo'])
        client = self.login(family_email)
        fresh = await self.browser.new_context(viewport={'width': 390, 'height': 900})
        self.addAsyncCleanup(fresh.close)
        await fresh.add_cookies([{'name': 'dc_s', 'value': client, 'url': self.url, 'httpOnly': True}])
        page = await fresh.new_page()
        for _ in range(2):
            await page.goto(self.url)
            await page.wait_for_function("document.querySelector('#app-content')?.dataset.ready==='true'")
            self.assertEqual(await page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
            self.assertEqual(await page.locator('[data-album] h2').all_text_contents(), ['Nino · Album privé'])
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name': 'dc_s', 'value': client, 'url': self.url, 'httpOnly': True}])
        await self.page.goto(self.url); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
        await self.upload('[data-media-upload=nino]:not([capture])', {'name': 'Nino.png', 'mimeType': 'image/png', 'buffer': png_fixture()}, 1)
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
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

    async def test_phone_hevc_mov_upload_normalizes_and_plays_after_reload(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('installed ffmpeg and ffprobe required')
        with tempfile.TemporaryDirectory() as folder:
            video = await asyncio.to_thread(make_mov, Path(folder) / 'Phone.MOV')
        client = self.login(self.family_email)
        await self.context.clear_cookies()
        await self.context.add_cookies([{'name': 'dc_s', 'value': client, 'url': self.url, 'httpOnly': True}])
        await self.page.goto(self.url); await self.wait_ready()
        await self.page.select_option('#language-picker', 'fr'); await self.page.wait_for_function('!savePending')
        await self.upload('[data-media-upload=nino]:not([capture])', {'name': 'Phone.MOV', 'mimeType': 'video/quicktime', 'buffer': video}, 1)
        media = await self.page.evaluate('DogCareAPI.getMedia()')
        film = media['items'][0]
        self.assertEqual((film['name'], film['mime']), ('Phone.mp4', 'video/mp4'))
        await self.page.reload(); await self.wait_ready()
        self.assertEqual(await self.page.locator('[data-album]').evaluate_all('(albums)=>albums.map(album=>album.dataset.album)'), ['nino'])
        await self.page.wait_for_function("document.querySelector('.media-thumb video').readyState >= 2")
        await self.page.click(f'[data-media-open="{film["id"]}"]')
        await self.page.locator('.media-lightbox video').evaluate('(video)=>{video.muted=true;return video.play();}')
        await self.page.wait_for_function("document.querySelector('.media-lightbox video').currentTime > 0")
        await self.page.locator('.media-lightbox video').evaluate('(video)=>video.pause()')
        await self.screenshots('media-phone-normalized-playback')
        self.assertEqual(await self.page.locator('.media-lightbox a[download]').inner_text(), 'Télécharger le fichier ↗')
        async with self.page.expect_download() as download_info:
            await self.page.click('.media-lightbox a[download]')
        self.assertEqual((await download_info.value).suggested_filename, 'Phone.mp4')
        await self.page.click('.media-lightbox button')
        await self.upload('[data-media-upload=nino]:not([capture])', {'name': 'Unknown-type.MOV', 'mimeType': 'application/octet-stream', 'buffer': video}, 2)
        second = next(item for item in (await self.page.evaluate('DogCareAPI.getMedia()'))['items'] if item['name'] == 'Unknown-type.mp4')
        self.assertEqual(second['mime'], 'video/mp4')
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
