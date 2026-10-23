"""Business weather preferences keep existing role and snapshot-write boundaries."""
import copy
import os
import sqlite3
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


class WeatherApiTest(ApiServerTestCase):
    def account(self, suffix='owner'):
        return self.login(f'{self._testMethodName}-{suffix}@example.test')

    def state(self, cookie):
        status, body, _ = _http(self.port, 'GET', '/api/state', cookie=cookie)
        self.assertEqual(status, 200, body)
        return body

    def settings(self):
        return {'location': {'name': 'Lausanne', 'latitude': 46.5197, 'longitude': 6.6323},
                'heatThreshold': 25}

    def save(self, cookie, value, expected=200, headers=None):
        status, body, _ = _http(self.port, 'PUT', '/api/weather-settings',
                                {'weatherSettings': value}, cookie, headers)
        self.assertEqual(status, expected, body)
        return body

    def headers(self, state):
        return {'X-DogCare-Business': str(state['business_id']),
                'If-Match': f'"{state["revision"]}"'}

    def test_save_reload_clear_preserves_care_and_closes_legacy_import(self):
        owner = self.account()
        other = self.account('other')
        before = self.state(owner)
        other_before = self.state(other)
        self.assertEqual(before['weatherSettings'], {'location': None, 'heatThreshold': 25})
        self.assertFalse(before['imported'])
        value = self.settings()
        saved = self.save(owner, value)
        self.assertEqual(saved['weatherSettings'], value)
        self.assertEqual(saved['revision'], before['revision'] + 1)
        self.assertTrue(saved['imported'])
        for key in ('daily', 'observations', 'dogs', 'invites', 'language', 'finance', 'knowledge'):
            self.assertEqual(saved[key], before[key])
        self.assertEqual(self.state(owner), saved)
        self.assertEqual(self.state(other), other_before)
        status, body, _ = _http(self.port, 'POST', '/api/import', {'language': 'it'}, owner)
        self.assertEqual(status, 200, body)
        self.assertTrue(body['skipped'])
        self.assertEqual(body['weatherSettings'], value)
        self.assertEqual(body['language'], saved['language'])
        # Clearing a location is explicit and does not reset the owner's threshold.
        cleared = {'location': None, 'heatThreshold': 27.5}
        self.save(owner, cleared)
        self.assertEqual(self.state(owner)['weatherSettings'], cleared)

    def test_only_owner_writes_and_only_staff_read_location(self):
        owner = self.account()
        daily = self.state(owner)['daily']
        daily.update(clients=[{'id': 'family', 'name': 'Family'}],
                     dogs=[{'id': 'dog', 'name': 'Dog', 'clientId': 'family', 'walkTariff': None}])
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': daily}, owner)[0], 200)
        value = self.settings()
        self.save(owner, value)
        for role in ('trusted-carer', 'client', 'professional'):
            with self.subTest(role=role):
                email = f'{self._testMethodName}-{role}@example.test'
                if role == 'professional':
                    route = '/api/portal/professionals'
                    member = {'email': email, 'dogIds': ['dog'], 'recordKeys': []}
                else:
                    route = '/api/portal/members'
                    member = {'email': email, 'role': role, 'clientId': 'family' if role == 'client' else None}
                self.assertEqual(_http(self.port, 'POST', route, member, owner)[0], 200)
                cookie = self.login(email)
                current = self.state(cookie)
                self.assertEqual(current['weatherSettings'], value if role == 'trusted-carer' else None)
                before = self.state(owner)
                self.save(cookie, {'location': None, 'heatThreshold': 30}, expected=403)
                self.assertEqual(self.state(owner), before)
        self.save(None, value, expected=401)

    def test_business_and_shared_revision_guards_reject_stale_writes(self):
        owner = self.account()
        other = self.account('other')
        before = self.state(owner)
        other_before = self.state(other)
        headers = self.headers(before)
        self.save(owner, self.settings(), expected=428, headers={})
        self.save(owner, self.settings(), expected=428,
                  headers={'X-DogCare-Business': str(before['business_id'])})
        self.save(other, self.settings(), expected=409, headers=headers)
        self.assertEqual(self.state(owner), before)
        self.assertEqual(self.state(other), other_before)
        # A daily edit uses the same revision, so it invalidates a weather draft.
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': before['daily']}, owner)[0], 200)
        after_daily = self.state(owner)
        self.save(owner, self.settings(), expected=409, headers=headers)
        self.assertEqual(self.state(owner), after_daily)
        saved = self.save(owner, self.settings())
        self.save(owner, {'location': None, 'heatThreshold': 30}, expected=409, headers=self.headers(after_daily))
        self.assertEqual(self.state(owner), saved)

    def test_invalid_numbers_fields_and_names_leave_snapshot_revision_and_import_unchanged(self):
        owner = self.account()
        before = self.state(owner)
        invalid = [None, [], {}, {'location': None}, dict(self.settings(), extra=True)]
        for threshold in (True, False, None, '25', [], -0.1, 50.1, float('nan'), float('inf'), -float('inf'), 10**400):
            invalid.append(dict(self.settings(), heatThreshold=threshold))
        for key, values in (('latitude', (True, '46', -90.1, 90.1, float('nan'), float('inf'), 10**400)),
                            ('longitude', (False, None, -180.1, 180.1, float('nan'), -float('inf'))),
                            ('name', ('', ' ', 'x' * 121, 'City\nOther', 'City\x7f', 12))):
            for value in values:
                item = self.settings()
                item['location'][key] = value
                invalid.append(item)
        for location in ({}, [], {'name': 'City', 'latitude': 1}, dict(self.settings()['location'], dog='private')):
            invalid.append(dict(self.settings(), location=location))
        for value in invalid:
            with self.subTest(value=str(value)[:100]):
                self.save(owner, value, expected=400)
                self.assertEqual(self.state(owner), before)
        for payload in ({}, {'weatherSettings': self.settings(), 'dog': 'private'}):
            self.assertEqual(_http(self.port, 'PUT', '/api/weather-settings', payload, owner)[0], 400)
            self.assertEqual(self.state(owner), before)
        for latitude, longitude, threshold in ((-90, -180, 0), (90, 180, 50)):
            value = {'location': {'name': 'X' * 119 + '🐕', 'latitude': latitude, 'longitude': longitude},
                     'heatThreshold': threshold}
            self.assertEqual(self.save(owner, value)['weatherSettings'], value)

    def test_database_failure_rolls_back_write_revision_and_import(self):
        owner = self.account()
        before = self.state(owner)
        save = self.server_mod.weather_settings.save

        def fail_after_save(connection, business_id, value):
            save(connection, business_id, value)
            raise sqlite3.OperationalError('fixture')

        with patch.object(self.server_mod.weather_settings, 'save', side_effect=fail_after_save):
            self.save(owner, self.settings(), expected=500)
        self.assertEqual(self.state(owner), before)
        with self.server_mod.connection() as connection:
            count = connection.execute('SELECT COUNT(*) FROM business_weather_settings WHERE business_id=?',
                                       (before['business_id'],)).fetchone()[0]
            self.assertEqual(count, 0)

    def test_init_adds_weather_table_without_changing_existing_history(self):
        with patch.dict(os.environ, {'DC_DB': str(self.tmp / 'before-weather.db')}):
            self.server_mod.init()
            with self.server_mod.connection() as connection:
                uid, bid = self.server_mod.ensure_account(connection, 'legacy-weather@example.test')
                self.server_mod.replace_observations(connection, bid, uid, {'billie': [{'text': 'Existing history'}]})
                connection.execute('UPDATE business SET imported=1 WHERE id=?', (bid,))
                connection.execute('DROP TABLE business_weather_settings')
                user = dict(connection.execute('SELECT * FROM user WHERE id=?', (uid,)).fetchone())
                notes = copy.deepcopy(self.server_mod.observations_map(connection, bid))
            self.server_mod.init()
            after = self.server_mod.state_of(user)
            self.assertEqual(after['observations'], notes)
            self.assertEqual(after['weatherSettings'], {'location': None, 'heatThreshold': 25})
