"""Daily workflows use tenant snapshots and private, revision-guarded documents."""
import base64
import copy
import http.client
import os
from unittest.mock import patch

from tests.test_tenant_isolation import ApiServerTestCase, _http


class DailyApiTest(ApiServerTestCase):
    def account(self, suffix="owner"):
        return self.login(f"{self._testMethodName}-{suffix}@example.com")

    def state(self, cookie):
        status, body, _ = _http(self.port, "GET", "/api/state", cookie=cookie)
        self.assertEqual(status, 200, body)
        return body

    def daily(self):
        return {"version": 1, "clients": [{"id": "c1", "name": "Fixture client"}],
                "dogs": [{"id": "d1", "name": "Fixture dog", "clientId": "c1"}],
                "bookings": [{"id": "b1", "dogId": "d1", "service": "night",
                              "start": "2026-10-30", "end": "2026-11-02",
                              "unitMinor": 2500, "currency": "CHF"}],
                "rates": {"currency": "CHF", "walk": None, "day": None, "night": 2500},
                "documents": []}

    def save(self, cookie, value, expected=200, headers=None):
        status, body, _ = _http(self.port, "PUT", "/api/daily", {"daily": value}, cookie, headers)
        self.assertEqual(status, expected, body)
        return body

    def document(self, **overrides):
        return {"dogId": "d1", "label": "Vaccination", "renewal": "", "name": "vaccination.pdf",
                "type": "application/pdf", "data": base64.b64encode(b"%PDF-1.7\nfixture").decode(),
                **overrides}

    def upload(self, cookie, payload=None, expected=200, headers=None):
        status, body, _ = _http(self.port, "POST", "/api/documents",
                                payload or self.document(), cookie, headers)
        self.assertEqual(status, expected, body)
        return body

    def headers(self, value):
        return {"X-DogCare-Business": str(value["business_id"]),
                "If-Match": f'"{value["revision"]}"'}

    def download(self, cookie, href):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("GET", href, headers={"Cookie": "dc_s=" + cookie} if cookie else {})
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def test_create_reload_extend_and_rate_configuration_preserve_agreement(self):
        cookie = self.account()
        before = self.state(cookie)
        self.assertEqual(before["daily"]["bookings"], [])
        value = self.daily()
        saved = self.save(cookie, value)
        self.assertEqual(self.state(cookie)["daily"], value)
        self.assertEqual(saved["revision"], before["revision"] + 1)
        self.assertTrue(saved["imported"])
        value["bookings"][0]["end"] = "2026-11-05"
        value["rates"]["night"] = 4000
        value["dogs"][0]["name"] = "Renamed dog"
        saved = self.save(cookie, value)
        self.assertEqual(saved["daily"]["bookings"][0]["unitMinor"], 2500)
        self.assertEqual(saved["observations"], before["observations"])
        self.assertEqual(self.state(cookie)["daily"], value)
        changed = copy.deepcopy(value)
        changed["bookings"][0]["unitMinor"] = 4000
        self.save(cookie, changed, expected=400)
        self.assertEqual(self.state(cookie), saved)

    def test_invalid_dates_ranges_types_and_references_do_not_write(self):
        cookie = self.account()
        before = self.state(cookie)
        cases = [("start", "2026-02-30"), ("end", "2026-10-30"),
                 ("end", "2026-10-29"), ("end", "2027-11-01"),
                 ("unitMinor", True), ("unitMinor", 1.5), ("unitMinor", -1),
                 ("unitMinor", 100000001), ("currency", "chf"),
                 ("dogId", "absent"), ("dogId", []), ("service", "week"),
                 ("id", "../../file")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                daily = self.daily()
                daily["bookings"][0][key] = value
                self.save(cookie, daily, expected=400)
                self.assertEqual(self.state(cookie), before)
        for path, bad in (("clients", [{"id": "c1", "name": "x"}] * 2),
                          ("clients", [{"id": "c1", "name": "x" * 121}]),
                          ("dogs", [{"id": "d1", "name": "x", "clientId": []}]),
                          ("version", True), ("rates", {})):
            daily = self.daily()
            daily[path] = bad
            self.save(cookie, daily, expected=400)
            self.assertEqual(self.state(cookie), before)

    def test_walk_day_inclusive_night_exclusive_and_leap_dates(self):
        cookie = self.account()
        for service in ("walk", "day", "night"):
            daily = self.daily()
            daily["bookings"][0].update(service=service, start="2028-02-29", end="2028-02-29")
            self.save(cookie, daily, expected=400 if service == "night" else 200)
        daily["bookings"][0]["end"] = "2028-03-01"
        self.save(cookie, daily)
        daily["bookings"][0].update(start="2028-01-01", end="2029-01-01")
        self.save(cookie, daily)  # 366 nights in leap year.
        daily["bookings"][0]["service"] = "day"
        self.save(cookie, daily, expected=400)  # 367 inclusive dates.

    def test_documents_private_download_and_metadata_updates_survive_reload(self):
        cookie = self.account()
        self.save(cookie, self.daily())
        before = self.state(cookie)
        after = self.upload(cookie)
        document = after["daily"]["documents"][0]
        self.assertNotIn("data", document)
        self.assertEqual(document["renewal"], "")
        self.assertEqual(after["revision"], before["revision"] + 1)
        status, data, headers = self.download(cookie, document["href"])
        self.assertEqual(status, 200)
        self.assertEqual(data, b"%PDF-1.7\nfixture")
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        self.assertTrue(headers["Content-Disposition"].startswith("attachment;"))
        document.update(label="New label", renewal="2027-10-05")
        final = self.save(cookie, after["daily"])
        self.assertEqual(self.state(cookie), final)

    def test_pdf_jpeg_and_png_require_matching_signature_and_bounded_payload(self):
        cookie = self.account()
        self.save(cookie, self.daily())
        for typ, contents in (("image/jpeg", b"\xff\xd8\xfffixture"),
                              ("image/png", b"\x89PNG\r\n\x1a\nfixture")):
            self.upload(cookie, self.document(type=typ, data=base64.b64encode(contents).decode()))
        before = self.state(cookie)
        for payload in (self.document(type="text/html"), self.document(data="!!!!"),
                        self.document(data="YQ=="), self.document(data=""),
                        self.document(type="image/png"), self.document(dogId="unknown"),
                        self.document(renewal="2026-02-30"), self.document(name="x\n"),
                        self.document(label="x" * 121), self.document(name="x" * 181),
                        self.document(data="A" * (((5 * 1024 * 1024 + 2) // 3) * 4 + 4))):
            with self.subTest(type=payload["type"], size=len(payload["data"])):
                self.upload(cookie, payload, expected=400)
                self.assertEqual(self.state(cookie), before)

    def test_document_references_cannot_be_forged_removed_or_transferred(self):
        cookie = self.account()
        self.save(cookie, self.daily())
        after = self.upload(cookie)
        for key, value in (("href", "https://example.com"), ("type", "text/html"),
                           ("name", "another.pdf"), ("dogId", "unknown"), ("id", "fake")):
            daily = copy.deepcopy(after["daily"])
            daily["documents"][0][key] = value
            self.save(cookie, daily, expected=400)
            self.assertEqual(self.state(cookie), after)
        daily["documents"] = []
        self.save(cookie, daily, expected=400)

    def test_auth_tenant_scope_and_stale_uploads_leave_no_binary(self):
        a, b = self.account("a"), self.account("b")
        self.save(a, self.daily())
        stale = self.headers(self.state(a))
        after = self.upload(a)
        href = after["daily"]["documents"][0]["href"]
        self.assertEqual(self.download(None, href)[0], 401)
        self.assertEqual(self.download(b, href)[0], 404)
        self.assertEqual(self.download(b, "/api/documents/unknown")[0], 404)
        before_b = self.state(b)
        self.save(b, self.daily(), expected=409, headers=self.headers(after))
        self.assertEqual(self.state(b), before_b)
        self.save(a, self.daily(), expected=400, headers=stale)  # Cannot remove existing doc.
        self.save(a, after["daily"], expected=409, headers=stale)
        self.upload(a, expected=409, headers=stale)
        self.assertEqual(self.state(a), after)
        with self.server_mod.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM daily_document WHERE business_id=?",
                                       (after["business_id"],)).fetchone()[0], 1)

    def test_database_failure_rolls_back_snapshot_revision_and_binary(self):
        cookie = self.account()
        self.save(cookie, self.daily())
        before = self.state(cookie)
        import sqlite3
        with patch.object(self.server_mod.daily, "save", side_effect=sqlite3.OperationalError("fixture")):
            self.upload(cookie, expected=500)
        self.assertEqual(self.state(cookie), before)
        with self.server_mod.connection() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM daily_document WHERE business_id=?",
                                       (before["business_id"],)).fetchone()[0], 0)

    def test_legacy_init_and_note_import_preserve_daily_state(self):
        cookie = self.account()
        _http(self.port, "PUT", "/api/observations", {
            "observations": {"billie": [{"text": "Existing history"}]}}, cookie)
        before = self.state(cookie)
        self.server_mod.init()
        self.assertEqual(self.state(cookie), before)
        saved = self.save(cookie, self.daily())
        status, body, _ = _http(self.port, "POST", "/api/import", {"language": "fr"}, cookie)
        self.assertEqual(status, 200, body)
        self.assertTrue(body["skipped"])
        self.assertEqual(body["daily"], saved["daily"])
        _http(self.port, "PUT", "/api/observations", {
            "observations": {"billie": [{"text": "New history"}]}}, cookie)
        self.assertEqual(self.state(cookie)["daily"], saved["daily"])

    def test_init_adds_daily_tables_to_existing_database_without_changing_notes(self):
        with patch.dict(os.environ, {"DC_DB": str(self.tmp / "before-daily.db")}):
            self.server_mod.init()
            with self.server_mod.connection() as c:
                uid, bid = self.server_mod.ensure_account(c, "legacy@example.com")
                self.server_mod.replace_observations(c, bid, uid, {
                    "billie": [{"text": "Retained legacy observation"}]})
                c.execute("UPDATE business SET imported=1 WHERE id=?", (bid,))
                c.execute("DROP TABLE business_daily")
                c.execute("DROP TABLE daily_document")
                before = self.server_mod.observations_map(c, bid)
            self.server_mod.init()
            with self.server_mod.connection() as c:
                self.assertEqual(self.server_mod.observations_map(c, bid), before)
                daily = self.server_mod.daily.load(c, bid)
                self.assertEqual(daily, self.server_mod.daily.empty())
                self.assertEqual(c.execute("SELECT count(*) FROM daily_document").fetchone()[0], 0)
            self.server_mod.init()
            with self.server_mod.connection() as c:
                self.assertEqual(self.server_mod.observations_map(c, bid), before)

    def test_unknown_booking_can_receive_explicit_agreement_without_automatic_repricing(self):
        cookie = self.account()
        value = self.daily()
        value["bookings"][0]["unitMinor"] = None
        self.save(cookie, value)
        value["rates"]["night"] = 5000
        saved = self.save(cookie, value)
        self.assertIsNone(saved["daily"]["bookings"][0]["unitMinor"])
        value["bookings"][0].update(unitMinor=3000, currency="EUR")
        agreed = self.save(cookie, value)
        self.assertEqual(agreed["daily"]["bookings"][0]["unitMinor"], 3000)
        value["rates"]["night"] = 6000
        saved = self.save(cookie, value)
        self.assertEqual(saved["daily"]["bookings"][0]["unitMinor"], 3000)
        value["bookings"][0]["unitMinor"] = 6000
        self.save(cookie, value, expected=400)
        self.assertEqual(self.state(cookie), saved)
