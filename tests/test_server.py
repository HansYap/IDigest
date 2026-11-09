"""Exercise the real loopback HTTP boundary without fetching public feeds."""

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import APP_ID, INSTANCE_ID, LocalServer


class FakeEngine:
    def snapshot(self):
        return {"stories": [], "sources": [], "settings": {}, "refresh": {"running": False}}

    def start_refresh(self):
        return {"running": True}

    def update_settings(self, payload):
        return payload

    def toggle_saved(self, story_id, saved):
        return {"id": story_id, "saved": saved}

    def mark_read(self, story_id, read):
        return {"id": story_id, "read": read}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(("127.0.0.1", 0), FakeEngine())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, payload=None, headers=None, raw=None):
        request_headers = headers or {}
        body = raw
        if payload is not None:
            body = json.dumps(payload).encode()
            request_headers = {"Content-Type": "application/json", **request_headers}
        request = Request(self.base + path, data=body, headers=request_headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            with error:
                return error.code, error.headers, error.read()

    def test_health_identifies_this_project(self):
        status, _, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["instance"], INSTANCE_ID)
        self.assertEqual(json.loads(body)["app"], APP_ID)

    def test_state_and_no_cache_policy(self):
        status, headers, body = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["stories"], [])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_reader_and_its_assets_are_served(self):
        for path, mime in (("/", "text/html"), ("/static/styles.css", "text/css"),
                           ("/static/briefing.js", "text/javascript"), ("/static/app.js", "text/javascript")):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(mime, headers["Content-Type"])
            self.assertTrue(body)

    def test_refresh_is_nonblocking(self):
        status, _, body = self.request("/api/refresh", {})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["running"])

    def test_settings_round_trip(self):
        status, _, body = self.request("/api/settings", {"watchlist": ["Sepang"]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["settings"]["watchlist"], ["Sepang"])

    def test_save_and_read_actions(self):
        for field in ("saved", "read"):
            status, _, body = self.request("/api/story", {"id": "a", field: True})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["story"][field])

    def test_foreign_website_cannot_change_settings(self):
        status, _, _ = self.request("/api/settings", {}, {"Origin": "https://example.com"})
        self.assertEqual(status, 403)

    def test_rebound_host_is_rejected(self):
        status, _, _ = self.request("/api/state", headers={"Host": "example.com"})
        self.assertEqual(status, 403)

    def test_plain_form_cannot_trigger_refresh(self):
        status, _, _ = self.request("/api/refresh", raw=b"anything")
        self.assertEqual(status, 403)

    def test_malformed_requests_are_reported(self):
        for raw in (b"not json", b"[]"):
            status, _, _ = self.request("/api/settings", raw=raw, headers={"Content-Type": "application/json"})
            self.assertEqual(status, 400)
        status, _, _ = self.request("/api/story", {"id": "a", "saved": "true"})
        self.assertEqual(status, 400)

    def test_large_request_is_rejected(self):
        status, _, _ = self.request("/api/settings", raw=b"x" * 33_000, headers={"Content-Type": "application/json"})
        self.assertEqual(status, 413)

    def test_unknown_paths_cannot_read_files(self):
        for path in ("/../app.py", "/data/app.log", "/sources.json"):
            status, _, _ = self.request(path)
            self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
