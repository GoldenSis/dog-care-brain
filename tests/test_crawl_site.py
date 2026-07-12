import unittest

from tools.crawl_site import allowed_urls, markdown_text, normalize_url, sitemap_urls


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


if __name__ == "__main__":
    unittest.main()
