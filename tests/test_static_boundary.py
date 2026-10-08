"""The API serves an explicit frontend surface, never the repository tree."""
import http.client
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


class StaticBoundaryTest(ApiServerTestCase):
    def test_internal_files_are_denied_with_and_without_session(self):
        cookie = self.login('static-boundary@example.com')
        paths = ('/Agents.md', '/AGENTS.md', '/README.md', '/.git', '/.git/config', '/.env',
                 '/deploy/dogcare.env.example', '/deploy/dogcare.service', '/deploy/dogcare.caddy',
                 '/scripts/private_backup.py', '/scripts/seed_private_preview.py',
                 '/tests/test_static_boundary.py', '/tests/test_api_adapter.js',
                 '/docs/client-portal.md', '/docs/review/comptabilite/after-390.png',
                 '/assets/photos/sources.json', '/assets/fonts/README.md',
                 '/api/server.py', '/%41gents.md', '/%2eenv', '/assets/../Agents.md')
        for session in (None, cookie):
            for path in paths:
                with self.subTest(path=path, authenticated=bool(session)):
                    self.assertEqual(_http(self.port, 'GET', path, cookie=session)[0], 404)

    def test_frontend_assets_and_authenticated_workspace_remain_available(self):
        cookie = self.login('static-assets@example.com')
        for path in ('/', '/public.html', '/welcome.js', '/portal-copy.js', '/api.js',
                     '/styles.css', '/muse.css', '/welcome.css',
                     '/assets/photos/good-company.jpg', '/assets/fonts/dm-sans-468d56b6.woff2',
                     '/assets/vendor/finance/pdfjs-dist/pdf.mjs',
                     '/assets/vendor/finance/tesseract.js/worker.min.js',
                     '/assets/vendor/finance/tesseract.js-core/tesseract-core-simd-lstm.wasm.js',
                     '/assets/vendor/finance/tessdata/fra.traineddata.gz'):
            with self.subTest(path=path):
                connection = http.client.HTTPConnection('127.0.0.1', self.port)
                try:
                    connection.request('GET', path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertGreater(len(response.read()), 0)
                    if path.endswith('.woff2'):
                        self.assertEqual(response.getheader('Content-Type'), 'font/woff2')
                finally:
                    connection.close()
        self.assertEqual(_http(self.port, 'GET', '/app.js', cookie=cookie)[0], 200)
        self.assertEqual(_http(self.port, 'GET', '/app.js')[0], 401)

    def test_allowed_name_cannot_symlink_to_an_internal_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'internal.md').write_text('synthetic internal file')
            (root / 'welcome.js').symlink_to(root / 'internal.md')
            with patch.dict(os.environ, {'DC_ROOT': str(root)}):
                self.assertEqual(_http(self.port, 'GET', '/welcome.js')[0], 404)

    def test_anonymous_homepage_fallback_cannot_symlink_to_private_content(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / 'public'
            root.mkdir()
            (root / 'index.html').write_text('<head></head>workspace')
            for target in (root / 'internal.md', parent / 'external.md', root / 'app.js', root / 'index.html'):
                with self.subTest(target=target.name):
                    target.write_text('synthetic private data')
                    (root / 'public.html').symlink_to(target)
                    try:
                        with patch.dict(os.environ, {'DC_ROOT': str(root)}):
                            for path in ('/', '/index.html', '/public.html'):
                                expected = 401 if target.name == 'app.js' and path == '/public.html' else 404
                                self.assertEqual(_http(self.port, 'GET', path)[0], expected, path)
                    finally:
                        (root / 'public.html').unlink()
