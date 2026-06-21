# Bright Sunshine / Signal Raccoon

Buyer-intent scoring API for SSPM (SaaS Security Posture Management) sales outreach. Give it a company name and a website or LinkedIn URL - it returns a 0-100 score, fit tier, evidence-based signals, a firmographic profile, and outreach guidance.

## How It Works

The pipeline runs six stages:

1. **Apollo enrichment** - pulls firmographics (industry, revenue, headcount, tech stack, keywords) from Apollo's API
2. **Company summarizer** - DeepSeek writes a dense company summary
3. **News search** - Tavily searches for AI adoption, security incidents, and leadership hires within a 90-day window (DuckDuckGo fallback)
4. **News extraction** - Parallel.ai extracts article text (httpx + BeautifulSoup fallback)
5. **Parallel analysis:**
   - **5a. Intent analyzer (LLM):** DeepSeek scans articles for buyer intent signals and writes outreach-ready evidence
   - **5b. Firmographic profiler (Python):** scores the company across 6 dimensions (data sensitivity, infrastructure, AI stack, security maturity, exposure ratio, regulatory surface)
6. **Consolidation (Python):** combines both outputs into a final 0-100 score with fit tier, outreach stance, and a deterministic thesis

All LLM-bound text is sanitized through `raccoon/sanitizer.py` to strip prompt injection patterns and redact potential secrets. Both LLM prompts include explicit security instructions.

Scoring is deterministic - the LLM finds signals, Python does the math. Same input always produces the same score.

## Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | None | Health check |
| `/analyze-intent` | POST | `auth` header | Returns `ConsolidatedReport` JSON for direct API consumption (Clay, Hermes, webhooks) |
| `/slack/deep-dive` | POST | Slack signing secret | Slash command endpoint for Slack. Accepts `/deep-dive Company website.com`, runs the pipeline, and posts a formatted Block Kit card back to the user. Uses Slack's deferred response pattern (immediate ack, async result). |

## Slack Integration

The `/slack/deep-dive` endpoint lets a salesperson type `/deep-dive Company company.com` in any Slack channel and get a formatted buyer intent card back in ~30 seconds. The card includes the score, fit tier, top signal evidence, outreach stance, and a lead-with hint - everything a BDR needs to decide whether to reach out.

The endpoint uses Slack's deferred response pattern: it acknowledges the request within 3 seconds ("🔍 Scanning..."), then runs the pipeline as a background task and posts the formatted result to Slack's `response_url` when done. Results are ephemeral (only visible to the invoking user).

Formatting is handled by `raccoon/slack_formatter.py`, which converts a `ConsolidatedReport` into Slack Block Kit JSON - pure Python, no LLM, deterministic.

## Project Structure

```
app.py                          FastAPI entry point, endpoints, auth, rate limiting, Slack verification
raccoon/
  config.py                     Environment variable configuration (pydantic-settings)
  input.py                      Input validation and normalization
  models.py                     All Pydantic data models
  sanitizer.py                  LLM input sanitization (injection + secret stripping)
  apollo.py                     Node 1 - Apollo enrichment
  summarizer.py                 Node 2 - Company summarizer (LLM)
  news_search.py                Node 3 - News search (Tavily + DDG)
  news_extract.py               Node 4 - Article extraction (Parallel.ai + scraping)
  intent_analyzer.py            Node 5a - Buyer intent analyzer (LLM)
  firmographic_profiler.py      Node 5b - Firmographic profiler (Python)
  consolidation.py              Node 6 - Score consolidation (Python)
  keywords.py                   Keyword and technology libraries
  pipeline.py                   Orchestrator - runs nodes 1-6
  slack_formatter.py            Slack Block Kit formatter
hermes/
  signal-raccoon.md             Hermes skill wrapper
```
