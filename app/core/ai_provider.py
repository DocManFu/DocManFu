"""AI provider abstraction for document analysis.

Supports OpenAI and Anthropic APIs.  Set ``AI_PROVIDER`` in .env to
"openai" or "anthropic" (or "none" to disable).
"""

import json
import logging
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# -- Prompt template -------------------------------------------------------

SYSTEM_PROMPT = """\
You are a document analysis assistant for a document management system.
Analyze the provided document text and return a JSON object with these fields:

{
  "document_type": "<one of: bill, bank_statement, medical, insurance, tax, invoice, receipt, legal, correspondence, report, other>",
  "suggested_name": "<descriptive filename WITHOUT extension, using format: YYYY-MM-DD_Company_DocumentType, e.g. 2024-03-15_Comcast_Internet_Bill>",
  "suggested_tags": ["<list of 2-5 relevant lowercase tags>"],
  "extracted_metadata": {
    "company": "<company/organization name or null>",
    "date": "<document date as YYYY-MM-DD or null>",
    "amount": "<monetary amount as string like '$123.45' or null>",
    "account_number": "<account/reference number or null>",
    "summary": "<one-sentence summary of the document>"
  },
  "confidence_score": <float 0.0 to 1.0 indicating analysis confidence>
}

Rules:
- Return ONLY valid JSON, no markdown fencing, no extra text.
- If a field cannot be determined, use null (for strings) or [] (for arrays).
- The suggested_name should be human-readable and filesystem-safe (no special characters besides hyphens and underscores).
- Tags should be simple lowercase words or short phrases (e.g. "utility", "bank", "medical", "tax", "quarterly").
- confidence_score: 0.9+ for clear documents, 0.5-0.8 for partially readable, below 0.5 for unclear.
"""


def _build_user_message(text: str, original_filename: str) -> str:
    """Build the user message containing document text for analysis."""
    truncated = text[: settings.AI_MAX_TEXT_LENGTH]
    was_truncated = len(text) > settings.AI_MAX_TEXT_LENGTH
    parts = [
        f"Original filename: {original_filename}",
        "",
        "--- Document Text ---",
        truncated,
    ]
    if was_truncated:
        parts.append(f"\n[Text truncated at {settings.AI_MAX_TEXT_LENGTH} characters out of {len(text)} total]")
    return "\n".join(parts)


# -- Result dataclass ------------------------------------------------------


@dataclass
class AIAnalysisResult:
    suggested_name: str | None = None
    document_type: str | None = None
    suggested_tags: list[str] = field(default_factory=list)
    extracted_metadata: dict = field(default_factory=dict)
    confidence_score: float = 0.0


# -- Provider implementations ---------------------------------------------


def _call_openai(text: str, original_filename: str) -> str:
    """Call OpenAI chat completions API and return the raw response text."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.AI_API_KEY, timeout=settings.AI_TIMEOUT)
    model = settings.AI_MODEL or "gpt-4o-mini"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(text, original_filename)},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _call_anthropic(text: str, original_filename: str) -> str:
    """Call Anthropic messages API and return the raw response text."""
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.AI_API_KEY, timeout=settings.AI_TIMEOUT)
    model = settings.AI_MODEL or "claude-sonnet-4-5-20250929"

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_user_message(text, original_filename)},
        ],
        temperature=0.2,
    )
    return response.content[0].text


_PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
}


# -- Parse AI response ----------------------------------------------------


def _parse_response(raw: str) -> AIAnalysisResult:
    """Parse AI JSON response into an AIAnalysisResult."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)

    return AIAnalysisResult(
        suggested_name=data.get("suggested_name"),
        document_type=data.get("document_type"),
        suggested_tags=data.get("suggested_tags") or [],
        extracted_metadata=data.get("extracted_metadata") or {},
        confidence_score=float(data.get("confidence_score", 0.0)),
    )


# -- Public API ------------------------------------------------------------


def analyze_document(text: str, original_filename: str) -> AIAnalysisResult:
    """Analyze document text using the configured AI provider.

    Args:
        text: Extracted document text (from OCR).
        original_filename: The original uploaded filename.

    Returns:
        AIAnalysisResult with classification, naming, and metadata.

    Raises:
        ValueError: If AI_PROVIDER is "none" or not configured.
        RuntimeError: If the AI call or response parsing fails.
    """
    provider = settings.AI_PROVIDER.lower()

    if provider == "none" or not provider:
        raise ValueError("AI_PROVIDER is set to 'none' — AI analysis is disabled")

    if not settings.AI_API_KEY:
        raise ValueError(f"AI_API_KEY is not set for provider '{provider}'")

    call_fn = _PROVIDERS.get(provider)
    if call_fn is None:
        raise ValueError(f"Unknown AI_PROVIDER: '{provider}'. Supported: {', '.join(_PROVIDERS)}")

    logger.info("Calling AI provider '%s' (model: %s) for '%s'", provider, settings.AI_MODEL, original_filename)

    raw_response = call_fn(text, original_filename)
    logger.debug("Raw AI response: %s", raw_response[:500])

    result = _parse_response(raw_response)
    logger.info(
        "AI analysis complete: type=%s, name=%s, confidence=%.2f",
        result.document_type,
        result.suggested_name,
        result.confidence_score,
    )
    return result
