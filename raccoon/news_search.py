from datetime import datetime, timedelta
from typing import List

from duckduckgo_search import DDGS  # ddgs package
from tavily import TavilyClient

from raccoon.config import settings
from raccoon.models import NewsSearchResult


def _build_queries(company: str) -> List[str]:
    return [
        f"{company} AI expansion OR AI adoption",
        f"{company} breach OR data leak OR security incident",
        f"{company} CTO OR CISO OR Chief AI Officer hires",
    ]


async def _search_tavily(company: str, max_results_per_query: int) -> List[NewsSearchResult]:
    if not settings.tavily_api_key:
        return []

    client = TavilyClient(api_key=settings.tavily_api_key)
    queries = _build_queries(company)
    seen = set()
    results: List[NewsSearchResult] = []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    for query in queries:
        try:
            response = client.search(
                query,
                search_depth="basic",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                max_results=max_results_per_query,
            )
            for item in response.get("results", []):
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
        except Exception:
            continue

    return results


async def _search_duckduckgo(company: str, max_results_per_query: int) -> List[NewsSearchResult]:
    queries = _build_queries(company)
    seen = set()
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


async def search_news(company: str, summary: str, max_results_per_query: int = 5) -> List[NewsSearchResult]:
    """Node 3 — news search.

    Tavily is the primary search provider. DuckDuckGo is used as a keyless fallback
    so the pipeline still runs locally before a Tavily key is configured.
    """
    results = await _search_tavily(company, max_results_per_query)
    if results:
        return results
    return await _search_duckduckgo(company, max_results_per_query)
