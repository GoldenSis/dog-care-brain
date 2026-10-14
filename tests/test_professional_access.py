"""Selected professional grants, direct file denial and revocation; isolated data."""
import base64
import copy
import json
import uuid

from tests.test_tenant_isolation import ApiServerTestCase, _http, _latest_link
from tests.test_media_api import png_fixture, upload_raw, read_raw


class ProfessionalAccessTest(ApiServerTestCase):
    def setUp(self):
        prefix = uuid.uuid4().hex
        self.owner_email = prefix + '-owner@example.com'
        self.owner = self.login(self.owner_email)
        self.other_email = prefix + '-other@example.com'
        self.other = self.login(self.other_email)
        self.email = prefix + '-professional@example.com'
        self.daily = {'version': 1, 'clients': [{'id': 'a', 'name': 'Private family A'}, {'id': 'b', 'name': 'Private family B'}],
                      'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'a'}, {'id': 'pablo', 'name': 'Private Pablo', 'clientId': 'b'}],
                      'bookings': [], 'rates': {'currency': 'CHF', 'day': 99123, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': self.daily}, cookie=self.owner)[0], 200)
        self.notes = {'nino': [{'id': 1, 'title': 'Selected daily note', 'text': 'Observed a quiet walk.', 'date': '2026-10-08'},
                               {'id': 2, 'title': 'Private internal note', 'text': 'Not chosen for sharing.'}],
                      'pablo': [{'id': 3, 'title': 'Other dog private note', 'text': 'Other family private information.'}]}
        self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': self.notes}, cookie=self.owner)[0], 200)
        self.client_email = prefix + '-family@example.com'
        self.assertEqual(_http(self.port, 'POST', '/api/portal/members',
                               {'email': self.client_email, 'role': 'client', 'clientId': 'a'}, cookie=self.owner)[0], 200)
        self.client = self.login(self.client_email)

    def state(self, cookie=None):
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=cookie or self.owner)
        self.assertEqual(status, 200, state)
        return state

    def grant(self, keys=None, dogs=None, email=None, owner=None):
        catalog = self.state()['portal']['shareCatalog']
        keys = keys if keys is not None else ['note:nino:1']
        keys = [next((r['key'] for r in catalog if r['key'].startswith(k + ':')), k) for k in keys]
        return _http(self.port, 'POST', '/api/portal/professionals',
                     {'email': email or self.email, 'dogIds': dogs if dogs is not None else ['nino'],
                      'recordKeys': keys}, cookie=owner or self.owner)

    def invite(self, keys=None):
        status, body, _ = self.grant(keys)
        self.assertEqual(status, 200, body)
        return self.login(self.email)

    def document(self, dog='nino', shared=False):
        path = '/api/portal/documents' if shared else '/api/documents'
        body = {'dogId': dog, 'label': 'Selected record', 'renewal': '', 'name': 'synthetic.pdf',
                'type': 'application/pdf', 'data': base64.b64encode(b'%PDF-1.4 synthetic selected record').decode()}
        status, result, _ = _http(self.port, 'POST', path, body, cookie=self.owner)
        self.assertEqual(status, 200, result)
        candidates = result['portal']['shareCatalog']
        return next(r for r in reversed(candidates) if r['dogId'] == dog and r['key'].startswith('client-document:' if shared else 'document:'))

    def test_exact_projection_and_existing_clients_preserved(self):
        cookie = self.invite()
        state = self.state(cookie)
        self.assertEqual(state['role'], 'professional')
        self.assertEqual([d['name'] for d in state['dogs']], ['Nino'])
        self.assertEqual(state['daily']['clients'], [])
        self.assertEqual(state['daily']['bookings'], [])
        self.assertIsNone(state['daily']['rates']['day'])
        self.assertEqual(state['observations'], {})
        self.assertIsNone(state['finance'])
        self.assertIsNone(state['knowledge'])
        self.assertEqual(len(state['portal']['sharedRecords']), 1)
        self.assertTrue(state['portal']['sharedRecords'][0]['key'].startswith('note:nino:1:'))
        for private in ('Private family', 'Private Pablo', 'Private internal', 'Other dog private', '99123', self.client_email):
            self.assertNotIn(private, json.dumps(state))
        self.assertEqual(self.state(self.client)['portal']['members'], [])
        self.assertNotIn('sharedRecords', self.state(self.client)['portal'])
        self.assertEqual(self.state()['role'], 'owner')
        self.assertEqual(self.state(self.other)['role'], 'owner')
        _, dog_rows, _ = _http(self.port, 'GET', '/api/dogs', cookie=self.owner)
        for d in dog_rows['dogs']:
            status = _http(self.port, 'GET', '/api/dogs/' + str(d['id']), cookie=cookie)[0]
            self.assertEqual(status, 200 if d['slug'] == 'nino' else 404)

    def test_notes_are_explicit_shared_versions_not_future_edits(self):
        cookie = self.invite()
        selected_key = self.state(cookie)['portal']['sharedRecords'][0]['key']
        notes = copy.deepcopy(self.notes)
        notes['nino'][0]['text'] = 'A later private edit not selected.'
        self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': notes}, cookie=self.owner)[0], 200)
        self.assertEqual(self.state(cookie)['portal']['sharedRecords'][0]['text'], 'Observed a quiet walk.')
        self.assertEqual(self.grant([selected_key])[0], 400)
        self.assertEqual(self.state()['portal']['professionals'][0]['sharedRecords'][0]['text'], 'Observed a quiet walk.')
        self.assertEqual(self.grant()[0], 200)
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=cookie)[0], 401)
        fresh = self.login(self.email)
        self.assertEqual(self.state(fresh)['portal']['sharedRecords'][0]['text'], notes['nino'][0]['text'])

    def test_only_selected_documents_and_media_are_readable(self):
        chosen = self.document()
        unchosen = self.document('pablo')
        family_doc = self.document(shared=True)
        status, uploaded = upload_raw(self.port, self.owner, png_fixture())
        self.assertEqual(status, 200, uploaded)
        media_id = uploaded['uploadedId']
        status, other = upload_raw(self.port, self.owner, png_fixture((20, 40, 60)))
        self.assertEqual(status, 200, other)
        cookie = self.invite([chosen['key'], family_doc['key'], 'media:' + media_id])
        for record in (chosen, family_doc):
            self.assertEqual(read_raw(self.port, record['href'], cookie)[0], 200)
        self.assertEqual(read_raw(self.port, unchosen['href'], cookie)[0], 403)
        self.assertEqual(read_raw(self.port, '/api/media/content/' + media_id, cookie)[:2], (200, png_fixture()))
        self.assertEqual(read_raw(self.port, '/api/media/content/' + other['uploadedId'], cookie)[0], 404)
        self.assertEqual([m['id'] for m in self.state(cookie)['media']['items']], [media_id])
        self.assertEqual(read_raw(self.port, chosen['href'], self.client)[0], 403)
        self.assertEqual(read_raw(self.port, chosen['href'], self.other)[0], 404)

    def test_direct_private_endpoints_and_all_care_writes_denied(self):
        cookie = self.invite()
        for path in ('/api/finance', '/api/knowledge', '/api/daily', '/api/invites',
                     '/api/finance-documents/' + 'a' * 64, '/api/blobs/' + 'a' * 32 + '.webm'):
            self.assertEqual(_http(self.port, 'GET', path, cookie=cookie)[0], 403, path)
        for method, paths in [('PUT', ('daily', 'knowledge', 'finance', 'observations', 'invites')),
                              ('POST', ('dogs', 'documents', 'blobs', 'import', 'portal/members', 'portal/professionals',
                                        'portal/revoke', 'portal/requests', 'portal/updates', 'portal/documents',
                                        'media/cover', 'media/delete', 'media/branding'))]:
            for path in paths:
                self.assertEqual(_http(self.port, method, '/api/' + path, {}, cookie=cookie)[0], 403, path)
        self.assertEqual(upload_raw(self.port, cookie, png_fixture())[0], 403)
        self.assertEqual(_http(self.port, 'PUT', '/api/prefs', {'language': 'fr'}, cookie=cookie)[0], 200)

    def test_scope_validation_and_account_ownership(self):
        for keys, dogs in [(['note:pablo:3'], ['nino']), (['unknown'], ['nino']), ([], ['unknown']), ([], []),
                           (['note:nino:1', 'note:nino:1'], ['nino'])]:
            self.assertEqual(self.grant(keys, dogs)[0], 400)
        for email in (self.owner_email, self.other_email, self.client_email):
            self.assertEqual(self.grant(email=email)[0], 400)
        self.assertEqual(self.grant(owner=self.client)[0], 403)
        self.assertEqual(_http(self.port, 'POST', '/api/portal/professionals', {})[0], 401)

    def test_revocation_ends_session_and_pending_login_and_files(self):
        doc = self.document()
        cookie = self.invite([doc['key']])
        _http(self.port, 'POST', '/api/auth/request', {'email': self.email})
        pending = _latest_link(self.outbox, self.email)
        from urllib.parse import urlparse
        user = self.state()['portal']['professionals'][0]
        self.assertEqual(_http(self.port, 'POST', '/api/portal/revoke', {'userId': user['id']}, cookie=self.owner)[0], 200)
        self.assertEqual(read_raw(self.port, doc['href'], cookie)[0], 401)
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=cookie)[0], 401)
        parsed = urlparse(pending)
        _, _, headers = _http(self.port, 'GET', parsed.path + '?' + parsed.query)
        self.assertNotIn('signin=ok', headers.get('location', ''))
        self.assertEqual(self.state()['portal']['professionals'], [])

    def test_reassignment_and_delete_recreate_end_grants(self):
        doc = self.document()
        cookie = self.invite([doc['key'], 'note:nino:1'])
        state = self.state()
        changed = state['daily']
        changed['dogs'][0]['clientId'] = 'b'
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': changed}, cookie=self.owner)[0], 200)
        self.assertEqual(self.state(cookie)['dogs'], [])
        self.assertEqual(read_raw(self.port, doc['href'], cookie)[0], 403)
        changed['dogs'][0]['clientId'] = 'a'
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': changed}, cookie=self.owner)[0], 200)
        self.assertEqual(self.state(cookie)['dogs'], [])
        self.assertEqual(self.grant([])[0], 200)
        cookie = self.login(self.email)
        # A dog with an immutable document cannot be removed: exercise deletion
        # on another explicitly granted dog without documents/bookings.
        self.assertEqual(self.grant([], ['pablo'])[0], 200)
        cookie = self.login(self.email)
        changed['dogs'] = changed['dogs'][:1]
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': changed}, cookie=self.owner)[0], 200)
        changed['dogs'].append({'id': 'pablo', 'name': 'A new dog', 'clientId': 'b'})
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': changed}, cookie=self.owner)[0], 200)
        self.assertEqual(self.state(cookie)['dogs'], [])

    def test_reads_and_prefs_keep_one_grant_during_concurrent_access_change(self):
        # Reuse the deterministic transaction barriers without inheriting the
        # unrelated client suite. In-flight reads may finish their old snapshot.
        from tests import test_client_portal
        helper = test_client_portal.ClientPortalTest
        doc = self.document()
        _, uploaded = upload_raw(self.port, self.owner, png_fixture())
        paths = ('/api/state', '/api/dogs', doc['href'], '/api/media')
        for path in paths:
            with self.subTest(path=path):
                cookie = self.invite([doc['key'], 'note:nino:1', 'media:' + uploaded['uploadedId']])
                before = _http(self.port, 'GET', path, cookie=cookie)[:2]
                during = helper.read_during_access_change(
                    self, path, cookie, lambda: self.grant(['note:pablo:3'], ['pablo']))[:2]
                self.assertEqual(during, before)
                self.assertNotIn('Private Pablo', json.dumps(during))
        cookie = self.invite()
        status, _, _ = helper.write_during_access_change(
            self, 'PUT', '/api/prefs', {'language': 'de'}, cookie,
            lambda: self.grant(['note:pablo:3'], ['pablo']))
        self.assertEqual(status, 401)
        self.assertEqual(self.state(self.login(self.email))['language'], 'fr')
