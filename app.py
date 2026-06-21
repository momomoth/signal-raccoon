"""Bright Sunshine / Signal Raccoon — buyer intent pipeline API.

A FastAPI service that runs the Signal Raccoon LangChain workflow, gated by a
shared secret key. Deploy on Railway. Consume via Slack slash command.
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import parse_qs

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from raccoon.config import settings
from raccoon.input import normalize_company_input
from raccoon.models import CompanyInput, ConsolidatedReport
from raccoon.pipeline import run_intent_pipeline
from raccoon.slack_formatter import build_slack_blocks

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Bright Sunshine", version="0.1.0")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "rate limit exceeded — max 5 requests per minute"},
    )


def verify_auth(auth: Optional[str] = Header(None)):
    """Gate every request with the shared secret."""
    if not auth or not secrets.compare_digest(auth, settings.app_secret):
        raise HTTPException(status_code=401, detail="invalid or missing auth key")


def verify_slack_signature(
    request: Request,
    x_slack_signature: Optional[str] = Header(None),
    x_slack_request_timestamp: Optional[str] = Header(None),
) -> None:
    """Verify that a request came from Slack using the signing secret.

    Slack signs each request with HMAC-SHA256. We reconstruct the signature
    from the raw body + timestamp and compare it. Also rejects requests
    older than 5 minutes to prevent replay attacks.

    If SLACK_SIGNING_SECRET is not configured, verification is skipped
    (useful for local development).
    """
    if not settings.slack_signing_secret:
        return

    if not x_slack_signature or not x_slack_request_timestamp:
        raise HTTPException(status_code=401, detail="missing Slack signature headers")

    try:
        timestamp = int(x_slack_request_timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="invalid timestamp")

    if abs(time.time() - timestamp) > 300:
        raise HTTPException(status_code=401, detail="request timestamp too old")

    raw_body = request._body.decode("utf-8") if request._body else ""

    basestring = f"v0:{x_slack_request_timestamp}:{raw_body}"
    computed = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode("utf-8"),
            basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    if not secrets.compare_digest(computed, x_slack_signature):
        raise HTTPException(status_code=401, detail="invalid Slack signature")


@app.get("/health")
async def health():
    """Public health check — no auth, no rate limit."""
    return {"status": "ok", "app": "bright_sunshine"}


@app.post("/analyze-intent", response_model=ConsolidatedReport)
@limiter.limit("5/minute")
async def analyze_intent_endpoint(
    request: Request,
    payload: CompanyInput,
    auth: Optional[str] = Header(None),
):
    """Run the full Signal Raccoon buyer-intent pipeline.

    Requires the shared auth secret in the `auth` header.
    Rate limited to 5 requests per minute per IP.
    """
    verify_auth(auth)
    normalized = normalize_company_input(payload)
    return await run_intent_pipeline(normalized)


@app.post("/slack/deep-dive")
@limiter.limit("5/minute")
async def slack_deep_dive(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle Slack slash command /deep-dive.

    Slack POSTs application/x-www-form-urlencoded with fields:
      text, response_url, user_id, channel_id, team_id, command

    Responds within 3s with an ack, then background-processes the
    pipeline and POSTs the real result to response_url.
    Rate limited to 5 requests per minute per IP.
    """
    raw_body = await request.body()

    verify_slack_signature(
        request,
        x_slack_signature=request.headers.get("X-Slack-Signature"),
        x_slack_request_timestamp=request.headers.get("X-Slack-Request-Timestamp"),
    )

    parsed = parse_qs(raw_body.decode("utf-8"))
    text = (parsed.get("text", [""])[0]).strip()
    response_url = (parsed.get("response_url", [""])[0]).strip()
    user_id = (parsed.get("user_id", ["unknown"])[0]).strip()

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return {
            "response_type": "ephemeral",
            "text": (
                ":warning: I need a company name AND a website or LinkedIn URL.\n"
                "Example: `/deep-dive Justworks justworks.com`\n"
                "Example: `/deep-dive Acme linkedin.com/company/acme`"
            ),
        }

    company = parts[0].strip()
    url = parts[1].strip()

    if "linkedin.com" in url.lower():
        company_input = CompanyInput(company=company, website="", linkedin=url)
    else:
        company_input = CompanyInput(company=company, website=url, linkedin="")

    try:
        normalized = normalize_company_input(company_input)
    except HTTPException:
        return {
            "response_type": "ephemeral",
            "text": (
                ":warning: I need a company name AND a website or LinkedIn URL.\n"
                "Example: `/deep-dive Justworks justworks.com`"
            ),
        }

    background_tasks.add_task(
        _run_pipeline_and_post_to_slack,
        response_url=response_url,
        company_input=normalized,
        user_id=user_id,
    )

    return {
        "response_type": "ephemeral",
        "text": f"🔍 Scanning *{company}* — this takes about 30 seconds. I'll update you here.",
    }


async def _run_pipeline_and_post_to_slack(
    response_url: str,
    company_input: CompanyInput,
    user_id: str,
):
    """Background task: run the pipeline and POST the result to Slack."""
    try:
        report = await run_intent_pipeline(company_input)
        blocks = build_slack_blocks(report)
        payload = {
            "response_type": "ephemeral",
            "blocks": blocks,
            "text": f"Signal Raccoon: {report.company} — {report.final_score}/100 ({report.fit_tier})",
        }
    except Exception as e:
        payload = {
            "response_type": "ephemeral",
            "text": f":x: Signal Raccoon hit an error scanning *{company_input.company}*:\n```{e}```",
        }

    if not response_url:
        return

    try:
        async with httpx.AsyncClient() as client:
            await client.post(response_url, json=payload, timeout=10.0)
    except Exception:
        pass
