#!/usr/bin/env python3
"""Create a small, robots-aware Markdown research corpus with Crawl4AI."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
import urllib.request
import urllib.error
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

USER_AGENT = "DogCareBrainResearchBot/1.0 (+https://goldensis.github.io/dog-care-brain/)"
MAX_DISCOVERY_BYTES = 2_000_000
MAX_PAGE_CHARS = 500_000


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: object, file_pointer: object, code: int, message: str, headers: object, new_url: str) -> object:
        if not same_origin(request.full_url, new_url):
            raise urllib.error.HTTPError(new_url, code, "Cross-origin redirect refused", headers, file_pointer)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


@dataclass
class Page:
    url: str
    title: str
    markdown: str


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(SameOriginRedirectHandler())
    with opener.open(request, timeout=20) as response:
        if not same_origin(url, response.geturl()):
            raise ValueError(f"Cross-origin redirect refused: {url} -> {response.geturl()}")
        content = response.read(MAX_DISCOVERY_BYTES + 1)
        if len(content) > MAX_DISCOVERY_BYTES:
            raise ValueError(f"Discovery document exceeds {MAX_DISCOVERY_BYTES} bytes: {url}")
        return content


def sitemap_urls(xml: bytes) -> list[str]:
    root = ET.fromstring(xml)
    return [element.text.strip() for element in root.iter() if element.tag.endswith("loc") and element.text]


def allowed_urls(base_url: str, candidates: list[str], robots_text: str, limit: int) -> list[str]:
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(urljoin(base_url, "/robots.txt"))
    parser.parse(robots_text.splitlines())
    selected: list[str] = []
    for candidate in candidates:
        normalized = normalize_url(candidate)
        parts = urlsplit(normalized)
        if parts.scheme not in {"http", "https"} or not same_origin(base_url, normalized):
            continue
        if normalized in selected or not parser.can_fetch(USER_AGENT, normalized):
            continue
        selected.append(normalized)
        if len(selected) >= limit:
            break
    return selected


def markdown_text(result: object) -> str:
    markdown = getattr(result, "markdown", "")
    if isinstance(markdown, str):
        return str(markdown)[:MAX_PAGE_CHARS]
    return (getattr(markdown, "fit_markdown", None) or getattr(markdown, "raw_markdown", "")).strip()[:MAX_PAGE_CHARS]


def same_origin(base_url: str, candidate: str) -> bool:
    def origin(url: str) -> tuple[str, str | None, int | None]:
        parts = urlsplit(url)
        default_port = 443 if parts.scheme.lower() == "https" else 80 if parts.scheme.lower() == "http" else None
        return parts.scheme.lower(), parts.hostname, parts.port or default_port

    return origin(base_url) == origin(candidate)


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than or equal to zero")
    return parsed


def output_is_safe(output: Path, workspace: Path) -> bool:
    return not output.resolve().is_relative_to(workspace.resolve())


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


async def crawl(urls: list[str], delay: float) -> list[Page]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError as error:
        raise SystemExit("Install crawler requirements first: pip install -r requirements-crawler.txt") from error

    browser_config = BrowserConfig(headless=True, user_agent=USER_AGENT, verbose=False)
    run_config = CrawlerRunConfig(cache_mode=CacheMode.ENABLED, check_robots_txt=True, page_timeout=20_000)
    pages: list[Page] = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        origin = urls[0]

        async def restrict_navigation(page: object, **_: object) -> object:
            async def handle_route(route: object) -> None:
                request = route.request
                if request.is_navigation_request() and not same_origin(origin, request.url):
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", handle_route)
            return page

        crawler.crawler_strategy.set_hook("on_page_context_created", restrict_navigation)
        for index, url in enumerate(urls):
            if index:
                await asyncio.sleep(delay)
            result = await crawler.arun(url=url, config=run_config)
            if not result.success:
                print(f"skip: {url}: {result.error_message}")
                continue
            final_url = getattr(result, "redirected_url", None) or getattr(result, "url", url)
            if not same_origin(origin, final_url):
                print(f"skip: cross-origin result refused: {url} -> {final_url}")
                continue
            metadata = result.metadata or {}
            pages.append(Page(url=url, title=metadata.get("title", url), markdown=markdown_text(result)))
            print(f"crawled: {url}")
    return pages


def write_report(output: Path, base_url: str, pages: list[Page]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {"source": base_url, "crawled_at": int(time.time()), "pages": [asdict(page) for page in pages]}
    (output / "corpus.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sections = ["# Public-site research corpus", "", f"Source: {base_url}", f"Pages: {len(pages)}", ""]
    for page in pages:
        sections.extend([f"## {page.title}", "", f"URL: {page.url}", "", page.markdown, ""])
    (output / "corpus.md").write_text("\n".join(sections), encoding="utf-8")


async def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("url", help="Public site root, for example https://www.rintintin-pro.com/")
    cli.add_argument("--output", required=True, type=Path, help="Directory for corpus.md and corpus.json")
    cli.add_argument("--max-pages", type=int, default=12, choices=range(1, 51), metavar="1-50")
    cli.add_argument("--delay", type=nonnegative_float, default=1.0, help="Seconds between page requests")
    cli.add_argument("--allow-output-in-repo", action="store_true", help="Permit an output path inside the current workspace")
    args = cli.parse_args()

    if not args.allow_output_in_repo and not output_is_safe(args.output, repository_root()):
        cli.error("--output must be outside the repository (or pass --allow-output-in-repo explicitly)")

    root = normalize_url(args.url)
    robots_url, sitemap_url = urljoin(root, "/robots.txt"), urljoin(root, "/sitemap.xml")
    robots = read_url(robots_url).decode("utf-8", errors="replace")
    candidates = [root, *sitemap_urls(read_url(sitemap_url))]
    urls = allowed_urls(root, candidates, robots, args.max_pages)
    if not urls:
        raise SystemExit("No crawlable URLs found after applying robots.txt and origin rules")
    pages = await crawl(urls, args.delay)
    write_report(args.output, root, pages)
    print(f"wrote {len(pages)} pages to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
