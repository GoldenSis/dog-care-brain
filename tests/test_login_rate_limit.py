import http.client
import json
import os
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


class LoginRateLimitTest(ApiServerTestCase):
    def setUp(self):
        with self.server_mod.connection() as c:
            c.execute('DELETE FROM login_attempt')
        for patcher in (
            patch.dict(os.environ, {'DC_TRUSTED_PROXY': '127.0.0.1'}),
            patch('login_delivery.configuration', return_value={'mode': 'smtp'}),
            patch('login_delivery.enqueue'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, email, ip, path='/api/auth/access'):
        return _http(self.port, 'POST', path, {'email': email}, headers={
            'X-DogCare-Client-IP': ip,
            'X-Forwarded-For': '192.0.2.99',
            'X-Real-IP': '192.0.2.99',
            'Forwarded': 'for=192.0.2.99',
        })[:2]

    def attempts(self, ip):
        with self.server_mod.connection() as c:
            row = c.execute('SELECT count FROM login_attempt WHERE key=?',
                            (self.server_mod._h('ip:' + ip),)).fetchone()
            return row[0] if row else 0

    def test_proxied_clients_have_independent_limits_shared_across_login_routes(self):
        for index in range(50):
            self.assertEqual(self.request(f'first-{index}@example.com', '192.0.2.1'),
                             (200, {'ok': True, 'mailed': True}))
        self.assertEqual(self.request('first-blocked@example.com', '192.0.2.1')[0], 429)
        self.assertEqual(self.request('second@example.com', '192.0.2.2'),
                         (200, {'ok': True, 'mailed': True}))
        self.assertEqual(self.request('still-blocked@example.com', '192.0.2.1', '/api/auth/request')[0], 429)
        self.assertEqual(self.attempts('192.0.2.1'), 50)
        self.assertEqual(self.attempts('192.0.2.2'), 1)

    def test_email_limit_remains_shared_across_client_ips(self):
        for index in range(5):
            self.assertEqual(self.request('same@example.com', f'192.0.2.{index + 1}')[0], 200)
        self.assertEqual(self.request('same@example.com', '192.0.2.6')[0], 429)
        self.assertEqual(self.attempts('192.0.2.6'), 0)

    def test_blocked_ip_cannot_consume_other_email_quotas(self):
        for index in range(50):
            self.assertEqual(self.request(f'initial-{index}@example.com', '192.0.2.1')[0], 200)
        for email in ('target-a@example.com', 'target-b@example.com'):
            for path in ('/api/auth/access', '/api/auth/request'):
                for _ in range(5):
                    self.assertEqual(self.request(email, '192.0.2.1', path),
                                     (429, {'ok': False, 'error': 'try again later'}))
            with self.server_mod.connection() as c:
                self.assertIsNone(c.execute('SELECT count FROM login_attempt WHERE key=?',
                                            (self.server_mod._h('email:' + email),)).fetchone())
            for _ in range(5):
                self.assertEqual(self.request(email, '192.0.2.2'),
                                 (200, {'ok': True, 'mailed': True}))
            self.assertEqual(self.request(email, '192.0.2.2')[0], 429)
        self.assertEqual(self.attempts('192.0.2.1'), 50)
        self.assertEqual(self.attempts('192.0.2.2'), 10)

    def test_forwarded_headers_cannot_bypass_default_or_untrusted_limits(self):
        get_request = self.httpd.get_request

        def untrusted_request():
            sock, address = get_request()
            return sock, ('198.51.100.7', address[1])

        cases = (
            ('default', patch.dict(os.environ, {'DC_TRUSTED_PROXY': ''}), '127.0.0.1'),
            ('untrusted', patch.object(self.httpd, 'get_request', side_effect=untrusted_request), '198.51.100.7'),
            ('public-bind', patch.object(self.httpd, 'server_address', ('0.0.0.0', self.port)), '127.0.0.1'),
            ('invalid-trust', patch.dict(os.environ, {'DC_TRUSTED_PROXY': '*'}), '127.0.0.1'),
        )
        for name, context, peer in cases:
            with self.subTest(name=name), context:
                with self.server_mod.connection() as c:
                    c.execute('DELETE FROM login_attempt')
                for index in range(51):
                    self.assertEqual(self.request(f'{name}-{index}@example.com', f'192.0.2.{index + 1}')[0],
                                     200 if index < 50 else 429)
                self.assertEqual(self.attempts(peer), 50)
                self.assertEqual(self.attempts('192.0.2.1'), 0)

    def test_invalid_or_ambiguous_proxy_headers_fall_back_to_socket_peer(self):
        values = ('', 'not-an-ip', '192.0.2.1, 192.0.2.2', '192.0.2.1:1234',
                  '[2001:db8::1]', 'fe80::1%eth0', '2001:db8::1%arbitrary',
                  '192.000.002.001', '999.2.3.4')
        for index, value in enumerate(values):
            self.assertEqual(self.request(f'malformed-{index}@example.com', value)[0], 200)
        self.assertEqual(_http(self.port, 'POST', '/api/auth/access',
                               {'email': 'missing@example.com'},
                               headers={'X-Forwarded-For': '192.0.2.88'})[0], 200)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            body = json.dumps({'email': 'duplicate@example.com'}).encode()
            conn.putrequest('POST', '/api/auth/access')
            conn.putheader('Content-Type', 'application/json')
            conn.putheader('Content-Length', str(len(body)))
            conn.putheader('X-DogCare-Client-IP', '192.0.2.1')
            conn.putheader('X-DogCare-Client-IP', '192.0.2.2')
            conn.endheaders(body)
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 200)
        finally:
            conn.close()
        self.assertEqual(self.attempts('127.0.0.1'), len(values) + 2)
        self.assertEqual(self.attempts('192.0.2.1'), 0)

    def test_equivalent_ip_literals_share_counters(self):
        values = ('2001:0DB8:0000:0000:0000:0000:0000:0001', '2001:db8::1',
                  '::ffff:192.0.2.1', '::ffff:c000:201', '192.0.2.1')
        for index, value in enumerate(values):
            self.assertEqual(self.request(f'literal-{index}@example.com', value)[0], 200)
        self.assertEqual(self.attempts('2001:db8::1'), 2)
        self.assertEqual(self.attempts('192.0.2.1'), 3)
        self.assertEqual(self.attempts('127.0.0.1'), 0)
