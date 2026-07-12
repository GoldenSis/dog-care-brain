import argparse
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.crawl_site import allowed_urls, markdown_text, nonnegative_float, normalize_url, output_is_safe, read_url, repository_root, same_origin, sitemap_urls


class CrawlSiteTest(unittest.TestCase):
    def test_normalize_url_removes_query_fragment_and_trailing_slash(self):
        self.assertEqual(normalize_url("HTTPS://Example.com/a/?x=1#top"), "https://example.com/a")

    def test_sitemap_urls_accepts_namespaced_sitemap(self):
        xml = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc></url></urlset>'
        self.assertEqual(sitemap_urls(xml), ["https://example.com/a"])

    def test_allowed_urls_stays_on_origin_and_respects_robots(self):
        candidates = [
            "https://example.com/",
            "https://example.com/public/",
            "https://example.com/private",
            "https://other.example/page",
            "https://example.com/public/?duplicate=yes",
        ]
        urls = allowed_urls("https://example.com/", candidates, "User-agent: *\nDisallow: /private", 10)
        self.assertEqual(urls, ["https://example.com/", "https://example.com/public"])

    def test_markdown_text_converts_string_subclasses_to_plain_string(self):
        class MarkdownResult(str):
            pass

        result = type("Result", (), {"markdown": MarkdownResult("# Care")})()
        markdown = markdown_text(result)
        self.assertEqual(markdown, "# Care")
        self.assertIs(type(markdown), str)

    def test_same_origin_rejects_redirect_target_on_another_host(self):
        self.assertTrue(same_origin("https://example.com/a", "https://example.com/b"))
        self.assertTrue(same_origin("https://example.com/a", "https://example.com:443/b"))
        self.assertFalse(same_origin("https://example.com/a", "https://elsewhere.example/b"))
        self.assertFalse(same_origin("https://example.com/a", "http://example.com/b"))
        self.assertFalse(same_origin("https://example.com/a", "https://example.com:444/b"))

    def test_delay_must_be_finite_and_nonnegative(self):
        self.assertEqual(nonnegative_float("0.5"), 0.5)
        for value in ("-1", "nan", "inf"):
            with self.assertRaises(argparse.ArgumentTypeError):
                nonnegative_float(value)

    def test_output_requires_explicit_opt_in_inside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.assertFalse(output_is_safe(workspace / "corpus", workspace))
            self.assertTrue(output_is_safe(workspace.parent / "corpus", workspace))

    def test_repository_root_is_independent_of_current_directory(self):
        self.assertEqual(repository_root(), Path(__file__).resolve().parents[1])

    def test_discovery_redirect_does_not_contact_another_origin(self):
        target_hits = []

        class TargetHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                target_hits.append(self.path)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_):
                pass

        target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{target.server_port}/escaped")
                self.end_headers()

            def log_message(self, *_):
                pass

        redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (target, redirect)]
        for thread in threads:
            thread.start()
        try:
            with self.assertRaises(Exception):
                read_url(f"http://127.0.0.1:{redirect.server_port}/robots.txt")
            self.assertEqual(target_hits, [])
        finally:
            redirect.shutdown()
            target.shutdown()
            redirect.server_close()
            target.server_close()


if __name__ == "__main__":
    unittest.main()
