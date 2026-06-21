"""Input normalization and validation for the Signal Raccoon pipeline.

This module owns the canonical rules for what makes a valid pipeline request.
It keeps app.py thin and makes the validation logic reusable across callers
(Hermes skill, Slack command, webhooks, etc.).
"""

from fastapi import HTTPException

from raccoon.models import CompanyInput


def normalize_company_input(payload: CompanyInput) -> CompanyInput:
    """Validate and normalize a CompanyInput payload.

    Rules:
    - ``company`` must be a non-empty string.
    - At least one of ``website`` or ``linkedin`` must be provided.

    Whitespace is stripped from string fields before checking.
    """
    payload.company = payload.company.strip()
    payload.website = payload.website.strip() if payload.website else ""
    payload.linkedin = payload.linkedin.strip() if payload.linkedin else ""

    if not payload.company:
        raise HTTPException(status_code=422, detail="company name is required")

    if not payload.website and not payload.linkedin:
        raise HTTPException(
            status_code=422, detail="website or linkedin URL is required"
        )

    return payload
