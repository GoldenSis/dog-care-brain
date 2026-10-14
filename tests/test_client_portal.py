"""Real account boundaries with synthetic, isolated businesses and memberships."""
import base64
import concurrent.futures
import copy
import hashlib
import threading
import uuid
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


class ClientPortalTest(ApiServerTestCase):
    def setUp(self):
        self.prefix = uuid.uuid4().hex
        self.owner = self.login(self.prefix + '-owner@example.com')
        self.other_owner = self.login(self.prefix + '-other@example.com')
        self.daily = {"version": 1, "clients": [{"id": "one", "name": "First family"}, {"id": "two", "name": "Other family"}],
                      "dogs": [{"id": "nino", "name": "Nino", "clientId": "one"}, {"id": "pablo", "name": "Private Pablo", "clientId": "two"}],
                      "bookings": [], "rates": {"currency": "CHF", "day": 99123, "night": None, "walk": None}, "documents": []}
        status, body, _ = _http(self.port, 'PUT', '/api/daily', {'daily': self.daily}, cookie=self.owner)
        self.assertEqual(status, 200, body)
        self.client_email = self.prefix + '-client@example.com'
        self.member(self.client_email, 'client', 'one')
        self.client = self.login(self.client_email)
        carer_email = self.prefix + '-carer@example.com'
        self.member(carer_email, 'trusted-carer', None)
        self.carer = self.login(carer_email)

    def member(self, email, role, client):
        status, body, _ = _http(self.port, 'POST', '/api/portal/members', {'email': email, 'role': role, 'clientId': client}, cookie=self.owner)
        self.assertEqual(status, 200, body)
        return body

    def upload(self, endpoint, dog='nino'):
        payload = {'dogId': dog, 'label': 'Welcome agreement', 'renewal': '', 'name': 'agreement.pdf', 'type': 'application/pdf',
                   'data': base64.b64encode(b'%PDF-1.4\nsynthetic agreement').decode()}
        status, body, _ = _http(self.port, 'POST', endpoint, payload, cookie=self.owner)
        self.assertEqual(status, 200, body)
        return body

    def test_anonymous_payloads_and_client_projection_exclude_internal_records(self):
        for path in ['/api/state', '/api/dogs', '/api/observations', '/api/invites', '/api/finance', '/api/client-documents/guess']:
            status, body, _ = _http(self.port, 'GET', path)
            self.assertEqual(status, 401, path)
            self.assertNotIn('Private Pablo', str(body))
        for dog, text in [('nino', 'Shared walk news'), ('pablo', 'Other private family news')]:
            status, _, _ = _http(self.port, 'POST', '/api/portal/updates', {'dogId': dog, 'text': text}, cookie=self.owner)
            self.assertEqual(status, 200)
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(status, 200)
        self.assertEqual([x['name'] for x in state['dogs']], ['Nino'])
        self.assertEqual(state['observations'], {})
        self.assertEqual(state['invites'], [])
        self.assertIsNone(state['finance'])
        self.assertIsNone(state['knowledge'])
        self.assertEqual([x['text'] for x in state['portal']['updates']], ['Shared walk news'])
        self.assertEqual(state['portal']['members'], [])
        for private in ['Private Pablo', 'Other family', 'Other private family news', '99123', 'Evening medication']:
            self.assertNotIn(private, str(state))

    def test_client_requests_persist_and_only_own_dogs_can_be_requested(self):
        payload = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': 'A quiet arrival'}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', payload, cookie=self.client)
        self.assertEqual(status, 200, state)
        request = state['portal']['requests'][0]
        self.assertEqual(request['status'], 'requested')
        self.assertEqual(state['daily']['bookings'], [])
        for dog in ['pablo', 'guess']:
            status, _, _ = _http(self.port, 'POST', '/api/portal/requests', {**payload, 'dogId': dog}, cookie=self.client)
            self.assertEqual(status, 403)
        _, reloaded, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(reloaded['portal']['requests'], [request])
        status, _, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': request['id'], 'status': 'accepted'}, cookie=self.other_owner)
        self.assertEqual(status, 400)
        status, owner, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': request['id'], 'status': 'accepted'}, cookie=self.owner)
        self.assertEqual(status, 200, owner)
        self.assertEqual(owner['daily']['bookings'][0]['unitMinor'], 99123)
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(state['portal']['requests'][0]['status'], 'accepted')
        self.assertEqual(state['daily']['bookings'][0]['dogId'], 'nino')

    def test_direct_private_endpoints_and_writes_are_denied(self):
        for path in ['/api/finance', '/api/knowledge', '/api/daily', '/api/invites', '/api/documents/'+'a'*32,
                     '/api/finance-documents/'+'a'*64, '/api/blobs/'+'a'*32+'.webm']:
            status, _, _ = _http(self.port, 'GET', path, cookie=self.client)
            self.assertEqual(status, 403, path)
        for path in ['/api/daily', '/api/observations', '/api/knowledge', '/api/finance', '/api/invites']:
            status, _, _ = _http(self.port, 'PUT', path, {}, cookie=self.client)
            self.assertEqual(status, 403, path)
        for path in ['/api/dogs', '/api/documents', '/api/blobs', '/api/import', '/api/portal/members', '/api/portal/decide', '/api/portal/updates', '/api/portal/documents']:
            status, _, _ = _http(self.port, 'POST', path, {}, cookie=self.client)
            self.assertEqual(status, 403, path)
        status, _, _ = _http(self.port, 'GET', '/api/finance-documents/'+'a'*64, cookie=self.carer)
        self.assertEqual(status, 403)
        status, _, _ = _http(self.port, 'POST', '/api/portal/members', {}, cookie=self.carer)
        self.assertEqual(status, 403)
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.carer)
        self.assertEqual(status, 200)
        self.assertIsNone(state['finance'])
        self.assertTrue(state['observations'])

    def test_only_explicit_client_documents_can_be_downloaded(self):
        internal = self.upload('/api/documents')['daily']['documents'][0]
        a = self.upload('/api/portal/documents')['portal']['documents'][0]
        self.upload('/api/portal/documents', 'pablo')
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(state['daily']['documents'], [])
        self.assertEqual([x['id'] for x in state['portal']['documents']], [a['id']])
        status, raw, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.client)
        self.assertEqual(status, 200)
        self.assertIn('synthetic agreement', raw)
        status, _, _ = _http(self.port, 'GET', '/api/documents/'+internal['id'], cookie=self.client)
        self.assertEqual(status, 403)
        status, _, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.other_owner)
        self.assertEqual(status, 404)
        other = self.member(self.client_email, 'client', 'two')
        revoked_status, _, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(revoked_status, 401)
        self.client = self.login(self.client_email)
        status, _, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.client)
        self.assertEqual(status, 404)

    def read_during_membership_reassignment(self, path):
        self.member(self.client_email, 'client', 'one')
        cookie = self.login(self.client_email)
        return self.read_during_access_change(path, cookie, lambda: self.member(self.client_email, 'client', 'two'))

    def read_during_access_change(self, path, cookie, change):
        authenticated = threading.Event()
        resume = threading.Event()
        original = self.server_mod.Handler._need_user

        def pause_after_authentication(handler, *args, **kwargs):
            user = original(handler, *args, **kwargs)
            if (user and handler.path == path and handler.headers.get('Cookie') == f'dc_s={cookie}'
                    and not authenticated.is_set()):
                authenticated.set()
                if not resume.wait(timeout=5):
                    raise TimeoutError('membership reassignment did not finish')
            return user

        with patch.object(self.server_mod.Handler, '_need_user', pause_after_authentication):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(_http, self.port, 'GET', path, cookie=cookie)
                try:
                    self.assertTrue(authenticated.wait(timeout=5), 'protected read did not authenticate')
                    change()
                finally:
                    resume.set()
                result = response.result(timeout=5)
        self.assertEqual(_http(self.port, 'GET', path, cookie=cookie)[0], 401)
        return result

    def test_client_document_read_keeps_family_snapshot_during_membership_reassignment(self):
        own = self.upload('/api/portal/documents')['portal']['documents'][0]
        state = self.upload('/api/portal/documents', 'pablo')
        other = next(doc for doc in state['portal']['documents'] if doc['dogId'] == 'pablo')
        for doc, expected in ((own, 200), (other, 404)):
            with self.subTest(dog=doc['dogId']):
                path = '/api/client-documents/' + doc['id']
                status, body, _ = self.read_during_membership_reassignment(path)
                self.assertEqual(status, expected, body)
                if expected == 200:
                    self.assertIn('synthetic agreement', body)
        cookie = self.login(self.client_email)
        self.assertEqual(_http(self.port, 'GET', '/api/client-documents/' + own['id'], cookie=cookie)[0], 404)
        self.assertEqual(_http(self.port, 'GET', '/api/client-documents/' + other['id'], cookie=cookie)[0], 200)

    def test_dog_reads_keep_family_snapshot_during_membership_reassignment(self):
        paths = [('/api/dogs', 200)]
        for dog, expected in zip(self.daily['dogs'], (200, 404)):
            status, body, _ = _http(self.port, 'POST', '/api/dogs',
                                    {'slug': dog['id'], 'name': dog['name']}, cookie=self.owner)
            self.assertEqual(status, 200, body)
            paths.append(('/api/dogs/' + str(body['dog']['id']), expected))
        for path, expected in paths:
            with self.subTest(path=path):
                status, body, _ = self.read_during_membership_reassignment(path)
                self.assertEqual(status, expected, body)
                if status == 200:
                    dogs = body['dogs'] if path == '/api/dogs' else [body['dog']]
                    self.assertEqual([dog['slug'] for dog in dogs], ['nino'])
        cookie = self.login(self.client_email)
        status, body, _ = _http(self.port, 'GET', '/api/dogs', cookie=cookie)
        self.assertEqual(status, 200, body)
        self.assertEqual([dog['slug'] for dog in body['dogs']], ['pablo'])
        self.assertEqual(_http(self.port, 'GET', paths[1][0], cookie=cookie)[0], 404)
        self.assertEqual(_http(self.port, 'GET', paths[2][0], cookie=cookie)[0], 200)

    def test_public_access_request_does_not_create_an_owner(self):
        email = self.prefix+'-unknown@example.com'
        status, body, _ = _http(self.port, 'POST', '/api/auth/access', {'email': email})
        self.assertEqual((status, body), (200, {'ok': True, 'mailed': False}))
        with self.server_mod.connection() as c:
            self.assertIsNone(c.execute('SELECT id FROM user WHERE email=?', (email,)).fetchone())

    def write_during_access_change(self, method, path, payload, cookie, change, revision_delta=1):
        authenticated = threading.Event()
        resume = threading.Event()
        original = self.server_mod.Handler._need_mutation_user
        _, before, _ = _http(self.port, 'GET', '/api/state', cookie=cookie)
        headers = {'X-DogCare-Business': str(before['business_id']),
                   'If-Match': f'"{before["revision"] + revision_delta}"'}

        def pause_after_authentication(handler, *args, **kwargs):
            user = original(handler, *args, **kwargs)
            if (user and not args and not kwargs and handler.path == path and
                    handler.headers.get('Cookie') == f'dc_s={cookie}' and not authenticated.is_set()):
                authenticated.set()
                if not resume.wait(timeout=5):
                    raise TimeoutError('access change did not finish')
            return user

        with patch.object(self.server_mod.Handler, '_need_mutation_user', pause_after_authentication):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(_http, self.port, method, path, payload, cookie=cookie, headers=headers)
                try:
                    self.assertTrue(authenticated.wait(timeout=5))
                    change()
                    _, unchanged, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
                    self.assertEqual(unchanged['revision'], before['revision'] + revision_delta)
                finally:
                    resume.set()
                status, body, _ = response.result(timeout=5)
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.owner)[1], unchanged)
        return status, body, before

    def test_prefs_write_rechecks_membership_before_mutation_and_projection(self):
        status, body, before = self.write_during_access_change(
            'PUT', '/api/prefs', {'language': 'de'}, self.client,
            lambda: self.member(self.client_email, 'client', 'two'))
        self.assertEqual(status, 401, body)
        with self.server_mod.connection() as c:
            self.assertEqual(c.execute('SELECT language FROM pref JOIN user ON user.id=pref.user_id WHERE email=?',
                                       (self.client_email,)).fetchone()[0], before['language'])

    def revoke(self, email):
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        member = next(m for m in state['portal']['members'] if m['email'] == email)
        status, body, _ = _http(self.port, 'POST', '/api/portal/revoke', {'userId': member['id']}, cookie=self.owner)
        self.assertEqual(status, 200, body)

    def test_client_writes_reject_reassigned_and_revoked_sessions(self):
        from tests.test_media_api import png_fixture, upload_raw

        status, uploaded = upload_raw(self.port, self.owner, png_fixture())
        self.assertEqual(status, 200, uploaded)
        media_id = uploaded['uploadedId']
        cases = [
            ('PUT', '/api/prefs', {'language': 'de'}),
            ('POST', '/api/portal/requests', {'dogId': 'pablo', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': 'stale request'}),
            ('POST', '/api/media/cover', {'dogId': 'nino', 'mediaId': media_id}),
            ('POST', '/api/media/delete', {'id': media_id}),
            ('POST', '/api/auth/logout', {}),
        ]
        for access_change in ('reassign', 'revoke'):
            for method, path, payload in cases:
                with self.subTest(change=access_change, path=path):
                    self.member(self.client_email, 'client', 'one')
                    cookie = self.login(self.client_email)
                    change = (lambda: self.member(self.client_email, 'client', 'two')) if access_change == 'reassign' else (lambda: self.revoke(self.client_email))
                    status, body, _ = self.write_during_access_change(method, path, payload, cookie, change)
                    self.assertEqual(status, 401, body)

    def test_staff_and_owner_writes_reject_revocation_before_the_transaction(self):
        request = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': ''}
        status, requested, _ = _http(self.port, 'POST', '/api/portal/requests', request, cookie=self.client)
        self.assertEqual(status, 200, requested)
        booking_id = requested['portal']['requests'][0]['id']
        extra = {'targetId': booking_id, 'id': '', 'label': 'Synthetic option', 'unitMinor': 100,
                 'currency': 'CHF', 'quantity': 1, 'reusable': False}
        status, priced, _ = _http(self.port, 'POST', '/api/portal/extras', extra, cookie=self.owner)
        self.assertEqual(status, 200, priced)
        extra_id = priced['portal']['quotes'][booking_id]['extras'][0]['id']
        self.assertEqual(_http(self.port, 'POST', '/api/portal/decide', {'id': booking_id, 'status': 'accepted'}, cookie=self.owner)[0], 200)
        status, requested, _ = _http(self.port, 'POST', '/api/portal/requests', {**request, 'service': 'night', 'end': '2026-11-03'}, cookie=self.client)
        self.assertEqual(status, 200, requested)
        pending_id = next(r['id'] for r in requested['portal']['requests'] if r['status'] == 'requested')
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        document = {'dogId': 'nino', 'label': 'Synthetic', 'renewal': '', 'name': 'synthetic.pdf',
                    'type': 'application/pdf', 'data': base64.b64encode(b'%PDF-1.4 synthetic').decode()}
        staff_cases = [
            ('PUT', '/api/observations', {'observations': {}}),
            ('PUT', '/api/daily', {'daily': state['daily']}),
            ('PUT', '/api/knowledge', {'knowledge': state['knowledge']}),
            ('POST', '/api/documents', document),
            ('POST', '/api/dogs', {'slug': 'stale-dog', 'name': 'Stale Dog'}),
            ('POST', '/api/blobs', {'data': base64.b64encode(b'stale recording').decode()}),
            ('POST', '/api/portal/updates', {'dogId': 'nino', 'text': 'stale shared note'}),
            ('POST', '/api/portal/documents', document),
        ]
        owner_cases = [
            ('PUT', '/api/invites', {'invites': []}),
            ('PUT', '/api/finance', {'finance': state['finance'], 'uploads': []}),
            ('POST', '/api/import', {'language': 'de'}),
            ('POST', '/api/portal/members', {'email': self.prefix + '-new@example.com', 'role': 'client', 'clientId': 'one'}),
            ('POST', '/api/portal/revoke', {'userId': state['portal']['members'][0]['id']}),
            ('POST', '/api/portal/decide', {'id': pending_id, 'status': 'accepted'}),
            ('POST', '/api/portal/cancel-booking', {'id': booking_id}),
            ('POST', '/api/portal/quote', {'targetId': pending_id, 'unitMinor': 100, 'currency': 'CHF'}),
            ('POST', '/api/portal/extras', extra),
            ('POST', '/api/portal/extra-remove', {'targetId': booking_id, 'id': extra_id}),
            ('POST', '/api/media/branding', {'hero': None, 'services': {'day': {'face': 'pug'}}}),
        ]
        email = self.prefix + '-carer@example.com'
        for method, path, payload in staff_cases + owner_cases:
            with self.subTest(path=path):
                if (method, path, payload) in staff_cases:
                    self.member(email, 'trusted-carer', None)
                    cookie = self.login(email)
                    change = lambda: self.revoke(email)
                    revision_delta = 1
                else:
                    cookie = self.login(self.prefix + '-owner@example.com')
                    revision_delta = 0
                    def change():
                        self.assertEqual(_http(self.port, 'POST', '/api/auth/logout', {}, cookie=cookie)[0], 200)
                status, body, _ = self.write_during_access_change(method, path, payload, cookie, change, revision_delta)
                self.assertEqual(status, 401, body)
        from pathlib import Path
        self.assertFalse(list(Path(self.server_mod.blobs_dir()).rglob(hashlib.sha256(b'stale recording').hexdigest()[:32] + '.*')))

    def test_mutations_recheck_role_and_business_even_if_session_remains(self):
        email = self.prefix + '-carer@example.com'
        _, before, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        _, other, _ = _http(self.port, 'GET', '/api/state', cookie=self.other_owner)
        for field, value, expected in [('role', 'client', 403), ('business_id', other['business_id'], 409)]:
            with self.subTest(field=field):
                def change():
                    with self.server_mod._lock, self.server_mod.connection() as c:
                        c.execute(f'UPDATE user SET {field}=? WHERE email=?', (value, email))
                status, body, _ = self.write_during_access_change(
                    'POST', '/api/dogs', {'slug': 'stale-dog', 'name': 'Stale Dog'}, self.carer, change, revision_delta=0)
                self.assertEqual(status, expected, body)
                with self.server_mod.connection() as c:
                    c.execute('UPDATE user SET role=?,business_id=? WHERE email=?', ('trusted-carer', before['business_id'], email))
                self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.other_owner)[1], other)

    def test_family_reads_keep_one_snapshot_during_reassignment_and_revocation(self):
        from tests.test_media_api import png_fixture, upload_raw

        document = self.upload('/api/portal/documents', 'pablo')['portal']['documents'][0]
        status, uploaded = upload_raw(self.port, self.owner, png_fixture(), dog='pablo')
        self.assertEqual(status, 200, uploaded)
        media_url = '/api/media/content/' + uploaded['uploadedId']
        paths = ['/api/state', '/api/dogs', '/api/observations', '/api/media', media_url,
                 '/api/client-documents/' + document['id'],
                 '/api/portal/estimate?dogId=pablo&service=day&start=2026-11-02&end=2026-11-02']
        for access_change in ('reassign', 'revoke'):
            for path in paths:
                with self.subTest(change=access_change, path=path):
                    self.member(self.client_email, 'client', 'one')
                    cookie = self.login(self.client_email)
                    before = _http(self.port, 'GET', path, cookie=cookie)[:2]
                    change = (lambda: self.member(self.client_email, 'client', 'two')) if access_change == 'reassign' else (lambda: self.revoke(self.client_email))
                    status, body, _ = self.read_during_access_change(path, cookie, change)
                    self.assertEqual((status, body), before)

    def test_staff_reads_do_not_mix_authenticated_role_with_new_private_records(self):
        from tests.test_media_api import png_fixture, upload_raw

        document = self.upload('/api/documents')['daily']['documents'][0]
        status, blob, _ = _http(self.port, 'POST', '/api/blobs', {'data': base64.b64encode(b'synthetic audio').decode()}, cookie=self.owner)
        self.assertEqual(status, 200, blob)
        status, uploaded = upload_raw(self.port, self.owner, png_fixture())
        self.assertEqual(status, 200, uploaded)
        paths = ['/api/state', '/api/observations', '/api/invites', '/api/dogs', '/api/media',
                 '/api/documents/' + document['id'], '/api/blobs/' + blob['ref']]
        for path in paths:
            with self.subTest(path=path):
                cookie = self.login(self.prefix + '-owner@example.com')
                before = _http(self.port, 'GET', path, cookie=cookie)[:2]
                def change():
                    self.assertEqual(_http(self.port, 'POST', '/api/auth/logout', {}, cookie=cookie)[0], 200)
                    self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': {'nino': [
                        {'id': 901, 'text': 'new private record ' + path}]}}, cookie=self.owner)[0], 200)
                self.assertEqual(self.read_during_access_change(path, cookie, change)[:2], before)

    def test_media_upload_rechecks_access_after_normalization(self):
        from contextlib import contextmanager
        from tests.test_media_api import png_fixture, upload_raw

        original = self.server_mod.media.normalize_upload
        for access_change in ('reassign', 'revoke'):
            with self.subTest(change=access_change):
                self.member(self.client_email, 'client', 'one')
                cookie = self.login(self.client_email)
                normalized = threading.Event()
                resume = threading.Event()

                @contextmanager
                def pause_after_normalization(*args, **kwargs):
                    with original(*args, **kwargs) as value:
                        normalized.set()
                        if not resume.wait(timeout=5):
                            raise TimeoutError('access change did not finish')
                        yield value

                with patch.object(self.server_mod.media, 'normalize_upload', pause_after_normalization):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        response = pool.submit(upload_raw, self.port, cookie, png_fixture())
                        try:
                            self.assertTrue(normalized.wait(timeout=5))
                            if access_change == 'reassign':
                                self.member(self.client_email, 'client', 'two')
                            else:
                                self.revoke(self.client_email)
                            _, before, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
                        finally:
                            resume.set()
                        status, body = response.result(timeout=5)
                self.assertEqual(status, 401, body)
                self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.owner)[1], before)


    def test_quote_rates_freeze_and_owner_extras_persist_without_finance_access(self):
        request = {'dogId':'nino','service':'day','start':'2026-11-02','end':'2026-11-03','note':''}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', request, cookie=self.client)
        self.assertEqual(status, 200, state)
        ident = state['portal']['requests'][0]['id']
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'], 198246)
        # Configured future rates must never reprice an existing request.
        self.daily['rates']['day'] = 123
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':self.daily},cookie=self.owner)[0],200)
        extra = {'targetId':ident,'id':'','label':'Synthetic optional pickup','unitMinor':1250,'currency':'CHF','quantity':2,'reusable':True}
        for user in (self.client,self.carer):
            self.assertEqual(_http(self.port,'POST','/api/portal/extras',extra,cookie=user)[0],403)
        self.assertEqual(_http(self.port,'POST','/api/portal/extras',extra,cookie=self.other_owner)[0],400)
        status, state, _ = _http(self.port,'POST','/api/portal/extras',extra,cookie=self.owner)
        self.assertEqual(status,200,state)
        q = state['portal']['quotes'][ident]
        self.assertEqual(q['totalMinor'],200746)
        self.assertEqual(len(state['portal']['extras']),1)
        eid = q['extras'][0]['id']
        for bad in ({'currency':'EUR'},{'unitMinor':None},{'unitMinor':-1},{'unitMinor':1.5},{'quantity':0},{'quantity':True},{'id':'unknown'}):
            self.assertEqual(_http(self.port,'POST','/api/portal/extras',{**extra,**bad},cookie=self.owner)[0],400,bad)
        status, state, _ = _http(self.port,'POST','/api/portal/extras',{**extra,'id':eid,'quantity':3,'reusable':False},cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],201996)
        status, state, _ = _http(self.port,'POST','/api/portal/decide',{'id':ident,'status':'accepted'},cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['daily']['bookings'][0]['unitMinor'],99123)
        _, state, _ = _http(self.port,'GET','/api/state',cookie=self.client)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],201996)
        self.assertEqual(state['portal']['extras'],[])
        self.assertIsNone(state['finance'])
        self.assertEqual(_http(self.port,'POST','/api/portal/extra-remove',{'targetId':ident,'id':eid},cookie=self.client)[0],403)
        self.assertEqual(_http(self.port,'POST','/api/portal/extra-remove',{'targetId':ident,'id':eid},cookie=self.owner)[0],200)
        self.assertEqual(_http(self.port,'GET','/api/state',cookie=self.client)[1]['portal']['quotes'][ident]['totalMinor'],198246)

    def test_unknown_zero_and_explicit_quote_completion(self):
        request = {'dogId':'nino','service':'night','start':'2026-11-02','end':'2026-11-04','note':''}
        status, state, _ = _http(self.port,'POST','/api/portal/requests',request,cookie=self.client)
        self.assertEqual(status,200,state)
        ident=state['portal']['requests'][0]['id']
        self.assertIsNone(state['portal']['quotes'][ident]['totalMinor'])
        extra={'targetId':ident,'id':'','label':'Synthetic free option','unitMinor':0,'currency':'CHF','quantity':1,'reusable':False}
        status,state,_=_http(self.port,'POST','/api/portal/extras',extra,cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertIsNone(state['portal']['quotes'][ident]['totalMinor'])
        self.assertEqual(state['portal']['quotes'][ident]['extras'][0]['totalMinor'],0)
        price={'targetId':ident,'unitMinor':0,'currency':'CHF'}
        self.assertEqual(_http(self.port,'POST','/api/portal/quote',price,cookie=self.client)[0],403)
        status,state,_=_http(self.port,'POST','/api/portal/quote',price,cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],0)
        self.assertEqual(_http(self.port,'POST','/api/portal/quote',{**price,'unitMinor':99},cookie=self.owner)[0],400)
        # The public projection is empty until explicitly bound to a business.
        from unittest.mock import patch
        with patch.dict('os.environ',{'DC_PUBLIC_BUSINESS':''}):
            self.assertEqual(_http(self.port,'GET','/api/public/services')[1],{'ok':True,'rates':None})
        _,owner,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        with patch.dict('os.environ',{'DC_PUBLIC_BUSINESS':str(owner['business_id'])}):
            public=_http(self.port,'GET','/api/public/services')[1]
            self.assertEqual(public,{'ok':True,'rates':self.daily['rates']})
        query='/api/portal/estimate?dogId=nino&service=day&start=2026-11-02&end=2026-11-03'
        self.assertEqual(_http(self.port,'GET',query,cookie=self.client)[1]['quote']['totalMinor'],198246)
        self.assertEqual(_http(self.port,'GET',query.replace('nino','pablo'),cookie=self.client)[0],403)

    def test_actual_finance_original_and_guessed_dog_ids_remain_private(self):
        _,state,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        value=state['finance']
        blob=b'%PDF-1.4\nPrivate synthetic finance original.\n%%EOF'
        ident=hashlib.sha256(blob).hexdigest()
        value['documents'].append({'id':ident,'sha256':ident,'name':'private.pdf','type':'application/pdf','size':len(blob)})
        status,body,_=_http(self.port,'PUT','/api/finance',{'finance':value,'uploads':[{'id':ident,'data':base64.b64encode(blob).decode()}]},cookie=self.owner)
        self.assertEqual(status,200,body)
        self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=self.owner)[0],200)
        for member in (self.client,self.carer):
            self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=member)[0],403)
        self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=self.other_owner)[0],404)
        for dog in state['dogs']:
            self.assertEqual(_http(self.port,'GET','/api/dogs/'+str(dog['id']),cookie=self.client)[0],404)
        changed={**self.daily,'rates':{**self.daily['rates'],'day':1}}
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':changed},cookie=self.carer)[0],400)

    def test_family_members_share_requests_but_dog_reassignment_does_not_transfer_private_history(self):
        other_family_email=self.prefix+'-second-parent@example.com'
        self.member(other_family_email,'client','one')
        sibling=self.login(other_family_email)
        payload={'dogId':'nino','service':'day','start':'2026-11-02','end':'2026-11-02','note':'Family private request'}
        status,state,_=_http(self.port,'POST','/api/portal/requests',payload,cookie=self.client)
        self.assertEqual(status,200,state)
        ident=state['portal']['requests'][0]['id']
        self.assertEqual(_http(self.port,'GET','/api/state',cookie=sibling)[1]['portal']['requests'][0]['id'],ident)
        self.assertEqual(_http(self.port,'POST','/api/portal/decide',{'id':ident,'status':'accepted'},cookie=self.owner)[0],200)
        doc=self.upload('/api/portal/documents')['portal']['documents'][0]
        self.assertEqual(_http(self.port,'POST','/api/portal/updates',{'dogId':'nino','text':'Private first family news'},cookie=self.owner)[0],200)
        _,owner,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        changed=owner['daily']
        next(d for d in changed['dogs'] if d['id']=='nino')['clientId']='two'
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':changed},cookie=self.owner)[0],200)
        _,saved,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        self.assertEqual(saved['portal']['bookingClients'], {ident:'one'})
        _,original,_=_http(self.port,'GET','/api/state',cookie=self.client)
        self.assertEqual(original['portal']['requests'], [])
        self.assertEqual(original['portal']['quotes'], {})
        self.member(other_family_email,'client','two')
        sibling=self.login(other_family_email)
        _,other,_=_http(self.port,'GET','/api/state',cookie=sibling)
        self.assertIn('nino',[d['id'] for d in other['daily']['dogs']])
        self.assertEqual(other['daily']['bookings'],[])
        self.assertEqual(other['portal']['requests'],[])
        self.assertEqual(other['portal']['documents'],[])
        self.assertEqual(other['portal']['updates'],[])
        self.assertEqual(other['portal']['quotes'],{})
        self.assertEqual(other['portal']['bookingClients'],{})
        self.assertEqual(_http(self.port,'GET','/api/client-documents/'+doc['id'],cookie=sibling)[0],404)
        self.assertEqual(_http(self.port, 'POST', '/api/portal/cancel-booking', {'id': ident}, cookie=self.owner)[0], 200)
        _,original,_=_http(self.port,'GET','/api/state',cookie=self.client)
        self.assertEqual(original['portal']['requests'], [])
        self.assertEqual(original['portal']['quotes'], {})

    def reassigned_pending_request(self):
        payload = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02',
                   'note': 'Original family request'}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', payload, cookie=self.client)
        self.assertEqual(status, 200, state)
        request = state['portal']['requests'][0]
        extra = {'targetId': request['id'], 'id': '', 'label': 'Original family option', 'unitMinor': 1250,
                 'currency': 'CHF', 'quantity': 2, 'reusable': False}
        status, state, _ = _http(self.port, 'POST', '/api/portal/extras', extra, cookie=self.owner)
        self.assertEqual(status, 200, state)
        quote = state['portal']['quotes'][request['id']]
        changed = state['daily']
        next(d for d in changed['dogs'] if d['id'] == 'nino').update(clientId='two', name='New family dog name')
        changed['rates']['day'] = 100
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': changed}, cookie=self.owner)
        self.assertEqual(status, 200, state)
        email = self.prefix + '-new-family@example.com'
        self.member(email, 'client', 'two')
        return request, quote, self.login(email)

    def test_reassigned_pending_request_stays_with_original_family_projection(self):
        request, quote, family_two = self.reassigned_pending_request()
        payload = {'dogId': 'nino', 'service': 'walk', 'start': '2026-11-03', 'end': '2026-11-03',
                   'note': 'New family request'}
        status, new_state, _ = _http(self.port, 'POST', '/api/portal/requests', payload, cookie=family_two)
        self.assertEqual(status, 200, new_state)
        newer = new_state['portal']['requests'][0]
        self.upload('/api/portal/documents')
        self.assertEqual(_http(self.port, 'POST', '/api/portal/updates',
                               {'dogId': 'nino', 'text': 'New family news'}, cookie=self.owner)[0], 200)
        status, original, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(status, 200, original)
        self.assertEqual(original['portal']['requests'], [request])
        self.assertEqual(original['portal']['quotes'], {request['id']: quote})
        self.assertEqual(original['dogs'], [])
        self.assertEqual(original['daily']['dogs'], [])
        self.assertEqual(original['daily']['bookings'], [])
        self.assertEqual(original['portal']['updates'], [])
        self.assertEqual(original['portal']['documents'], [])
        self.assertNotIn('New family', str(original))
        status, new_state, _ = _http(self.port, 'GET', '/api/state', cookie=family_two)
        self.assertEqual(status, 200, new_state)
        self.assertEqual(new_state['portal']['requests'], [newer])
        self.assertEqual(set(new_state['portal']['quotes']), {newer['id']})
        self.assertNotIn('Original family', str(new_state))

    def test_owner_can_decline_reassigned_request_but_cannot_accept_it(self):
        request, quote, family_two = self.reassigned_pending_request()
        _, before, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        for decision in ('accepted', 'declined'):
            for cookie, expected in ((self.client, 403), (family_two, 403), (self.other_owner, 400)):
                with self.subTest(decision=decision, expected=expected):
                    status, _, _ = _http(self.port, 'POST', '/api/portal/decide',
                                         {'id': request['id'], 'status': decision}, cookie=cookie)
                    self.assertEqual(status, expected)
        status, _, _ = _http(self.port, 'POST', '/api/portal/decide',
                             {'id': request['id'], 'status': 'accepted'}, cookie=self.owner)
        self.assertEqual(status, 400)
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.owner)[1], before)
        status, declined, _ = _http(self.port, 'POST', '/api/portal/decide',
                                    {'id': request['id'], 'status': 'declined'}, cookie=self.owner)
        self.assertEqual(status, 200, declined)
        self.assertEqual(declined['daily'], before['daily'])
        self.assertEqual(declined['finance'], before['finance'])
        self.assertEqual(declined['portal']['requests'], [{**request, 'status': 'declined'}])
        self.assertEqual(declined['portal']['quotes'], {request['id']: quote})
        self.assertEqual(declined['portal']['bookingClients'], {})
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.owner)[1], declined)
        _, original, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(original['portal']['requests'], declined['portal']['requests'])
        self.assertEqual(original['portal']['quotes'], {request['id']: quote})
        self.assertEqual(original['dogs'], [])
        self.assertEqual(original['daily']['dogs'], [])
        self.assertEqual(original['daily']['bookings'], [])
        _, other, _ = _http(self.port, 'GET', '/api/state', cookie=family_two)
        self.assertEqual(other['portal']['requests'], [])
        self.assertEqual(other['portal']['quotes'], {})
        self.assertEqual(other['daily']['bookings'], [])
        for decision in ('accepted', 'declined'):
            self.assertEqual(_http(self.port, 'POST', '/api/portal/decide',
                                   {'id': request['id'], 'status': decision}, cookie=self.owner)[0], 400)

    def test_carer_bookings_receive_stored_rates_without_price_editing(self):
        import copy
        value = copy.deepcopy(self.daily)
        value['bookings'] = [
            {'id': 'priced', 'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'unitMinor': None, 'currency': 'CHF'},
            {'id': 'unknown', 'dogId': 'nino', 'service': 'walk', 'start': '2026-11-02', 'end': '2026-11-02', 'unitMinor': None, 'currency': 'CHF'},
        ]
        forged = copy.deepcopy(value)
        forged['bookings'][0]['unitMinor'] = 99123
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=self.carer)[0], 400)
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.carer)
        self.assertEqual(status, 200, state)
        self.assertEqual([b['unitMinor'] for b in state['daily']['bookings']], [99123, None])
        value = state['daily']
        value['rates']['day'] = 12345
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.owner)[0], 200)
        value['bookings'][0]['end'] = '2026-11-03'
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.carer)
        self.assertEqual(status, 200, state)
        self.assertEqual(state['daily']['bookings'][0]['unitMinor'], 99123)
        for amount in (0, None, 12345):
            forged = copy.deepcopy(state['daily'])
            forged['bookings'][0]['unitMinor'] = amount
            self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=self.carer)[0], 400)

    def test_request_ids_cannot_be_created_as_manual_bookings(self):
        self.member(self.prefix + '-family-two@example.com', 'client', 'two')
        family_two = self.login(self.prefix + '-family-two@example.com')
        request = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': ''}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', request, cookie=self.client)
        self.assertEqual(status, 200, state)
        ident = state['portal']['requests'][0]['id']
        extra = {'targetId': ident, 'id': '', 'label': 'Private first-family pickup', 'unitMinor': 1250,
                 'currency': 'CHF', 'quantity': 2, 'reusable': False}
        status, state, _ = _http(self.port, 'POST', '/api/portal/extras', extra, cookie=self.owner)
        self.assertEqual(status, 200, state)
        quote = state['portal']['quotes'][ident]
        current = state['daily']
        current['rates']['day'] = 12345
        status, before, _ = _http(self.port, 'PUT', '/api/daily', {'daily': current}, cookie=self.owner)
        self.assertEqual(status, 200, before)
        forged = copy.deepcopy(current)
        forged['bookings'].append({'id': ident, 'dogId': 'pablo', 'service': 'day', 'start': request['start'],
                                   'end': request['end'], 'unitMinor': None, 'currency': 'CHF'})
        for cookie in (self.carer, self.owner):
            with self.subTest(role='carer' if cookie == self.carer else 'owner'):
                status, body, _ = _http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=cookie)
                self.assertEqual(status, 400, body)
        _, after, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['daily'], before['daily'])
        self.assertEqual(after['portal'], before['portal'])
        _, other, _ = _http(self.port, 'GET', '/api/state', cookie=family_two)
        self.assertEqual(other['daily']['bookings'], [])
        self.assertEqual(other['portal']['quotes'], {})
        self.assertNotIn(extra['label'], str(other))
        status, accepted, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': ident, 'status': 'accepted'}, cookie=self.owner)
        self.assertEqual(status, 200, accepted)
        self.assertEqual(accepted['portal']['quotes'][ident], quote)
        self.assertEqual(accepted['portal']['bookingClients'], {ident: 'one'})
        self.assertEqual(accepted['daily']['bookings'][0]['dogId'], 'nino')
        current = accepted['daily']
        current['bookings'][0]['end'] = '2026-11-03'
        status, updated, _ = _http(self.port, 'PUT', '/api/daily', {'daily': current}, cookie=self.carer)
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated['daily']['bookings'][0]['unitMinor'], quote['unitMinor'])
        self.assertEqual(updated['portal']['quotes'][ident]['extras'], quote['extras'])
        status, foreign, _ = _http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=self.other_owner)
        self.assertEqual(status, 200, foreign)
        self.assertEqual(foreign['portal']['quotes'][ident]['extras'], [])

    def test_request_id_reservation_survives_decision_without_a_booking(self):
        request = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': ''}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', request, cookie=self.client)
        self.assertEqual(status, 200, state)
        ident = state['portal']['requests'][0]['id']
        status, state, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': ident, 'status': 'declined'}, cookie=self.owner)
        self.assertEqual(status, 200, state)
        forged = copy.deepcopy(state['daily'])
        forged['bookings'].append({'id': ident, 'dogId': 'nino', 'service': 'day', 'start': request['start'],
                                   'end': request['end'], 'unitMinor': None, 'currency': 'CHF'})
        for decision in ('declined', 'accepted'):
            with self.subTest(decision=decision):
                with self.server_mod.connection() as c:
                    c.execute('UPDATE booking_request SET status=? WHERE business_id=? AND id=?',
                              (decision, state['business_id'], ident))
                for cookie in (self.carer, self.owner):
                    status, body, _ = _http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=cookie)
                    self.assertEqual(status, 400, body)
                _, reloaded, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
                self.assertEqual(reloaded['daily'], state['daily'])
                self.assertEqual(reloaded['revision'], state['revision'])

    def test_quote_extras_lookup_indexes_business_and_target(self):
        import quotes
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.owner)
        item = {'id': 'target', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02',
                'unitMinor': 100, 'currency': 'CHF'}
        with self.server_mod.connection() as c:
            statements = []
            c.set_trace_callback(statements.append)
            quotes.quote(c, state['business_id'], item, booking=True)
            c.set_trace_callback(None)
            query = next(sql for sql in statements if 'FROM booking_extra' in sql)
            plan = ' '.join(row['detail'] for row in c.execute('EXPLAIN QUERY PLAN ' + query))
        self.assertIn('business_id=? AND target_id=?', plan)
        self.assertNotIn('TEMP B-TREE', plan)
