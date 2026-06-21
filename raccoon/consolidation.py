"""Consolidation layer — combines article signals and firmographic profile
into a final ConsolidatedReport. Pure Python, no LLM calls.
"""

from datetime import date
from typing import List, Optional

from raccoon.models import (
    ConsolidatedReport,
    FirmographicProfile,
    IntentAnalysisResult,
    IntentSignal,
    ScoringConfig,
)


def _compute_recency_factor(
    signals: List[IntentSignal],
    config: ScoringConfig,
) -> float:
    """Recency factor ∈ [recency_floor, recency_ceiling] based on signal dates."""
    signals_with_date = [s for s in signals if s.date is not None]
    if len(signals_with_date) == 0:
        return 1.0

    now = date.today()
    recent_count = 0
    for s in signals_with_date:
        signal_date_str = s.date
        if signal_date_str is None:
            continue
        try:
            signal_date = date.fromisoformat(signal_date_str)
            if (now - signal_date).days < config.recency_window_days:
                recent_count += 1
        except (ValueError, TypeError):
            pass

    recency_ratio = recent_count / len(signals_with_date)
    return config.recency_floor + (recency_ratio * (config.recency_ceiling - config.recency_floor))


def _compute_count_factor(n: int, config: ScoringConfig) -> float:
    """Signal volume bonus."""
    if n <= 1:
        return config.count_floor
    elif n <= 3:
        return 1.0
    elif n <= 6:
        return 1.1
    else:
        return config.count_ceiling


def _determine_fit_tier(final_score: float) -> str:
    if final_score >= 75:
        return "strong"
    elif final_score >= 55:
        return "good"
    elif final_score >= 35:
        return "okay"
    else:
        return "poor"


def _determine_outreach_stance(fit_tier: str) -> str:
    mapping = {
        "strong": "prioritize",
        "good": "include",
        "okay": "nurture",
        "poor": "deprioritize",
        "no_data": "insufficient",
    }
    return mapping.get(fit_tier, "insufficient")


def build_thesis(
    company: str,
    fit_tier: str,
    outreach_stance: str,
    intent_signals: List[IntentSignal],
    firmographic_profile: Optional[FirmographicProfile],
    data_flags: List[str],
) -> str:
    """Compose a one-paragraph narrative thesis from the strongest available evidence."""
    parts: List[str] = []

    openings = {
        "strong": f"{company} shows clear SSPM/AI security buying intent.",
        "good": f"{company} is a solid SSPM prospect worth active outreach.",
        "okay": f"{company} shows moderate SSPM relevance. Monitor for developing signals.",
        "poor": f"{company} currently shows weak SSPM buying intent.",
        "no_data": f"Insufficient data to evaluate {company} at this time.",
    }
    parts.append(openings.get(fit_tier, openings["no_data"]))

    if intent_signals:
        sorted_signals = sorted(intent_signals, key=lambda s: s.severity, reverse=True)
        top_signals = sorted_signals[:3]
        signal_strs = [
            f"{s.signal_type}: {s.title} (severity {s.severity})"
            for s in top_signals
        ]
        parts.append("Signals: " + "; ".join(signal_strs) + ".")

    if firmographic_profile is not None and firmographic_profile.data_quality != "missing":
        real_categories = [
            cat for cat in firmographic_profile.categories
            if cat.data_quality == "present" and cat.score >= 6
        ]
        sorted_cats = sorted(real_categories, key=lambda c: c.score, reverse=True)
        top_cats = sorted_cats[:2]
        if top_cats:
            cat_strs = [
                f"Strong {cat.category}: {cat.evidence[0] if cat.evidence else 'detected'} (score {cat.score}/10)"
                for cat in top_cats
            ]
            parts.append("Firmographic profile: " + "; ".join(cat_strs) + ".")
        else:
            parts.append("No significant firmographic signals detected.")

    if data_flags:
        parts.append("Note: " + "; ".join(data_flags) + ".")

    recommendations = {
        "prioritize": "Recommendation: Prioritize outreach within 48 hours. Lead with the top signal evidence.",
        "include": "Recommendation: Include in active sequence. Reference the strongest signal in opening message.",
        "nurture": "Recommendation: Add to nurture sequence. Check back in 30 days for new signals.",
        "deprioritize": "Recommendation: Deprioritize. Re-scan if circumstances change.",
        "insufficient": "Recommendation: Re-try when more data is available.",
    }
    parts.append(recommendations.get(outreach_stance, recommendations["insufficient"]))

    return " ".join(parts)


def consolidate(
    company: str,
    intent_result: IntentAnalysisResult,
    firmographic_profile: Optional[FirmographicProfile],
    summary: Optional[str],
    articles_considered: int,
    errors: List[str],
    config: Optional[ScoringConfig] = None,
) -> ConsolidatedReport:
    """Combine intent signals and firmographic profile into a final report."""
    if config is None:
        config = ScoringConfig()

    signals_exist = len(intent_result.signals) > 0
    firmo_exists = (
        firmographic_profile is not None
        and firmographic_profile.data_quality != "missing"
    )

    data_flags: List[str] = []
    if not signals_exist:
        data_flags.append("no signals found")
    if not firmo_exists:
        data_flags.append("no firmographic data available")

    if not signals_exist and not firmo_exists:
        return ConsolidatedReport(
            company=company,
            final_score=0.0,
            fit_tier="no_data",
            raw_intent_score=intent_result.raw_intent_score,
            firmographic_score=0.0,
            intent_signals=[],
            firmographic_profile=firmographic_profile,
            thesis=build_thesis(
                company, "no_data", "insufficient", [],
                firmographic_profile, data_flags,
            ),
            outreach_stance="insufficient",
            data_flags=data_flags,
            reasoning=intent_result.reasoning,
            summary=summary,
            articles_considered=articles_considered,
            errors=errors,
        )

    # Step 1: Article score
    raw_article = intent_result.raw_intent_score * 10  # 1-10 → 10-100
    recency_factor = _compute_recency_factor(intent_result.signals, config)
    count_factor = _compute_count_factor(len(intent_result.signals), config)
    article_score = raw_article * recency_factor * count_factor * config.signal_weight

    # Step 2: Firmographic score
    if firmographic_profile is not None and firmo_exists:
        firmo_score = firmographic_profile.composite_score * config.firmo_weight
    else:
        firmo_score = 0.0

    # Step 3: Final score (clamped)
    final_score = min(100.0, round(article_score + firmo_score, 1))

    # Step 4: Fit tier
    fit_tier = _determine_fit_tier(final_score)

    # Step 5: Firmographic-only cap
    if not signals_exist and firmo_exists:
        if fit_tier in ("strong", "good"):
            fit_tier = config.firmo_max_standalone_tier

    outreach_stance = _determine_outreach_stance(fit_tier)

    thesis = build_thesis(
        company, fit_tier, outreach_stance,
        intent_result.signals, firmographic_profile, data_flags,
    )

    return ConsolidatedReport(
        company=company,
        final_score=final_score,
        fit_tier=fit_tier,
        raw_intent_score=intent_result.raw_intent_score,
        firmographic_score=round(firmo_score, 1),
        intent_signals=intent_result.signals,
        firmographic_profile=firmographic_profile,
        thesis=thesis,
        outreach_stance=outreach_stance,
        data_flags=data_flags,
        reasoning=intent_result.reasoning,
        summary=summary,
        articles_considered=articles_considered,
        errors=errors,
    )
