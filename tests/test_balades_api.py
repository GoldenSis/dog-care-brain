"""Balades: staff-only access, own revision guard, shared validation limits."""
import copy
import json
import uuid

from tests.test_tenant_isolation import ApiServerTestCase, _http


def track(**over):
    value = {'id': 'walk-1', 'name': 'Parc de Saint-Cloud', 'date': '2026-10-21', 'dogs': ['nino'],
             'points': [[48.8402, 2.219, 1792900000], [48.8411, 2.2205, 1792900060]], 'durationSec': 60,
             'source': 'record', 'walkRefs': [{'date': '2026-10-21', 'dogId': 'nino'}],
             'spots': [{'id': 's1', 'type': 'tolere', 'lat': 48.84, 'lon': 2.22, 'note': 'Calmes sans laisse le matin',
                        'rule': 'Laisse obligatoire', 'noted': '2026-10-20'}]}
    value.update(over)
    return value


class BaladesApiTest(ApiServerTestCase):
    def setUp(self):
        prefix = uuid.uuid4().hex
        self.owner = self.login(prefix + '-owner@example.com')
        daily = {'version': 1, 'clients': [{'id': 'one', 'name': 'Family'}], 'dogs': [{'id': 'nino', 'name': 'Nino', 'clientId': 'one'}],
                 'bookings': [], 'rates': {'currency': 'CHF', 'day': None, 'night': None, 'walk': None}, 'documents': []}
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': daily}, cookie=self.owner)[0], 200)
        self.business = str(self.get(self.owner)[1]['business_id'])
        self.roles = {}
        for role, client in (('trusted-carer', None), ('client', 'one')):
            email = f'{prefix}-{role}@example.com'
            self.assertEqual(_http(self.port, 'POST', '/api/portal/members', {'email': email, 'role': role, 'clientId': client}, cookie=self.owner)[0], 200)
            self.roles[role] = self.login(email)
        notes = {'nino': [{'id': 1, 'title': 'Shared note', 'text': 'Quiet walk.', 'date': '2026-10-08'}]}
        self.assertEqual(_http(self.port, 'PUT', '/api/observations', {'observations': notes}, cookie=self.owner)[0], 200)
        catalog = _http(self.port, 'GET', '/api/state', cookie=self.owner)[1]['portal']['shareCatalog']
        key = next(r['key'] for r in catalog if r['key'].startswith('note:nino:1'))
        email = prefix + '-pro@example.com'
        self.assertEqual(_http(self.port, 'POST', '/api/portal/professionals', {'email': email, 'dogIds': ['nino'], 'recordKeys': [key]}, cookie=self.owner)[0], 200)
        self.roles['professional'] = self.login(email)

    def get(self, cookie):
        return _http(self.port, 'GET', '/api/balades', cookie=cookie)

    def put(self, cookie, value, revision):
        return _http(self.port, 'PUT', '/api/balades', {'balades': value}, cookie,
                     {'X-DogCare-Business': self.business, 'If-Match': f'"{revision}"'})

    def test_staff_write_and_read_others_denied(self):
        status, body, _ = self.get(self.owner)
        self.assertEqual((status, body['revision'], body['balades']), (200, 0, {'version': 1, 'tracks': []}))
        care_revision = _http(self.port, 'GET', '/api/state', cookie=self.owner)[1]['revision']
        value = {'version': 1, 'tracks': [track()]}
        status, body, _ = self.put(self.owner, value, 0)
        self.assertEqual((status, body['revision'], body['balades']), (200, 1, value))
        self.assertEqual(_http(self.port, 'GET', '/api/state', cookie=self.owner)[1]['revision'], care_revision)
        self.assertNotIn('balades', _http(self.port, 'GET', '/api/state', cookie=self.owner)[1])
        carer = self.roles['trusted-carer']
        self.assertEqual(self.get(carer)[1]['balades'], value)
        value['tracks'][0]['name'] = 'Renamed by carer'
        self.assertEqual(self.put(carer, value, 1)[0], 200)
        for role in ('client', 'professional'):
            with self.subTest(role=role):
                self.assertEqual(self.get(self.roles[role])[0], 403)
                self.assertEqual(self.put(self.roles[role], {'version': 1, 'tracks': []}, 2)[0], 403)
                self.assertNotIn('Saint-Cloud', str(_http(self.port, 'GET', '/api/state', cookie=self.roles[role])[1]))
        self.assertEqual(self.get(None)[0], 401)
        self.assertEqual(self.get(self.owner)[1]['balades']['tracks'][0]['name'], 'Renamed by carer')

    def test_stale_revision_and_limits_rejected_without_writing(self):
        value = {'version': 1, 'tracks': [track()]}
        self.assertEqual(self.put(self.owner, value, 0)[0], 200)
        status, body, _ = self.put(self.owner, {'version': 1, 'tracks': []}, 0)
        self.assertEqual((status, body.get('conflict')), (409, True))
        self.assertEqual(_http(self.port, 'PUT', '/api/balades', {'balades': value}, self.owner, {'X-DogCare-Business': self.business})[0], 428)
        spot = track()['spots'][0]
        bad = [track(points=[[48, 2, None]]), track(points=[[48 + i * 1e-5, 2, None] for i in range(20001)]),
               track(spots=[dict(spot, id=f's{i}', type='pause', rule='') for i in range(201)]),
               track(spots=[dict(spot, type='danger')]), track(spots=[dict(spot, note='x' * 501)]),
               track(walkRefs=[{'date': '2026-10-21', 'dogId': 'other'}]), dict(track(), extra=1)]
        for item in bad:
            with self.subTest(item=str(item)[:60]):
                self.assertEqual(self.put(self.owner, {'version': 1, 'tracks': [item]}, 1)[0], 400)
        many = [track(id=f't{i}', walkRefs=[]) for i in range(501)]
        self.assertEqual(self.put(self.owner, {'version': 1, 'tracks': many}, 1)[0], 400)
        self.assertEqual(self.get(self.owner)[1], {'ok': True, 'business_id': int(self.business), 'revision': 1, 'balades': value})
        other = self.login(uuid.uuid4().hex + '-other@example.com')
        self.assertEqual(self.get(other)[1]['balades'], {'version': 1, 'tracks': []})
        changed = copy.deepcopy(value)
        self.assertEqual(_http(self.port, 'PUT', '/api/balades', {'balades': changed}, other, {'X-DogCare-Business': self.business, 'If-Match': '"1"'})[0], 409)

    def test_aggregate_utf8_capacity_includes_spot_text(self):
        import balades
        spots = [dict(track()['spots'][0], id=f's{i}', note='é' * 500, rule='é' * 500) for i in range(200)]
        value = {'version': 1, 'tracks': [track(id=f't{i}', walkRefs=[], spots=spots) for i in range(80)]}
        encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        self.assertLess(len(encoded), 30 * 1024 * 1024)
        self.assertGreater(len(encoded.encode('utf-8')), 30 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, 'tooLarge'):
            balades.validate(value)
        value['tracks'] = value['tracks'][:40]
        self.assertEqual(balades.validate(value), value)
