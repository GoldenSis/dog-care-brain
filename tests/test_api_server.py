"""Regression coverage for local account storage and transactional writes."""
import base64
import concurrent.futures
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from tests.test_tenant_isolation import (
    ApiServerTestCase, ROOT, _cookie_from, _http, _latest_link,
)


class ApiServerRegressionTest(ApiServerTestCase):
    def account(self, suffix="owner"):
        return self.login(f"{self._testMethodName}-{suffix}@example.com")

    def state(self, cookie):
        status, body, _ = _http(self.port, "GET", "/api/state", cookie=cookie)
        self.assertEqual(status, 200, body)
        return body

    def test_default_magic_link_and_cookie_work_over_local_http(self):
        email = "default-http@example.com"
        status, body, _ = _http(self.port, "POST", "/api/auth/request", {"email": email})
        self.assertEqual(status, 200, body)
        link = urlparse(_latest_link(self.outbox, email))
        self.assertEqual(link.scheme, "http")
        self.assertEqual(link.netloc, f"127.0.0.1:{self.port}")
        status, _, headers = _http(self.port, "GET", f"{link.path}?{link.query}")
        self.assertEqual(status, 302)
        self.assertNotIn("Secure", headers["set-cookie"])
        cookie = _cookie_from(headers)
        self.assertTrue(cookie)
        self.assertEqual(self.state(cookie)["email"], email)

    def test_explicit_secure_cookie_also_uses_https_links(self):
        with patch.dict(os.environ, {"DC_INSECURE_COOKIE": "0"}):
            email = "explicit-https@example.com"
            status, body, _ = _http(self.port, "POST", "/api/auth/request", {"email": email})
            self.assertEqual(status, 200, body)
            self.assertEqual(urlparse(_latest_link(self.outbox, email)).scheme, "https")
            self.assertIn("Secure", self.server_mod.cookie_header("test"))

    def test_runtime_defaults_are_outside_static_document_root(self):
        with patch.dict(os.environ):
            for name in ("DC_DB", "DC_OUTBOX", "DC_BLOBS", "DC_DATA_DIR"):
                os.environ.pop(name, None)
            root = Path(self.server_mod.static_root())
            self.assertEqual(root, ROOT)
            for path in (self.server_mod.db_path(), self.server_mod.outbox_dir(),
                         self.server_mod.blobs_dir()):
                with self.subTest(path=path):
                    self.assertNotIn(root, Path(path).resolve().parents)
                    self.assertNotEqual(root, Path(path).resolve())

    def test_init_rejects_private_paths_inside_static_root_and_symlinks(self):
        public = self.tmp / "public"
        public.mkdir()
        alias = self.tmp / "public-alias"
        alias.symlink_to(public, target_is_directory=True)
        for base in (public, alias):
            for key, child in (("DC_DB", "data.db"), ("DC_OUTBOX", "outbox"),
                               ("DC_BLOBS", "recordings")):
                with self.subTest(base=base.name, key=key):
                    with patch.dict(os.environ, {"DC_ROOT": str(public), key: str(base / child)}):
                        with self.assertRaises(ValueError):
                            self.server_mod.init()

    def test_normal_writes_prevent_a_later_destructive_import(self):
        writes = (
            ("PUT", "/api/observations", {"observations": {"billie": [{"text": "Real note"}]}}),
            ("PUT", "/api/invites", {"invites": [{"email": "carer@example.com"}]}),
            ("PUT", "/api/prefs", {"language": "fr"}),
            ("POST", "/api/dogs", {"slug": "new-dog", "name": "New Dog"}),
        )
        for index, (method, path, payload) in enumerate(writes):
            with self.subTest(path=path):
                cookie = self.account(str(index))
                status, body, _ = _http(self.port, method, path, payload, cookie)
                self.assertEqual(status, 200, body)
                before = self.state(cookie)
                status, body, _ = _http(self.port, "POST", "/api/import", {
                    "observations": {"billie": [{"text": "Stale browser note"}]},
                    "invites": [], "language": "en",
                }, cookie)
                self.assertEqual(status, 200, body)
                self.assertTrue(body.get("skipped"))
                self.assertTrue(body.get("imported"))
                self.assertEqual(body.get("business_id"), before["business_id"])
                after = self.state(cookie)
                for key in ("observations", "invites", "language", "dogs"):
                    self.assertEqual(after[key], before[key])

    def test_partial_import_preserves_absent_collections(self):
        for key, value in (("language", "fr"),
                           ("invites", [{"email": "invited@example.com"}])):
            with self.subTest(key=key):
                cookie = self.account(key)
                before = self.state(cookie)
                status, body, _ = _http(self.port, "POST", "/api/import", {key: value}, cookie)
                self.assertEqual(status, 200, body)
                self.assertEqual(body["observations"], before["observations"])
                self.assertTrue(body.get("imported"))
                if key == "language":
                    self.assertEqual(body["language"], "fr")
                    self.assertEqual(body["invites"], before["invites"])
                else:
                    self.assertEqual(body["invites"][0]["email"], value[0]["email"])
                    self.assertEqual(body["language"], before["language"])

    def test_init_closes_legacy_import_eligibility_for_established_accounts(self):
        untouched = self.account("untouched")
        writes = (
            ("PUT", "/api/observations", {"observations": {"billie": [{"text": "Existing history"}]}}),
            ("PUT", "/api/invites", {"invites": [{"email": "existing-carer@example.com"}]}),
            ("PUT", "/api/prefs", {"language": "fr"}),
            ("POST", "/api/dogs", {"slug": "existing-dog", "name": "Existing Dog"}),
        )
        accounts = []
        for index, (method, path, payload) in enumerate(writes):
            cookie = self.account(str(index))
            status, body, _ = _http(self.port, method, path, payload, cookie)
            self.assertEqual(status, 200, body)
            before = self.state(cookie)
            connection = self.server_mod.db()
            try:
                connection.execute("UPDATE business SET imported=0 WHERE id=?", (before["business_id"],))
                connection.commit()
            finally:
                connection.close()
            accounts.append((path, cookie, before))
        self.server_mod.init()
        for path, cookie, before in accounts:
            with self.subTest(path=path):
                self.assertTrue(self.state(cookie)["imported"])
                status, body, _ = _http(self.port, "POST", "/api/import", {
                    "observations": {"billie": [{"text": "Stale browser history"}]},
                }, cookie)
                self.assertEqual(status, 200, body)
                self.assertTrue(body["skipped"])
                self.assertEqual(self.state(cookie), before)
        self.assertFalse(self.state(untouched)["imported"])
        status, body, _ = _http(self.port, "POST", "/api/import", {"language": "fr"}, untouched)
        self.assertEqual(status, 200, body)
        self.assertFalse(body["skipped"])
        self.assertEqual(body["language"], "fr")

    def test_import_accepts_legacy_snapshot_larger_than_two_megabytes(self):
        cookie = self.account()
        text = "\u2603" * (450 * 1024)
        status, body, _ = _http(self.port, "POST", "/api/import", {
            "observations": {"billie": [{"text": text}]},
        }, cookie)
        self.assertEqual(status, 200, body.get("error") if isinstance(body, dict) else body)
        self.assertEqual(body["observations"]["billie"][0]["text"], text)

    def test_nested_invalid_replacements_return_json_without_changing_state(self):
        payloads = (
            ("PUT", "/api/observations", {"observations": {"billie": [None]}}),
            ("PUT", "/api/observations", {"observations": {"billie": [{"tags": "bad"}]}}),
            ("PUT", "/api/observations", {"observations": {"billie": [{"audio": []}]}}),
            ("PUT", "/api/invites", {"invites": [None]}),
            ("PUT", "/api/invites", {"invites": [{"permissions": "bad"}]}),
            ("PUT", "/api/prefs", {"language": {"code": "fr"}}),
            ("POST", "/api/import", {"observations": {"billie": [None]}, "language": "fr"}),
        )
        cookie = self.account()
        before = self.state(cookie)
        for method, path, payload in payloads:
            with self.subTest(path=path, payload=payload):
                status, body, headers = _http(self.port, method, path, payload, cookie)
                self.assertEqual(status, 400, body)
                self.assertIn("application/json", headers["content-type"])
                self.assertFalse(body["ok"])
                self.assertEqual(self.state(cookie), before)
        status, body, _ = _http(self.port, "PUT", "/api/prefs", {"language": "fr"}, cookie)
        self.assertEqual(status, 200, body)

    def test_failed_import_does_not_consume_eligibility(self):
        cookie = self.account()
        before = self.state(cookie)
        status, body, _ = _http(self.port, "POST", "/api/import", {"invites": [None]}, cookie)
        self.assertEqual(status, 400, body)
        self.assertEqual(self.state(cookie), before)
        status, body, _ = _http(self.port, "POST", "/api/import", {"language": "fr"}, cookie)
        self.assertEqual(status, 200, body)
        self.assertFalse(body.get("skipped", False))
        self.assertEqual(body["language"], "fr")

    def test_oversized_audio_duration_returns_json_without_changing_state(self):
        cookie = self.account()
        before = self.state(cookie)
        status, body, headers = _http(self.port, "PUT", "/api/observations", {
            "observations": {"billie": [{"audio": {
                "url": "data:audio/webm;base64,YQ==", "duration": 10**309,
            }}]},
        }, cookie)
        self.assertEqual(status, 400, body)
        self.assertIn("application/json", headers["content-type"])
        self.assertFalse(body["ok"])
        self.assertEqual(self.state(cookie), before)

    def test_invite_constraint_failure_rolls_back_prior_deletion(self):
        cookie = self.account()
        existing = {"email": "existing@example.com", "token": "existing-token"}
        status, body, _ = _http(self.port, "PUT", "/api/invites", {"invites": [existing]}, cookie)
        self.assertEqual(status, 200, body)
        before = self.state(cookie)
        duplicate = {"email": "new@example.com", "token": "duplicate-token"}
        status, body, headers = _http(self.port, "PUT", "/api/invites", {
            "invites": [duplicate, duplicate],
        }, cookie)
        self.assertEqual(status, 409, body)
        self.assertIn("application/json", headers["content-type"])
        self.assertFalse(body["ok"])
        self.assertEqual(self.state(cookie), before)

    def test_recordings_are_only_readable_by_their_business(self):
        cookie_a = self.account("a")
        cookie_b = self.account("b")
        recording = b"private recording"
        status, body, _ = _http(self.port, "POST", "/api/blobs", {
            "type": "audio/webm;codecs=opus",
            "data": base64.b64encode(recording).decode(),
        }, cookie_a)
        self.assertEqual(status, 200, body)
        path = "/api/blobs/" + body["ref"]
        status, body, _ = _http(self.port, "GET", path, cookie=cookie_a)
        self.assertEqual(status, 200, body)
        self.assertEqual(body, recording.decode())
        status, body, _ = _http(self.port, "GET", path, cookie=cookie_b)
        self.assertEqual(status, 404, body)
        status, body, _ = _http(self.port, "GET", path)
        self.assertEqual(status, 401, body)

    def test_blob_upload_accepts_recording_above_old_request_limit(self):
        cookie = self.account()
        recording = b"voice" * (350 * 1024)
        status, body, _ = _http(self.port, "POST", "/api/blobs", {
            "type": "audio/webm;codecs=opus",
            "data": base64.b64encode(recording).decode(),
        }, cookie)
        self.assertEqual(status, 200, body)
        status, body, _ = _http(self.port, "GET", "/api/blobs/" + body["ref"], cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body, recording.decode())

    def test_retried_and_concurrent_recording_uploads_reuse_one_business_file(self):
        cookie = self.account()
        bid = self.state(cookie)["business_id"]
        payload = {"type": "audio/webm;codecs=opus", "data": base64.b64encode(b"same recording").decode()}
        barrier = threading.Barrier(4)

        def upload(_):
            barrier.wait(timeout=5)
            return _http(self.port, "POST", "/api/blobs", payload, cookie)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(upload, range(4)))
        responses.append(_http(self.port, "POST", "/api/blobs", payload, cookie))
        refs = set()
        for status, body, _ in responses:
            self.assertEqual(status, 200, body)
            refs.add(body["ref"])
        self.assertEqual(len(refs), 1)
        ref = refs.pop()
        directory = Path(self.server_mod.blobs_dir()) / str(bid)
        self.assertEqual([path.name for path in directory.iterdir()], [ref])
        status, body, _ = _http(self.port, "GET", "/api/blobs/" + ref, cookie=cookie)
        self.assertEqual(status, 200, body)
        self.assertEqual(body, "same recording")

    def test_identical_recording_refs_are_stored_separately_for_each_business(self):
        cookie_a, cookie_b = self.account("a"), self.account("b")
        payload = {"type": "audio/webm", "data": base64.b64encode(b"shared recording").decode()}
        status, body, _ = _http(self.port, "POST", "/api/blobs", payload, cookie_a)
        self.assertEqual(status, 200, body)
        ref = body["ref"]
        status, body, _ = _http(self.port, "GET", "/api/blobs/" + ref, cookie=cookie_b)
        self.assertEqual(status, 404, body)
        status, body, _ = _http(self.port, "POST", "/api/blobs", payload, cookie_b)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["ref"], ref)
        directories = []
        for cookie in (cookie_a, cookie_b):
            status, body, _ = _http(self.port, "GET", "/api/blobs/" + ref, cookie=cookie)
            self.assertEqual(status, 200, body)
            self.assertEqual(body, "shared recording")
            bid = self.state(cookie)["business_id"]
            directory = Path(self.server_mod.blobs_dir()) / str(bid)
            self.assertEqual([path.name for path in directory.iterdir()], [ref])
            directories.append(directory)
        self.assertNotEqual(directories[0], directories[1])
        self.assertFalse((directories[0] / ref).samefile(directories[1] / ref))

    def test_legacy_random_recording_refs_remain_readable_only_by_their_business(self):
        cookie_a, cookie_b = self.account("a"), self.account("b")
        bid = self.state(cookie_a)["business_id"]
        ref = "f" * 32 + ".webm"
        directory = Path(self.server_mod.blobs_dir()) / str(bid)
        directory.mkdir()
        (directory / ref).write_bytes(b"legacy recording")
        path = "/api/blobs/" + ref
        status, body, _ = _http(self.port, "PUT", "/api/observations", {
            "observations": {"billie": [{"text": "Old voice note", "audio": {"url": path}}]},
        }, cookie_a)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["observations"]["billie"][0]["audio"]["url"], path)
        status, body, _ = _http(self.port, "GET", path, cookie=cookie_a)
        self.assertEqual(status, 200, body)
        self.assertEqual(body, "legacy recording")
        status, body, _ = _http(self.port, "GET", path, cookie=cookie_b)
        self.assertEqual(status, 404, body)

    def test_concurrent_first_signins_share_one_account(self):
        email = "concurrent-first@example.com"
        paths = []
        for _ in range(8):
            status, body, _ = _http(self.port, "POST", "/api/auth/request", {"email": email})
            self.assertEqual(status, 200, body)
            link = urlparse(_latest_link(self.outbox, email))
            paths.append(f"{link.path}?{link.query}")
        barrier = threading.Barrier(len(paths))

        def verify(path):
            barrier.wait(timeout=5)
            return _http(self.port, "GET", path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(paths)) as pool:
            responses = list(pool.map(verify, paths))
        businesses = set()
        for status, body, headers in responses:
            self.assertEqual(status, 302, body)
            cookie = _cookie_from(headers)
            self.assertTrue(cookie, headers)
            businesses.add(self.state(cookie)["business_id"])
        self.assertEqual(len(businesses), 1)
        connection = self.server_mod.db()
        try:
            count = connection.execute("SELECT COUNT(*) FROM user WHERE email=?", (email,)).fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            connection.close()

    def test_failed_first_signin_keeps_token_usable_and_rolls_back_account(self):
        email = "failed-first@example.com"
        status, body, _ = _http(self.port, "POST", "/api/auth/request", {"email": email})
        self.assertEqual(status, 200, body)
        query = parse_qs(urlparse(_latest_link(self.outbox, email)).query)
        with patch.object(self.server_mod, "seed_business", side_effect=RuntimeError("seed failed")):
            with self.assertRaisesRegex(RuntimeError, "seed failed"):
                self.server_mod.do_auth_verify(query)
        connection = self.server_mod.db()
        try:
            self.assertIsNone(connection.execute("SELECT id FROM user WHERE email=?", (email,)).fetchone())
        finally:
            connection.close()
        sid, error = self.server_mod.do_auth_verify(query)
        self.assertIsNone(error)
        self.assertTrue(sid)
        self.assertEqual(self.state(sid)["email"], email)


if __name__ == "__main__":
    unittest.main()
