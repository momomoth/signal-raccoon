"""Slack Block Kit formatter for ConsolidatedReport.

Pure Python, no LLM, deterministic. Converts a ConsolidatedReport into
Slack Block Kit JSON suitable for posting via response_url or webhook.
"""

from typing import List, Optional

from raccoon.models import ConsolidatedReport, IntentSignal

_TIER_EMOJI = {
    "strong": "🟢",
    "good": "🟡",
    "okay": "🛑",
    "poor": "🔴",
    "no_data": "❓",
}

_STANCE_EMOJI = {
    "prioritize": "🎯",
    "include": "📋",
    "nurture": "🌱",
    "deprioritize": "⏸️",
    "insufficient": "❓",
}

_STANCE_DESCRIPTION = {
    "prioritize": "Prioritize — reach out within 48 hours",
    "include": "Include in active sequence",
    "nurture": "Add to nurture, check back in 30 days",
    "deprioritize": "Deprioritize — re-scan if circumstances change",
    "insufficient": "Insufficient data to recommend action",
}


def _first_sentence(text: str) -> str:
    """Extract the first sentence from a string."""
    if not text:
        return ""
    for delimiter in [". ", ".\n", "! ", "? "]:
        idx = text.find(delimiter)
        if idx != -1:
            return text[:idx + 1].strip()
    return text.strip()


def _last_sentence(text: str) -> str:
    """Extract the last sentence from a string."""
    if not text:
        return ""
    for delimiter in [". ", ".\n", "! ", "? "]:
        idx = text.rfind(delimiter)
        if idx != -1:
            return text[idx + 1:].strip()
    return text.strip()


def _strip_summary_prefix(text: str) -> str:
    """Remove leading **Summary:** or similar artifacts."""
    if not text:
        return text
    stripped = text.strip()
    if stripped.startswith("**Summary:**"):
        return stripped[len("**Summary:**"):].strip()
    if stripped.startswith("Summary:"):
        return stripped[len("Summary:"):].strip()
    return stripped


def _build_narrative(report: ConsolidatedReport) -> str:
    """Compose 2-3 sentences from the best available evidence."""
    sentences: List[str] = []

    if report.intent_signals:
        sorted_signals = sorted(report.intent_signals, key=lambda s: s.severity, reverse=True)
        first = _first_sentence(sorted_signals[0].evidence)
        if first:
            sentences.append(first)

        if len(sorted_signals) >= 2:
            second = _first_sentence(sorted_signals[1].evidence)
            if second:
                sentences.append(second)

    profile = report.firmographic_profile
    if profile is not None and profile.data_quality != "missing":
        for cat in profile.categories:
            if cat.category == "data_sensitivity" and cat.data_quality == "present" and cat.score >= 7:
                items = cat.evidence[:3]
                if items:
                    if len(items) >= 3:
                        safety = f"They handle {items[0]}, {items[1]}, and {items[2]} data."
                    elif len(items) == 2:
                        safety = f"They handle {items[0]} and {items[1]} data."
                    else:
                        safety = f"They handle {items[0]} data."
                    sentences.append(safety)
                break

    if sentences:
        return " ".join(sentences)

    if profile is not None and profile.data_quality != "missing":
        return (
            f"{report.company} shows structural SSPM fit "
            f"({report.firmographic_score}/100 firmographic) but no recent "
            f"behavioral signals were detected. Worth monitoring."
        )

    return f"Insufficient data available for {report.company}. Try providing a LinkedIn URL for better enrichment."


def _top_signal(report: ConsolidatedReport) -> Optional[IntentSignal]:
    """Return the highest-severity signal, or None."""
    if not report.intent_signals:
        return None
    return sorted(report.intent_signals, key=lambda s: s.severity, reverse=True)[0]


def _top_signal_angle(top: IntentSignal) -> str:
    """Extract the outreach hook from the top signal's evidence."""
    return _last_sentence(top.evidence)


def build_slack_blocks(report: ConsolidatedReport) -> List[dict]:
    """Return a Slack Block Kit payload for a ConsolidatedReport."""
    blocks: List[dict] = []

    tier_emoji = _TIER_EMOJI.get(report.fit_tier, "❓")
    stance_emoji = _STANCE_EMOJI.get(report.outreach_stance, "❓")
    stance_desc = _STANCE_DESCRIPTION.get(report.outreach_stance, "No recommendation")

    # Edge case: no data at all
    if report.fit_tier == "no_data":
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"❓ *{report.company}* — No data available"},
        })
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Try providing a LinkedIn URL for better enrichment."}],
        })
        return blocks

    # 1. Header block
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{tier_emoji} *{report.company} — {report.final_score}/100 ({report.fit_tier})*",
        },
    })

    # 2. Narrative block
    narrative = _build_narrative(report)
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": narrative},
    })

    # 3. Top signal context (only if signals exist)
    top = _top_signal(report)
    if top:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Top signal: *{top.signal_type}* ({top.severity}/10)"},
                {"type": "mrkdwn", "text": f"— {top.title}"},
            ],
        })

    # 4. Divider
    blocks.append({"type": "divider"})

    # 5. Action block
    action_text = f"{stance_emoji} ACTION: {stance_desc}"
    if report.outreach_stance in ("prioritize", "include") and top:
        angle = _top_signal_angle(top)
        if angle:
            action_text += f"\nLead with: {angle}"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": action_text},
    })

    # 6. Footer context
    firmo_composite = (
        report.firmographic_profile.composite_score
        if report.firmographic_profile and report.firmographic_profile.data_quality != "missing"
        else 0
    )
    firmo_display = f"{firmo_composite}/100" if firmo_composite > 0 else "N/A"
    footer_parts = [f"{report.articles_considered} articles", f"firmo fit: {firmo_display}", report.outreach_stance]
    footer_text = " · ".join(footer_parts)

    if report.data_flags:
        flags = ", ".join(f.strip('"') for f in report.data_flags)
        footer_text += f" · flags: {flags}"

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": footer_text}],
    })

    return blocks
