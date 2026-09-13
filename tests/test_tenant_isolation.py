"""Tenant isolation: business A cannot read business B's dogs.

Stdlib only. Starts api/server.py against a temp SQLite file.
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _http(port, method, path, body=None, cookie=None, headers=None):
    if headers is None and cookie and method in ("PUT", "POST") and path != "/api/auth/request":
        status, state, _ = _http(port, "GET", "/api/state", cookie=cookie)
        if status == 200:
            headers = {"X-DogCare-Business": str(state["business_id"]),
                       "If-Match": '"' + str(state["revision"]) + '"'}
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    extra_headers = headers or {}
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    if cookie:
        headers["Cookie"] = f"dc_s={cookie}"
    headers.update(extra_headers)
    try:
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        headers_out = {k.lower(): v for k, v in resp.getheaders()}
    finally:
        conn.close()
    try:
        parsed = json.loads(raw.decode() or "null")
    except json.JSONDecodeError:
        parsed = raw.decode()
    return resp.status, parsed, headers_out


def _cookie_from(headers):
    raw = headers.get("set-cookie") or ""
    for part in raw.split(";"):
        part = part.strip()
        if part.startswith("dc_s="):
            return part.split("=", 1)[1]
    return None


def _latest_link(outbox, email):
    files = sorted(Path(outbox).glob("*.json"), key=lambda p: p.stat().st_mtime)
    for path in reversed(files):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("to") == email:
            return data["link"]
    raise AssertionError(f"no outbox letter for {email}")


class ApiServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="dogcare-iso-")
        cls.addClassCleanup(temporary.cleanup)
        cls.tmp = Path(temporary.name)
        environment = patch.dict(os.environ, {
            "DC_DB": str(cls.tmp / "t.db"),
            "DC_OUTBOX": str(cls.tmp / "outbox"),
            "DC_BLOBS": str(cls.tmp / "blobs"),
            "DC_ROOT": str(ROOT),
        })
        environment.start()
        cls.addClassCleanup(environment.stop)
        os.environ.pop("DC_INSECURE_COOKIE", None)
        import_path = str(ROOT / "api")
        sys.path.insert(0, import_path)
        cls.addClassCleanup(sys.path.remove, import_path)
        import server  # noqa: E402
        cls.server_mod = server
        server.init()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.httpd.server_address[1]
        cls.outbox = os.environ["DC_OUTBOX"]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def login(self, email):
        status, body, _ = _http(self.port, "POST", "/api/auth/request", {"email": email})
        self.assertEqual(status, 200, body)
        self.assertTrue(body.get("ok"))
        link = _latest_link(self.outbox, email)
        path = urlparse(link).path + "?" + urlparse(link).query
        status, _, headers = _http(self.port, "GET", path)
        self.assertEqual(status, 302)
        cookie = _cookie_from(headers)
        self.assertTrue(cookie)
        return cookie


class TenantIsolationTest(ApiServerTestCase):
    def test_user_of_business_a_cannot_read_business_b_dogs(self):
        cookie_a = self.login("owner-a@example.com")
        cookie_b = self.login("owner-b@example.com")

        status, body, _ = _http(
            self.port, "POST", "/api/dogs",
            {"slug": "secret-a", "name": "Secret A"}, cookie=cookie_a,
        )
        self.assertEqual(status, 200, body)
        dog_id = body["dog"]["id"]

        status, body, _ = _http(self.port, "GET", "/api/dogs", cookie=cookie_b)
        self.assertEqual(status, 200, body)
        slugs = {d["slug"] for d in body["dogs"]}
        self.assertNotIn("secret-a", slugs)
        ids = {d["id"] for d in body["dogs"]}
        self.assertNotIn(dog_id, ids)

        status, body, _ = _http(self.port, "GET", f"/api/dogs/{dog_id}", cookie=cookie_b)
        self.assertEqual(status, 404, body)

        status, body, _ = _http(self.port, "GET", "/api/observations", cookie=cookie_b)
        self.assertEqual(status, 200, body)
        self.assertNotIn("secret-a", body["observations"])

        status, body, _ = _http(self.port, "GET", f"/api/dogs/{dog_id}", cookie=cookie_a)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["dog"]["slug"], "secret-a")


if __name__ == "__main__":
    unittest.main()
