import asyncio
from typing import List

from raccoon.apollo import enrich_company
from raccoon.consolidation import consolidate
from raccoon.firmographic_profiler import profile_firmographics
from raccoon.intent_analyzer import analyze_intent
from raccoon.models import CompanyInput, ConsolidatedReport, Firmographics, IntentAnalysisResult
from raccoon.news_extract import extract_articles
from raccoon.news_search import search_news
from raccoon.summarizer import summarize_company


async def run_intent_pipeline(company_input: CompanyInput) -> ConsolidatedReport:
    """Run the full Signal Raccoon buyer-intent pipeline."""
    errors: List[str] = []
    company = company_input.company
    website = company_input.website
    linkedin = company_input.linkedin

    # Node 1: firmographics
    try:
        firmographics = await enrich_company(website=website, linkedin=linkedin)
    except Exception as e:
        errors.append(str(e))
        firmographics = Firmographics()

    # Node 2: company summary
    try:
        summary = await summarize_company(
            company=company, website=website, firmographics=firmographics
        )
    except Exception as e:
        errors.append(str(e))
        summary = ""

    # Node 3: news search
    try:
        news_results = await search_news(company=company, summary=summary)
    except Exception as e:
        errors.append(str(e))
        news_results = []

    # Node 4: article extraction
    try:
        articles = await extract_articles(news_results)
    except Exception as e:
        errors.append(str(e))
        articles = []

    # Nodes 5a and 5b: run concurrently
    intent_task = analyze_intent(
        company=company,
        firmographics=firmographics,
        summary=summary,
        articles=articles,
    )
    profile_task = profile_firmographics(firmographics)

    try:
        intent_result, firmo_profile = await asyncio.gather(
            intent_task, profile_task
        )
    except Exception as e:
        errors.append(f"Parallel analysis failed: {e}")
        try:
            intent_result = await analyze_intent(
                company=company,
                firmographics=firmographics,
                summary=summary,
                articles=articles,
            )
        except Exception as e2:
            errors.append(f"Intent analysis failed: {e2}")
            intent_result = IntentAnalysisResult(
                signals=[],
                raw_intent_score=1,
                reasoning=f"Analysis error: {e2}",
            )
        try:
            firmo_profile = await profile_firmographics(firmographics)
        except Exception as e2:
            errors.append(f"Firmographic profiling failed: {e2}")
            firmo_profile = None

    # Node 6: consolidate
    return consolidate(
        company=company,
        intent_result=intent_result,
        firmographic_profile=firmo_profile,
        summary=summary,
        articles_considered=len(articles),
        errors=errors,
    )
