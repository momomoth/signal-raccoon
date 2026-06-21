"""Firmographic profiler — deterministic categorical scoring from Apollo data.

Reads ``Firmographics.raw.organization`` and produces a ``FirmographicProfile``
with 6 categorical scores (0-10 each). No LLM calls. Pure Python.
"""

from typing import List, Optional

from raccoon.keywords import (
    AI_STACK_TECHS,
    INFRASTRUCTURE_TECHS,
    REGULATORY_KEYWORDS,
    SECURITY_TECHS,
    SENSITIVITY_KEYWORDS,
    HIGH_REGULATION_INDUSTRIES,
)
from raccoon.models import CategoryScore, Firmographics, FirmographicProfile


def _match_keywords(company_keywords: List[str], library: List[str]) -> List[str]:
    """Case-insensitive substring match. Returns list of matched library terms."""
    matched = []
    lower_company = " ".join(company_keywords).lower()
    for term in library:
        if term.lower() in lower_company:
            matched.append(term)
    return matched


def _match_techs(technologies: list, library: List[str]) -> List[str]:
    """Match library terms against the `name` field of technology entries."""
    tech_names = []
    for tech in technologies:
        if isinstance(tech, dict):
            name = tech.get("name", "")
            if name:
                tech_names.append(name)
    matched = []
    lower_techs = " ".join(tech_names).lower()
    for term in library:
        if term.lower() in lower_techs:
            matched.append(term)
    return matched


def _score_category(
    category: str,
    match_count: int,
    multiplier: int,
    evidence: List[str],
    weight: float,
    has_data: bool,
) -> CategoryScore:
    if not has_data:
        return CategoryScore(
            category=category,
            score=5,
            max_possible=10,
            evidence=[],
            weight=weight,
            data_quality="defaulted",
        )
    score = min(10, match_count * multiplier)
    return CategoryScore(
        category=category,
        score=score,
        max_possible=10,
        evidence=evidence[:10],
        weight=weight,
        data_quality="present" if match_count > 0 else "present",
    )


def _score_sensitivity(keywords: List[str]) -> CategoryScore:
    has_data = len(keywords) > 0
    matched = _match_keywords(keywords, SENSITIVITY_KEYWORDS) if has_data else []
    return _score_category("data_sensitivity", len(matched), 1, matched, 1.0, has_data)


def _score_infrastructure(technologies: list) -> CategoryScore:
    has_data = len(technologies) > 0
    matched = _match_techs(technologies, INFRASTRUCTURE_TECHS) if has_data else []
    return _score_category("infrastructure_scale", len(matched), 1, matched, 1.0, has_data)


def _score_ai_stack(technologies: list) -> CategoryScore:
    has_data = len(technologies) > 0
    matched = _match_techs(technologies, AI_STACK_TECHS) if has_data else []
    return _score_category("ai_stack_presence", len(matched), 1, matched, 1.0, has_data)


def _score_security_maturity(technologies: list) -> CategoryScore:
    has_data = len(technologies) > 0
    matched = _match_techs(technologies, SECURITY_TECHS) if has_data else []
    return _score_category("security_maturity", len(matched), 1, matched, 1.0, has_data)


def _score_exposure_ratio(dept_headcount: dict) -> CategoryScore:
    if not dept_headcount:
        return CategoryScore(
            category="exposure_ratio",
            score=5,
            max_possible=10,
            evidence=[],
            weight=0.7,
            data_quality="defaulted",
        )

    eng = dept_headcount.get("engineering", 0)
    ds = dept_headcount.get("data_science", 0)
    pm = dept_headcount.get("product_management", 0)
    it = dept_headcount.get("information_technology", 0)

    required_keys = ["engineering", "data_science", "product_management", "information_technology"]
    if not all(k in dept_headcount for k in required_keys):
        return CategoryScore(
            category="exposure_ratio",
            score=5,
            max_possible=10,
            evidence=[],
            weight=0.7,
            data_quality="defaulted",
        )

    numerator = eng + ds + pm
    denominator = max(1, it)
    ratio = numerator / denominator

    if ratio > 20:
        score = 9
    elif ratio > 10:
        score = 7
    elif ratio > 5:
        score = 5
    elif ratio > 2:
        score = 3
    else:
        score = 1

    evidence = [f"{ratio:.1f}:1 ({numerator} eng+ds+pm vs {it} it)"]

    return CategoryScore(
        category="exposure_ratio",
        score=score,
        max_possible=10,
        evidence=evidence,
        weight=0.7,
        data_quality="present",
    )


def _score_regulatory_surface(org: dict, sensitivity_matches: List[str]) -> CategoryScore:
    score = 0
    evidence = []

    symbol = org.get("publicly_traded_symbol")
    if symbol is not None:
        score += 3
        evidence.append(f"Public company ({symbol})")

    industry = org.get("industry", "")
    if industry and industry.lower() in [i.lower() for i in HIGH_REGULATION_INDUSTRIES]:
        score += 2
        evidence.append(f"Industry: {industry}")

    regulatory_matches = [m for m in sensitivity_matches if m in REGULATORY_KEYWORDS]
    if regulatory_matches:
        score += 2
        evidence.append(f"Keywords: {', '.join(regulatory_matches[:5])}")

    framework_keywords = ["HIPAA", "SOX", "GDPR", "PCI", "FedRAMP", "SOC", "FINRA", "GLBA", "CCPA"]
    company_keywords = org.get("keywords", [])
    if company_keywords:
        lower_keywords = " ".join(company_keywords).lower()
        framework_hits = [kw for kw in framework_keywords if kw.lower() in lower_keywords]
        if framework_hits:
            score += 3
            evidence.append(f"Frameworks: {', '.join(framework_hits)}")

    score = min(10, score)

    has_data = bool(industry or symbol or company_keywords)

    return CategoryScore(
        category="regulatory_surface",
        score=score if has_data else 5,
        max_possible=10,
        evidence=evidence[:10],
        weight=0.8,
        data_quality="present" if has_data else "defaulted",
    )


def _compute_composite(categories: List[CategoryScore]) -> float:
    weighted_sum = sum(cat.score * cat.weight for cat in categories)
    weight_total = sum(cat.weight for cat in categories)
    if weight_total == 0:
        return 50.0
    average = weighted_sum / weight_total
    return round(average * 10, 1)


async def profile_firmographics(firmographics: Optional[Firmographics]) -> FirmographicProfile:
    """Produce a FirmographicProfile from Apollo firmographics data.

    If firmographics is None or raw is empty, returns a missing profile
    with all categories defaulted to 5 and composite_score = 50.
    """
    if firmographics is None or not firmographics.raw:
        categories = [
            CategoryScore(category=c, score=5, max_possible=10, evidence=[], weight=w, data_quality="defaulted")
            for c, w in [
                ("data_sensitivity", 1.0),
                ("infrastructure_scale", 1.0),
                ("ai_stack_presence", 1.0),
                ("security_maturity", 1.0),
                ("exposure_ratio", 0.7),
                ("regulatory_surface", 0.8),
            ]
        ]
        return FirmographicProfile(
            categories=categories,
            composite_score=50.0,
            data_quality="missing",
        )

    org = firmographics.raw.get("organization", {})
    if not org:
        org = firmographics.raw

    keywords = org.get("keywords", [])
    technologies = org.get("current_technologies", [])
    dept_headcount = org.get("departmental_head_count", {})

    cat_sensitivity = _score_sensitivity(keywords)
    cat_infrastructure = _score_infrastructure(technologies)
    cat_ai = _score_ai_stack(technologies)
    cat_security = _score_security_maturity(technologies)
    cat_exposure = _score_exposure_ratio(dept_headcount)

    sensitivity_matches = _match_keywords(keywords, SENSITIVITY_KEYWORDS)
    cat_regulatory = _score_regulatory_surface(org, sensitivity_matches)

    categories = [
        cat_sensitivity,
        cat_infrastructure,
        cat_ai,
        cat_security,
        cat_exposure,
        cat_regulatory,
    ]

    present_count = sum(1 for c in categories if c.data_quality == "present")
    if present_count == 6:
        data_quality = "full"
    elif present_count == 0:
        data_quality = "missing"
    else:
        data_quality = "partial"

    composite = _compute_composite(categories)

    if data_quality == "missing":
        composite = 50.0

    return FirmographicProfile(
        categories=categories,
        composite_score=composite,
        data_quality=data_quality,
    )
