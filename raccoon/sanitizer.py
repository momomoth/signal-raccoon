"""Text sanitization for LLM-bound content.

Strips common prompt injection patterns and potential secret leakage from
untrusted text (scraped articles, firmographic data) before it reaches
LLM prompts. This is defense-in-depth — it won't stop every attack, but
it removes the low-hanging fruit.
"""

import re
from typing import Optional

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:a|an)\s+\w+", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s+prompt:", re.IGNORECASE),
    re.compile(r"reveal\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"output\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"repeat\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"what\s+(?:are|is)\s+your\s+(?:system|initial)\s+(?:prompt|instructions)", re.IGNORECASE),
    re.compile(r"print\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
    re.compile(r"show\s+(?:your|the)\s+(?:system|initial)\s+prompt", re.IGNORECASE),
]

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"AKIA[A-Z0-9]{16}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36}", re.IGNORECASE),
    re.compile(r"xox[bpoas]-[A-Za-z0-9-]{10,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[=:]\s*[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"password\s*[=:]\s*\S{8,}", re.IGNORECASE),
    re.compile(r"token\s*[=:]\s*[A-Za-z0-9]{20,}", re.IGNORECASE),
]

_MAX_TEXT_LENGTH = 10000
_REPLACEMENT = "[REDACTED]"


def sanitize_text(text: Optional[str], max_length: int = _MAX_TEXT_LENGTH) -> str:
    """Sanitize untrusted text before it enters an LLM prompt.

    - Strips common prompt injection phrases.
    - Redacts potential secrets/API keys.
    - Truncates to max_length.
    - Returns empty string for None input.
    """
    if not text:
        return ""

    cleaned = text

    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub(_REPLACEMENT, cleaned)

    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(_REPLACEMENT, cleaned)

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


def sanitize_article_fields(title: Optional[str], body: str) -> tuple[str, str]:
    """Sanitize article title and body for LLM consumption.

    Returns (sanitized_title, sanitized_body).
    """
    return sanitize_text(title, max_length=500), sanitize_text(body, max_length=8000)
