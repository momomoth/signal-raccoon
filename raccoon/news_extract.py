import asyncio
import re
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
import html2text

from raccoon.config import settings
from raccoon.models import Article, NewsSearchResult
from raccoon.sanitizer import sanitize_article_fields

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Overall wall-clock cap for the whole extraction batch. Bounded by the
# product's "30 seconds from send" promise: an article still in flight when
# this fires is cancelled, but anything already extracted is kept and returned
# downstream so the pipeline can continue with partial data rather than stalling.
_NODE_TIMEOUT_SECONDS = 30.0


def _attr_str(element, name: str) -> Optional[str]:
    """Return an element attribute as a string, or None if missing/empty."""
    value = element.get(name)
    return value if isinstance(value, str) and value else None


def _extract_date(soup: BeautifulSoup) -> Optional[str]:
    """Best-effort date extraction from common meta tags and JSON-LD."""
    selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"property": "og:article:published_time"}),
        ("meta", {"name": "publishedDate"}),
        ("meta", {"name": "date"}),
        ("time", {}),
    ]
    for tag, attrs in selectors:
        element = soup.find(tag, attrs=attrs)
        if element:
            value = _attr_str(element, "content") or _attr_str(element, "datetime") or element.get_text(strip=True)
            if value:
                return value

    for script in soup.find_all("script", type="application/ld+json"):
        import json
        try:
            data = json.loads(script.string or script.get_text())
            if isinstance(data, list):
                data = data[0] if data else {}
            date = data.get("datePublished") if isinstance(data, dict) else None
            if date:
                return date
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return None


def _clean_text(text: str) -> str:
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


async def _extract_parallel(url: str, fallback_date: Optional[str] = None) -> Optional[Article]:
    """Try Parallel.ai for reliable article extraction."""
    if not settings.parallel_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                settings.parallel_api_url,
                headers={"Authorization": f"Bearer {settings.parallel_api_key}"},
                json={"urls": [url]},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None

    results = data.get("results", [])

    if not results:
        return None

    item = results[0]
    raw_title = item.get("title")
    excerpts = item.get("excerpts", [])
    raw_body = "\n\n".join(excerpts) if excerpts else ""
    pub_date = item.get("publish_date") or fallback_date

    title, body = sanitize_article_fields(raw_title, raw_body)

    if not body or len(body) < 200:
        return None

    return Article(
        title=title,
        url=url,
        body=body,
        publication_date=pub_date,
    )


async def _extract_httpx(result: NewsSearchResult) -> Optional[Article]:
    """Fallback raw scraper using httpx + BeautifulSoup + html2text."""
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(result.url)
            response.raise_for_status()
            html = response.text
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")

    for selector in ["script", "style", "nav", "footer", "aside", "header", ".ad", ".advertisement"]:
        for element in soup.select(selector):
            element.decompose()

    raw_title = soup.title.get_text(strip=True) if soup.title else result.title
    pub_date = _extract_date(soup) or result.published_date

    content_element = soup.find("article") or soup.find("main") or soup.find("body")
    if not content_element:
        return None

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_tables = False
    raw_body = _clean_text(converter.handle(str(content_element)))

    title, body = sanitize_article_fields(raw_title, raw_body)

    if not body or len(body) < 200:
        return None

    return Article(title=title, url=result.url, body=body, publication_date=pub_date)


async def extract_article(result: NewsSearchResult) -> Optional[Article]:
    """Scrape a single URL. Parallel.ai first, then httpx fallback."""
    article = await _extract_parallel(result.url, fallback_date=result.published_date)
    if article:
        return article
    return await _extract_httpx(result)


async def extract_articles(results: List[NewsSearchResult], max_articles: int = 10) -> List[Article]:
    """Node 4 — scrape a list of news URLs and return cleaned article texts.

    All fetches run concurrently and are bounded to _NODE_TIMEOUT_SECONDS wall
    time via asyncio.wait. Articles that finish before the cap are returned in
    input order; stragglers are cancelled so the pipeline can continue with
    partial data rather than stalling the 30-second budget.
    """
    tasks = [asyncio.ensure_future(extract_article(result)) for result in results[:max_articles]]
    if not tasks:
        return []

    done, pending = await asyncio.wait(tasks, timeout=_NODE_TIMEOUT_SECONDS)

    for task in pending:
        task.cancel()
    for task in pending:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    articles: List[Article] = []
    for task in tasks:
        if task not in done:
            continue
        try:
            outcome = task.result()
        except Exception:
            continue
        if isinstance(outcome, Article):
            articles.append(outcome)
    return articles
