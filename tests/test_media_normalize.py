import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from tests.phone_media_fixtures import make_mov
from tests import test_media_api as media_tests
from tests.test_media_api import read_raw, upload_raw
from tests.test_tenant_isolation import ApiServerTestCase, _http


class PhoneMediaApiTest(ApiServerTestCase):
    setUp = media_tests.MediaApiTest.setUp

    def test_concurrent_png_validation_is_bounded_and_releases_slot(self):
        import media
        entered, release = threading.Event(), threading.Event()
        validate_png = media.png
        calls = []

        def blocked_validation(data):
            calls.append(len(data))
            if len(calls) == 1:
                entered.set()
                if not release.wait(4):
                    raise ValueError('test validation timed out')
            return validate_png(data)

        payload = media_tests.png_fixture()
        with patch.object(media, 'png', side_effect=blocked_validation), ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(upload_raw, self.port, self.client, payload)
            try:
                self.assertTrue(entered.wait(2))
                status, body = upload_raw(self.port, self.client, payload)
                self.assertEqual(status, 400, body)
                self.assertIn('déjà en cours', body['error'])
                self.assertEqual(len(calls), 1)
                self.assertEqual(_http(self.port, 'GET', '/api/media', cookie=self.client)[1]['media']['items'], [])
            finally:
                release.set()
            self.assertEqual(first.result()[0], 200)
        status, body = upload_raw(self.port, self.client, b'invalid png')
        self.assertEqual(status, 400, body)
        self.assertEqual(body['error'], media.INVALID)
        self.assertEqual(upload_raw(self.port, self.client, payload)[0], 200)
        self.assertEqual(len(_http(self.port, 'GET', '/api/media', cookie=self.client)[1]['media']['items']), 2)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'local ffmpeg/ffprobe required')
    def test_hevc_mov_normalizes_private_playable_download_without_source_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = make_mov(Path(temporary) / 'synthetic.mov')
            status, body = upload_raw(self.port, self.client, payload, mime='video/quicktime', headers={'X-DogCare-Filename': 'Phone.MOV'})
            self.assertEqual(status, 200, body)
            item = next(i for i in body['media']['items'] if i['id'] == body['uploadedId'])
            self.assertEqual((item['mime'], item['name']), ('video/mp4', 'Phone.mp4'))
            status, content, _ = read_raw(self.port, item['url'], self.client)
            self.assertEqual(status, 200)
            result = Path(temporary) / 'result.mp4'
            result.write_bytes(content)
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(result)]))
            self.assertEqual({s['codec_name'] for s in info['streams']}, {'h264', 'aac'})
            self.assertNotIn('private synthetic', json.dumps(info))
            subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(result), '-f', 'null', '-'], check=True, capture_output=True)
            self.assertEqual(read_raw(self.port, item['url'], self.family)[0], 404)
            self.assertEqual(read_raw(self.port, item['url'], self.other)[0], 404)
            self.assertEqual(read_raw(self.port, item['url'])[0], 401)
            self.assertEqual(_http(self.port, 'POST', '/api/media/delete', {'id': item['id']}, cookie=self.client)[0], 200)

    def test_valid_heic_header_missing_decoder_fails_without_saved_entry(self):
        import media_normalize
        source = b'\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic'
        actual = shutil.which
        with patch.object(media_normalize.shutil, 'which', side_effect=lambda name: None if name == 'heif-convert' else actual(name)):
            status, body = upload_raw(self.port, self.client, source, mime='image/heic')
        self.assertEqual(status, 400)
        self.assertIn('HEIC/HEIF indisponible', body['error'])
        self.assertEqual(_http(self.port, 'GET', '/api/media', cookie=self.client)[1]['media']['items'], [])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'local ffmpeg/ffprobe required')
    def test_heic_converter_output_is_redecoded_and_metadata_removed(self):
        import media_normalize
        source = Path(__file__).with_name('fixtures') / 'synthetic-phone.heic'
        with tempfile.TemporaryDirectory() as temporary:
            decoded = Path(temporary) / 'decoder.jpg'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=orange:s=32x24',
                            '-frames:v', '1', '-update', '1', str(decoded)], check=True, capture_output=True)
            jpeg = decoded.read_bytes()
            exif = b'Exif\x00\x00private synthetic metadata'
            jpeg = jpeg[:2] + b'\xff\xe1' + (len(exif) + 2).to_bytes(2, 'big') + exif + jpeg[2:]
            original_tool, original_run = media_normalize.tool, media_normalize.run
            def converter(arguments, directory, deadline):
                if arguments[0] == '/synthetic-heif-convert':
                    self.assertIn('--strict', arguments)
                    Path(arguments[-1]).write_bytes(jpeg)
                    return b''
                return original_run(arguments, directory, deadline)
            with patch.object(media_normalize, 'tool', side_effect=lambda name: '/synthetic-heif-convert' if name == 'heif-convert' else original_tool(name)), patch.object(media_normalize, 'run', side_effect=converter):
                status, body = upload_raw(self.port, self.client, source.read_bytes(), mime='image/heic', headers={'X-DogCare-Filename': 'Phone.heic'})
            self.assertEqual(status, 200, body)
            item = next(i for i in body['media']['items'] if i['id'] == body['uploadedId'])
            self.assertEqual((item['mime'], item['name']), ('image/jpeg', 'Phone.jpg'))
            content = read_raw(self.port, item['url'], self.client)[1]
            self.assertNotIn(b'Exif', content)
            self.assertNotIn(b'private synthetic', content)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'local ffmpeg/ffprobe required')
    def test_duration_limit_and_busy_converter_do_not_publish_partial_media(self):
        import media_normalize
        with tempfile.TemporaryDirectory() as temporary:
            payload = make_mov(Path(temporary) / 'synthetic.mov', hevc=False)
            with patch.object(media_normalize, 'SECONDS_LIMIT', 0):
                status, body = upload_raw(self.port, self.client, payload, mime='video/quicktime')
                self.assertEqual(status, 400)
                self.assertIn('60 secondes', body['error'])
            media_normalize._SLOTS.acquire()
            try:
                status, body = upload_raw(self.port, self.client, payload, mime='video/quicktime')
                self.assertEqual(status, 400)
                self.assertIn('déjà en cours', body['error'])
            finally:
                media_normalize._SLOTS.release()
            with patch.object(media_normalize, 'TIMEOUT', 0):
                self.assertEqual(upload_raw(self.port, self.client, payload, mime='video/quicktime')[0], 400)
        self.assertEqual(_http(self.port, 'GET', '/api/media', cookie=self.client)[1]['media']['items'], [])

    def test_disguised_network_playlist_never_reaches_decoder(self):
        import media_normalize
        with patch.object(media_normalize, 'run') as decode:
            status, _ = upload_raw(self.port, self.client, b'#EXTM3U\nhttp://127.0.0.1/private\n', mime='video/quicktime')
        self.assertEqual(status, 400)
        decode.assert_not_called()

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and shutil.which('heif-convert'), 'installed libheif converter required; target runtime gate must verify HEIC')
    def test_real_heic_photo_normalizes_and_decodes(self):
        source = Path(__file__).with_name('fixtures') / 'synthetic-phone.heic'
        status, body = upload_raw(self.port, self.client, source.read_bytes(), mime='image/heic', headers={'X-DogCare-Filename': 'Phone.HEIC'})
        self.assertEqual(status, 200, body)
        item = next(i for i in body['media']['items'] if i['id'] == body['uploadedId'])
        self.assertEqual((item['mime'], item['name']), ('image/jpeg', 'Phone.jpg'))
        status, content, _ = read_raw(self.port, item['url'], self.client)
        self.assertEqual(status, 200)
        self.assertEqual(content[:2], b'\xff\xd8')
        self.assertNotIn(b'Exif', content)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'local ffmpeg/ffprobe required')
    def test_rotated_phone_movie_keeps_portrait_orientation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, rotated = Path(temporary) / 'source.mov', Path(temporary) / 'portrait.mov'
            make_mov(source, hevc=False)
            subprocess.run(['ffmpeg', '-v', 'error', '-display_rotation', '90', '-i', str(source), '-c', 'copy', str(rotated)], check=True, capture_output=True)
            status, body = upload_raw(self.port, self.client, rotated.read_bytes(), mime='video/quicktime')
            self.assertEqual(status, 200, body)
            item = next(i for i in body['media']['items'] if i['id'] == body['uploadedId'])
            rotated.write_bytes(read_raw(self.port, item['url'], self.client)[1])
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-of', 'json', str(rotated)]))
            self.assertEqual((info['streams'][0]['width'], info['streams'][0]['height']), (64, 96))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'local ffmpeg/ffprobe required')
    def test_failed_conversion_cleans_private_temporary_files_and_releases_slot(self):
        import media_normalize
        source = Path(__file__).with_name('fixtures') / 'synthetic-phone.mov'
        with tempfile.TemporaryDirectory() as temporary:
            with source.open('rb') as stream, patch.object(media_normalize, 'TIMEOUT', 0):
                with self.assertRaisesRegex(ValueError, 'Conversion trop'):
                    with media_normalize.normalize(stream, 'video/quicktime', source.stat().st_size, 'Phone.mov', temporary):
                        self.fail('expired conversion succeeded')
            self.assertEqual(list(Path(temporary).iterdir()), [])
            with source.open('rb') as stream, media_normalize.normalize(stream, 'video/quicktime', source.stat().st_size, 'Phone.mov', temporary) as result:
                self.assertEqual(result[1], 'video/mp4')
            self.assertEqual(list(Path(temporary).iterdir()), [])
