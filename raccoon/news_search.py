import asyncio
from datetime import datetime, timedelta
from typing import List

from ddgs import DDGS
from tavily import AsyncTavilyClient

from raccoon.config import settings
from raccoon.models import NewsSearchResult

# Per-query Tavily timeout. The default is 60s, which is far too long when 3
# queries run before the pipeline can proceed. With queries running in
# parallel, this is the wall-clock ceiling for the whole Tavily stage.
_TAVILY_TIMEOUT_SECONDS = 15.0


def _build_queries(company: str) -> List[str]:
    return [
        f"{company} AI expansion OR AI adoption",
        f"{company} breach OR data leak OR security incident",
        f"{company} CTO OR CISO OR Chief AI Officer hires",
    ]


async def _tavily_query(
    client: AsyncTavilyClient,
    query: str,
    start_date: str,
    end_date: str,
    max_results: int,
) -> List[dict]:
    """Run a single Tavily search. Returns raw result items; the caller dedupes."""
    response = await client.search(
        query,
        search_depth="basic",
        start_date=start_date,
        end_date=end_date,
        max_results=max_results,
        timeout=_TAVILY_TIMEOUT_SECONDS,
    )
    return list(response.get("results", []))


async def _search_tavily(company: str, max_results_per_query: int) -> List[NewsSearchResult]:
    if not settings.tavily_api_key:
        return []

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    queries = _build_queries(company)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # Run all 3 signal-category queries concurrently. Each failed query is
    # returned as an exception rather than aborting the gather, so a single
    # slow/failing query does not throw away results from the other two.
    tasks = [
        _tavily_query(client, q, start_str, end_str, max_results_per_query)
        for q in queries
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    results: List[NewsSearchResult] = []
    for resp in responses:
        if not isinstance(resp, list):
            continue
        for item in resp:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(
                NewsSearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("content", ""),
                    published_date=item.get("published_date"),
                )
            )

    return results


def _ddg_search_sync(company: str, max_results_per_query: int) -> List[NewsSearchResult]:
    """Synchronous DuckDuckGo search. Run this inside to_thread, not on the loop."""
    queries = _build_queries(company)
    seen: set[str] = set()
    results: List[NewsSearchResult] = []

    with DDGS() as ddgs:
        for query in queries:
            try:
                for item in ddgs.text(query, max_results=max_results_per_query, timelimit="m"):
                    url = item.get("href", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    results.append(
                        NewsSearchResult(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("body", ""),
                        )
                    )
            except Exception:
                continue

    return results


async def _search_duckduckgo(company: str, max_results_per_query: int) -> List[NewsSearchResult]:
    """DuckDuckGo fallback. The DDGS client (v9) is sync-only, so offload to a thread."""
    return await asyncio.to_thread(_ddg_search_sync, company, max_results_per_query)


async def search_news(company: str, summary: str, max_results_per_query: int = 5) -> List[NewsSearchResult]:
    """Node 3 — news search.

    Tavily is the primary search provider and is called via its async client,
    with the three signal-category queries run concurrently via asyncio.gather.
    DuckDuckGo is used as a keyless synchronous fallback so the pipeline still
    runs locally before a Tavily key is configured; it runs on a worker thread
    to avoid blocking the event loop.
    """
    results = await _search_tavily(company, max_results_per_query)
    if results:
        return results
    return await _search_duckduckgo(company, max_results_per_query)