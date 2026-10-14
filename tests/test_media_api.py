import http.client
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import struct
import tempfile
import uuid
import zlib
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


def png_fixture(color=(240, 140, 60), width=4, height=3):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    pixels = (b'\x00' + bytes(color) * width) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def upload_raw(port, cookie, data, dog='nino', purpose=None, mime='image/png', headers=None):
    _, state, _ = _http(port, 'GET', '/api/state', cookie=cookie)
    request_headers = {'Cookie': 'dc_s=' + cookie, 'Content-Type': mime,
                       'X-DogCare-Business': str(state['business_id']), 'X-DogCare-Filename': 'synthetic.png'}
    request_headers.update(headers or {})
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        conn.request('POST', '/api/media/upload?' + ('purpose=' + purpose if purpose else 'dogId=' + dog), data, request_headers)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def read_raw(port, path, cookie=None, headers=None):
    request_headers = {'Cookie': 'dc_s=' + cookie} if cookie else {}
    request_headers.update(headers or {})
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        conn.request('GET', path, headers=request_headers)
        response = conn.getresponse()
        return response.status, response.read(), dict(response.getheaders())
    finally:
        conn.close()


class MediaApiTest(ApiServerTestCase):
    def setUp(self):
        prefix = uuid.uuid4().hex
        self.owner = self.login(prefix + '-owner@example.com')
        self.other = self.login(prefix + '-other@example.com')
        self.daily = {'version': 1, 'clients': [{'id': 'one', 'name': 'One'}, {'id': 'two', 'name': 'Two'}],
                      'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'one'}, {'id': 'pablo', 'name': 'Pablo', 'clientId': 'two'}],
                      'bookings': [], 'rates': {'currency': 'CHF', 'day': None, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': self.daily}, cookie=self.owner)[0], 200)
        for label, role, cid in [('client', 'client', 'one'), ('family', 'client', 'two'), ('carer', 'trusted-carer', None)]:
            email = prefix + '-' + label + '@example.com'
            self.assertEqual(_http(self.port, 'POST', '/api/portal/members', {'email': email, 'role': role, 'clientId': cid}, cookie=self.owner)[0], 200)
            setattr(self, label, self.login(email))

    def uploaded(self, cookie=None, **kwargs):
        data = png_fixture()
        status, body = upload_raw(self.port, cookie or self.client, data, **kwargs)
        self.assertEqual(status, 200, body)
        return next(item for item in body['media']['items'] if item['id'] == body['uploadedId'])

    def test_private_upload_reload_download_cover_and_delete(self):
        one = self.uploaded()
        two = self.uploaded()
        self.assertNotEqual(one['id'], two['id'])
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(status, 200)
        self.assertEqual(len(state['media']['items']), 2)
        self.assertNotIn('contents', json.dumps(state))
        self.assertEqual(read_raw(self.port, one['url'], self.client)[:2], (200, png_fixture()))
        for cookie, code in [(None, 401), (self.other, 404), (self.family, 404), (self.carer, 404)]:
            self.assertEqual(read_raw(self.port, one['url'], cookie)[0], code)
        self.assertEqual(read_raw(self.port, one['url'], self.owner)[0], 200)
        payload = {'dogId': 'nino', 'mediaId': one['id']}
        status, body, _ = _http(self.port, 'POST', '/api/media/cover', payload, cookie=self.client)
        self.assertEqual(status, 200, body)
        self.assertEqual(body['media']['covers']['nino'], one['id'])
        status, body, _ = _http(self.port, 'POST', '/api/media/delete', {'id': one['id']}, cookie=self.client)
        self.assertEqual(status, 200, body)
        self.assertNotIn('nino', body['media']['covers'])
        self.assertEqual(read_raw(self.port, one['url'], self.owner)[0], 404)

    def test_all_operations_enforce_family_business_and_role(self):
        one = self.uploaded()
        for cookie in (self.other, self.family, self.carer):
            status, state, _ = _http(self.port, 'GET', '/api/media', cookie=cookie)
            self.assertEqual(status, 200)
            self.assertEqual(state['media']['items'], [])
            for action, payload in [('cover', {'dogId': 'nino', 'mediaId': one['id']}), ('delete', {'id': one['id']})]:
                self.assertIn(_http(self.port, 'POST', '/api/media/' + action, payload, cookie=cookie)[0], (403, 404))
        for dog in ('pablo', 'guess'):
            self.assertEqual(upload_raw(self.port, self.client, png_fixture(), dog=dog)[0], 403)
        for cookie in (self.client, self.carer):
            self.assertEqual(upload_raw(self.port, cookie, png_fixture(), purpose='branding')[0], 403)
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', {'hero': None, 'services': {}}, cookie=cookie)[0], 403)
        self.assertEqual(upload_raw(self.port, self.client, png_fixture(), headers={'X-DogCare-Business': '999999'})[0], 409)
        self.assertEqual(upload_raw(self.port, self.client, png_fixture(), headers={'Origin': 'https://other.invalid'})[0], 403)

    def test_owner_can_manage_existing_care_only_dog_without_inventing_a_family(self):
        item = self.uploaded(self.owner, dog='billie')
        self.assertEqual(item['dogId'], 'billie')
        self.assertEqual(_http(self.port, 'POST', '/api/media/cover', {'dogId': 'billie', 'mediaId': item['id']}, cookie=self.owner)[0], 200)
        self.assertEqual(upload_raw(self.port, self.client, png_fixture(), dog='billie')[0], 403)
        self.assertEqual(upload_raw(self.port, self.other, png_fixture(), dog='nino')[0], 403)
        self.assertEqual(read_raw(self.port, item['url'], self.client)[0], 404)

    def test_reassignment_never_discloses_old_family_media_or_cover(self):
        item = self.uploaded()
        _http(self.port, 'POST', '/api/media/cover', {'dogId': 'nino', 'mediaId': item['id']}, cookie=self.client)
        self.daily['dogs'][0]['clientId'] = 'two'
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': self.daily}, cookie=self.owner)[0], 200)
        for cookie in (self.client, self.family):
            _, state, _ = _http(self.port, 'GET', '/api/media', cookie=cookie)
            self.assertEqual(state['media']['items'], [])
            self.assertEqual(state['media']['covers'], {})
            self.assertEqual(read_raw(self.port, item['url'], cookie)[0], 404)
        self.assertEqual(read_raw(self.port, item['url'], self.owner)[0], 200)

    def test_membership_reassignment_during_read_never_uses_the_new_family_with_an_old_session(self):
        target = self.uploaded(self.family, dog='pablo')
        _, owner, _ = _http(self.port, 'GET', '/api/auth/me', cookie=self.owner)
        _, client, _ = _http(self.port, 'GET', '/api/auth/me', cookie=self.client)
        with self.server_mod.connection() as c:
            owner_row = dict(c.execute('SELECT * FROM user WHERE email=?', (owner['email'],)).fetchone())
        original = self.server_mod.Handler._need_user

        for path in (target['url'], '/api/media', '/api/state'):
            with self.subTest(path=path):
                with self.server_mod._lock, self.server_mod.connection() as c:
                    self.server_mod.portal.add_member(c, owner_row, {'email': client['email'], 'role': 'client', 'clientId': 'one'})
                cookie = self.login(client['email'])

                def reassign(handler, *args, **kwargs):
                    user = original(handler, *args, **kwargs)
                    if user and handler.path == path:
                        with self.server_mod._lock, self.server_mod.connection() as c:
                            self.server_mod.portal.add_member(c, owner_row, {'email': client['email'], 'role': 'client', 'clientId': 'two'})
                    return user

                with patch.object(self.server_mod.Handler, '_need_user', reassign):
                    status, content, _ = read_raw(self.port, path, cookie)
                if path == target['url']:
                    self.assertIn(status, (401, 404))
                else:
                    self.assertIn(status, (200, 401))
                    if status == 200:
                        self.assertNotIn(target['id'], {item['id'] for item in json.loads(content)['media']['items']})
                self.assertEqual(read_raw(self.port, path, cookie)[0], 401)

    def test_explicit_owner_branding_publish_replace_reset_and_private_album_refusal(self):
        private = self.uploaded()
        first = self.uploaded(self.owner, purpose='branding')
        second = self.uploaded(self.owner, purpose='branding')
        _, owner, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        with patch.dict(os.environ, {'DC_PUBLIC_BUSINESS': str(owner['business_id'])}):
            for item in (private, first, second):
                self.assertEqual(read_raw(self.port, '/api/public/media/' + item['id'])[0], 404)
            payload = {'hero': {'mediaId': private['id'], 'fit': 'contain', 'position': 50}, 'services': {}}
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', payload, cookie=self.owner)[0], 400)
            payload['hero']['mediaId'] = first['id']
            payload['services'] = {'day': {'face': 'terrier'}, 'night': {'mediaId': second['id']}, 'walk': {'face': 'pug'}}
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', payload, cookie=self.owner)[0], 200)
            _, public, _ = _http(self.port, 'GET', '/api/public/branding')
            self.assertEqual(public['branding']['hero']['fit'], 'contain')
            self.assertEqual(read_raw(self.port, public['branding']['hero']['url'])[:2], (200, png_fixture()))
            self.assertNotIn('name', json.dumps(public))
            self.assertEqual(read_raw(self.port, '/api/public/media/' + second['id'])[0], 200)
            payload['hero']['mediaId'] = second['id']
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', payload, cookie=self.owner)[0], 200)
            self.assertEqual(read_raw(self.port, '/api/public/media/' + first['id'])[0], 404)
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', {'hero': None, 'services': {}}, cookie=self.owner)[0], 200)
            self.assertEqual(read_raw(self.port, '/api/public/media/' + second['id'])[0], 404)

    def test_rejects_spoofed_truncated_oversized_and_invalid_uploads_atomically(self):
        invalid_vp8 = bytes.fromhex('0000009d012a01000100')
        invalid_webp = b'RIFF' + struct.pack('<I', 4 + 8 + len(invalid_vp8)) + b'WEBPVP8 ' + struct.pack('<I', len(invalid_vp8)) + invalid_vp8
        for data, mime in [(b'<svg onload="alert(1)">', 'image/png'), (png_fixture()[:-1], 'image/png'),
                           (png_fixture(), 'image/jpeg'), (b'HEIC', 'image/heic'),
                           (bytes.fromhex('ffd8ffc00008080001000101ffda000278ffd9'), 'image/jpeg'), (invalid_webp, 'image/webp'),
                           (b'\x00\x00\x00\x18ftypisom', 'video/mp4')]:
            status, body = upload_raw(self.port, self.client, data, mime=mime)
            self.assertEqual(status, 400, body)
        status, body = upload_raw(self.port, self.client, b'x', headers={'Content-Length': str(81 * 1024 * 1024)})
        self.assertEqual(status, 413, body)
        _, state, _ = _http(self.port, 'GET', '/api/media', cookie=self.client)
        self.assertEqual(state['media']['items'], [])

    def test_interrupted_upload_and_revocation_during_upload_leave_no_media(self):
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        body = png_fixture()
        def start():
            connection = socket.create_connection(('127.0.0.1', self.port), timeout=5)
            head = (f'POST /api/media/upload?dogId=nino HTTP/1.0\r\nHost: 127.0.0.1:{self.port}\r\n'
                    f'Cookie: dc_s={self.client}\r\nContent-Type: image/png\r\nContent-Length: {len(body)}\r\n'
                    f'X-DogCare-Business: {state["business_id"]}\r\n\r\n').encode()
            connection.sendall(head + body[:8])
            return connection
        with start() as connection:
            connection.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(connection)
            response.begin()
            self.assertEqual(response.status, 400)
            response.read()
        with start() as connection:
            _, owner, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
            member = next(x for x in owner['portal']['members'] if x['role'] == 'client' and x['clientId'] == 'one')
            self.assertEqual(_http(self.port, 'POST', '/api/portal/revoke', {'userId': member['id']}, cookie=self.owner)[0], 200)
            connection.sendall(body[8:])
            response = http.client.HTTPResponse(connection)
            response.begin()
            self.assertIn(response.status, (401, 403))
            response.read()
        _, state, _ = _http(self.port, 'GET', '/api/media', cookie=self.owner)
        self.assertEqual(state['media']['items'], [])

    def test_invalid_branding_and_cover_values_leave_saved_selection_intact(self):
        item = self.uploaded(self.owner, purpose='branding')
        payload = {'hero': {'mediaId': item['id'], 'fit': 'contain', 'position': 50}, 'services': {'night': {'face': 'pug'}}}
        self.assertEqual(_http(self.port, 'POST', '/api/media/branding', payload, cookie=self.owner)[0], 200)
        for invalid in ({'position': -1}, {'position': True}, {'fit': 'javascript:alert(1)'}, {'mediaId': []}):
            bad = {**payload, 'hero': {**payload['hero'], **invalid}}
            self.assertEqual(_http(self.port, 'POST', '/api/media/branding', bad, cookie=self.owner)[0], 400)
        self.assertEqual(_http(self.port, 'POST', '/api/media/cover', {'dogId': 'nino', 'mediaId': item['id']}, cookie=self.owner)[0], 404)
        _, current, _ = _http(self.port, 'GET', '/api/media', cookie=self.owner)
        self.assertEqual(current['media']['branding'], payload)

    def test_media_quotas_reject_without_partial_metadata(self):
        with patch.object(self.server_mod.media, 'BUSINESS_LIMIT', 1):
            self.assertEqual(upload_raw(self.port, self.client, png_fixture())[0], 400)
        with patch.object(self.server_mod.media, 'ITEM_LIMIT', 0):
            self.assertEqual(upload_raw(self.port, self.client, png_fixture())[0], 400)
        _, state, _ = _http(self.port, 'GET', '/api/media', cookie=self.owner)
        self.assertEqual(state['media']['items'], [])

    def test_range_downloads_and_backup_restore_include_exact_media(self):
        item = self.uploaded()
        status, content, headers = read_raw(self.port, item['url'], self.client, {'Range': 'bytes=2-10'})
        self.assertEqual((status, content), (206, png_fixture()[2:11]))
        self.assertEqual(headers['Content-Range'], 'bytes 2-10/' + str(len(png_fixture())))
        self.assertEqual(read_raw(self.port, item['url'], self.client, {'Range': 'bytes=9999-'})[0], 416)
        from scripts import private_backup
        with tempfile.TemporaryDirectory(prefix='dogcare-media-backup-') as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            with self.server_mod.connection() as c, closing(sqlite3.connect(source / 'dogcare.db')) as dest:
                c.backup(dest)
            shutil.copytree(os.environ['DC_BLOBS'], source / 'blobs')
            snapshot = private_backup.backup(source, root / 'backups')
            restored = private_backup.restore(snapshot, root / 'restored')
            with closing(sqlite3.connect(restored / 'dogcare.db')) as c:
                data, = c.execute('SELECT contents FROM media_asset WHERE id=?', (item['id'],)).fetchone()
                self.assertEqual(data, png_fixture())
