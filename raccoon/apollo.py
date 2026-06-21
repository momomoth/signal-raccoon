from typing import Optional

import httpx

from raccoon.config import settings
from raccoon.models import Firmographics


def _clean(value) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


async def enrich_company(website: str, linkedin: str) -> Firmographics:
    """Node 1 — Apollo API enrichment.

    Uses the company LinkedIn URL when available, otherwise falls back to domain.
    Returns a structured Firmographics object; if the key is missing or the call
    fails, returns an empty Firmographics with whatever we could infer.
    """
    if not settings.apollo_api_key:
        return Firmographics(raw={"error": "APOLLO_API_KEY not configured"})

    params = {}
    if linkedin:
        params["linkedin_url"] = linkedin
    elif website:
        params["domain"] = (
            website.replace("https://", "").replace("http://", "").split("/")[0]
        )

    headers = {
        "X-Api-Key": settings.apollo_api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                settings.apollo_enrich_url, params=params, headers=headers
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Apollo enrichment failed: HTTP {exc.response.status_code}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Apollo enrichment failed: {type(exc).__name__}"
        ) from exc

    org = data.get("organization", {}) if isinstance(data, dict) else {}

    return Firmographics(
        name=_clean(org.get("name")),
        industry=_clean(org.get("industry")),
        employee_count=_clean(
            org.get("estimated_num_employees") or org.get("employee_count")
        ),
        revenue=_clean(org.get("annual_revenue_printed") or org.get("revenue")),
        funding_stage=_clean(org.get("funding_stage")),
        technologies=org.get("technologies", [])
        if isinstance(org.get("technologies"), list)
        else [],
        raw=data,
    )
