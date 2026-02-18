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
  "document_type": "<MUST be exactly one of: bill, invoice, receipt, bank_statement, insurance, medical, tax, legal, correspondence, report, other>",
  "suggested_name": "<descriptive human-readable filename WITHOUT extension or date. Use natural title case with spaces. Do NOT include dates — the date is stored separately in metadata.>",
  "suggested_tags": ["<list of 2-5 relevant lowercase tags>"],
  "extracted_metadata": {
    "company": "<company/organization name or null>",
    "date": "<document date as YYYY-MM-DD or null>",
    "amount": "<monetary amount as string like '$123.45' or null>",
    "account_number": "<account/reference number or null>",
    "due_date": "<payment due date as YYYY-MM-DD or null — only for bills/invoices>",
    "payment_url": "<payment URL found in the document or null — only for bills/invoices>",
    "summary": "<one-sentence summary of the document>"
  },
  "confidence_score": <float 0.0 to 1.0 indicating analysis confidence>
}

Document types (pick the best fit):
- bill: a request for payment — utility bills, phone bills, medical/dental/hospital bills, any statement requesting payment or showing an amount due. If a document requests payment or shows a balance due, classify it as "bill" even if the content is medical, dental, or insurance-related.
- invoice: an itemized bill from a vendor or contractor
- receipt: proof of payment already made
- bank_statement: bank or credit card account statement
- insurance: insurance paperwork that is NOT a bill — pre-auth approvals, EOBs, claims, coverage letters, policy documents. If the insurance document requests payment or shows a balance due, use "bill" instead.
- medical: medical records, lab results, prescriptions, doctor's notes — NOT bills or insurance paperwork. If the medical document requests payment or shows a balance due, use "bill" instead.
- tax: tax returns, W-2s, 1099s, tax notices
- legal: contracts, court documents, legal notices
- correspondence: letters, newsletters, general communications
- report: reports, analyses, summaries
- other: none of the above

IMPORTANT: The key distinction for "bill" vs other types is whether the document requests payment or shows an amount due. A medical statement showing a balance due is a "bill", not "medical". An insurance EOB showing a patient responsibility amount is a "bill", not "insurance".

Rules:
- CRITICAL: Only use company names, dates, amounts, and other details that appear VERBATIM in the document text. NEVER guess or infer entity names that are not explicitly written in the document.
- The suggested_name MUST be based solely on information found in the document text. Use the company/organization name exactly as it appears. If no company name is clearly present, use a generic description (e.g. "Escrow Refund Check" not "Comcast Internet Bill"). Do NOT include dates in the name.
- If the OCR text is garbled or unclear, lower your confidence_score accordingly and use only the parts you can read with certainty.
- For bills and invoices, extract the payment due date as due_date. If no explicit due date, use null.
- For bills and invoices, look for payment URLs (e.g. pay.xfinity.com, online payment portals). Extract the full URL if found, otherwise use null.
- Return ONLY valid JSON, no markdown fencing, no extra text.
- If a field cannot be determined, use null (for strings) or [] (for arrays).
- The suggested_name should be human-readable and filesystem-safe (no special characters besides hyphens and underscores).
- Tags should be simple lowercase words or short phrases (e.g. "utility", "bank", "medical", "tax", "quarterly").
- confidence_score: 0.9+ for clear documents, 0.5-0.8 for partially readable, below 0.5 for unclear/garbled text.
"""


VISION_SYSTEM_PROMPT = """\
You are a document analysis assistant for a document management system.
Analyze the provided page images of a document and return a JSON object with these fields:

{
  "document_type": "<MUST be exactly one of: bill, invoice, receipt, bank_statement, insurance, medical, tax, legal, correspondence, report, other>",
  "suggested_name": "<descriptive human-readable filename WITHOUT extension or date. Use natural title case with spaces. Do NOT include dates — the date is stored separately in metadata.>",
  "suggested_tags": ["<list of 2-5 relevant lowercase tags>"],
  "extracted_metadata": {
    "company": "<company/organization name or null>",
    "date": "<document date as YYYY-MM-DD or null>",
    "amount": "<monetary amount as string like '$123.45' or null>",
    "account_number": "<account/reference number or null>",
    "due_date": "<payment due date as YYYY-MM-DD or null — only for bills/invoices>",
    "payment_url": "<payment URL found in the document or null — only for bills/invoices>",
    "summary": "<one-sentence summary of the document>"
  },
  "confidence_score": <float 0.0 to 1.0 indicating analysis confidence>
}

Document types (pick the best fit):
- bill: a request for payment — utility bills, phone bills, medical/dental/hospital bills, any statement requesting payment or showing an amount due. If a document requests payment or shows a balance due, classify it as "bill" even if the content is medical, dental, or insurance-related.
- invoice: an itemized bill from a vendor or contractor
- receipt: proof of payment already made
- bank_statement: bank or credit card account statement
- insurance: insurance paperwork that is NOT a bill — pre-auth approvals, EOBs, claims, coverage letters, policy documents. If the insurance document requests payment or shows a balance due, use "bill" instead.
- medical: medical records, lab results, prescriptions, doctor's notes — NOT bills or insurance paperwork. If the medical document requests payment or shows a balance due, use "bill" instead.
- tax: tax returns, W-2s, 1099s, tax notices
- legal: contracts, court documents, legal notices
- correspondence: letters, newsletters, general communications
- report: reports, analyses, summaries
- other: none of the above

IMPORTANT: The key distinction for "bill" vs other types is whether the document requests payment or shows an amount due. A medical statement showing a balance due is a "bill", not "medical". An insurance EOB showing a patient responsibility amount is a "bill", not "insurance".

Rules:
- CRITICAL: Only use company names, dates, amounts, and other details that are VISIBLE in the document images. NEVER guess or infer entity names that do not appear in the document.
- The suggested_name MUST be based solely on information found in the document. Use the company/organization name exactly as it appears. If no company name is clearly visible, use a generic description (e.g. "Escrow Refund Check" not "Comcast Internet Bill"). Do NOT include dates in the name.
- If parts of the document are blurry or hard to read, lower your confidence_score accordingly and use only the parts you can read with certainty.
- Examine the visual layout, tables, logos, and any text visible in the images.
- For bills and invoices, extract the payment due date as due_date. If no explicit due date, use null.
- For bills and invoices, look for payment URLs (e.g. pay.xfinity.com, online payment portals). Extract the full URL if found, otherwise use null.
- Return ONLY valid JSON, no markdown fencing, no extra text.
- If a field cannot be determined, use null (for strings) or [] (for arrays).
- The suggested_name should be human-readable and filesystem-safe (no special characters besides hyphens and underscores).
- Tags should be simple lowercase words or short phrases (e.g. "utility", "bank", "medical", "tax", "quarterly").
- confidence_score: 0.9+ for clear documents, 0.5-0.8 for partially readable, below 0.5 for unclear/blurry images.
"""


def _build_user_message(
    text: str, original_filename: str, max_text_length: int = 4000
) -> str:
    """Build the user message containing document text for analysis."""
    truncated = text[:max_text_length]
    was_truncated = len(text) > max_text_length
    parts = [
        f"Original filename: {original_filename}",
        "",
        "--- Document Text ---",
        truncated,
    ]
    if was_truncated:
        parts.append(
            f"\n[Text truncated at {max_text_length} characters out of {len(text)} total]"
        )
    return "\n".join(parts)


# -- Result dataclass ------------------------------------------------------


@dataclass
class AIAnalysisResult:
    suggested_name: str | None = None
    document_type: str | None = None
    suggested_tags: list[str] = field(default_factory=list)
    extracted_metadata: dict = field(default_factory=dict)
    confidence_score: float = 0.0


# -- Config helper ---------------------------------------------------------


def _load_ai_config() -> dict:
    """Load AI config from DB settings service (with env var fallback).

    Opens a short-lived DB session to read settings, then closes it.
    """
    try:
        from app.core.settings_service import get_ai_config
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            return get_ai_config(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "Failed to load AI config from DB, falling back to env vars: %s", exc
        )
        return {
            "ai_provider": settings.AI_PROVIDER,
            "ai_api_key": settings.AI_API_KEY,
            "ai_model": settings.AI_MODEL,
            "ai_base_url": settings.AI_BASE_URL,
            "ai_max_text_length": str(settings.AI_MAX_TEXT_LENGTH),
            "ai_timeout": str(settings.AI_TIMEOUT),
            "ai_max_pages": str(settings.AI_MAX_PAGES),
            "ai_vision_dpi": str(settings.AI_VISION_DPI),
            "ai_vision_model": settings.AI_VISION_MODEL,
        }


# -- Provider implementations ---------------------------------------------


def _call_openai(text: str, original_filename: str, config: dict) -> str:
    """Call OpenAI chat completions API and return the raw response text."""
    from openai import OpenAI

    client = OpenAI(
        api_key=config["ai_api_key"], timeout=int(config.get("ai_timeout") or 60)
    )
    model = config.get("ai_model") or "gpt-4o-mini"
    max_text = int(config.get("ai_max_text_length") or 4000)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_message(text, original_filename, max_text),
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _call_anthropic(text: str, original_filename: str, config: dict) -> str:
    """Call Anthropic messages API and return the raw response text."""
    from anthropic import Anthropic

    client = Anthropic(
        api_key=config["ai_api_key"], timeout=int(config.get("ai_timeout") or 60)
    )
    model = config.get("ai_model") or "claude-sonnet-4-5-20250929"
    max_text = int(config.get("ai_max_text_length") or 4000)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_message(text, original_filename, max_text),
            },
        ],
        temperature=0.2,
    )
    return response.content[0].text


def _call_ollama(text: str, original_filename: str, config: dict) -> str:
    """Call Ollama via its OpenAI-compatible API and return the raw response text."""
    from openai import OpenAI

    raw_base = config.get("ai_base_url") or ""
    base_url = raw_base.rstrip("/") + "/v1" if raw_base else "http://localhost:11434/v1"
    client = OpenAI(
        api_key="ollama", base_url=base_url, timeout=int(config.get("ai_timeout") or 60)
    )
    model = config.get("ai_model") or "llama3.2"
    max_text = int(config.get("ai_max_text_length") or 4000)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_message(text, original_filename, max_text),
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


_PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
}


# -- Vision provider implementations --------------------------------------


def _call_openai_vision(images: list[str], original_filename: str, config: dict) -> str:
    """Call OpenAI with vision content blocks."""
    from openai import OpenAI

    client = OpenAI(
        api_key=config["ai_api_key"], timeout=int(config.get("ai_timeout") or 60)
    )
    model = config.get("ai_vision_model") or config.get("ai_model") or "gpt-4o"

    content = [{"type": "text", "text": f"Original filename: {original_filename}"}]
    for img_b64 in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high",
                },
            }
        )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _call_anthropic_vision(
    images: list[str], original_filename: str, config: dict
) -> str:
    """Call Anthropic with image content blocks."""
    from anthropic import Anthropic

    client = Anthropic(
        api_key=config["ai_api_key"], timeout=int(config.get("ai_timeout") or 60)
    )
    model = (
        config.get("ai_vision_model")
        or config.get("ai_model")
        or "claude-sonnet-4-5-20250929"
    )

    content = [{"type": "text", "text": f"Original filename: {original_filename}"}]
    for img_b64 in images:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            }
        )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=VISION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )
    return response.content[0].text


def _call_ollama_vision(images: list[str], original_filename: str, config: dict) -> str:
    """Call Ollama vision model via OpenAI-compatible API."""
    from openai import OpenAI

    raw_base = config.get("ai_base_url") or ""
    base_url = raw_base.rstrip("/") + "/v1" if raw_base else "http://localhost:11434/v1"
    client = OpenAI(
        api_key="ollama", base_url=base_url, timeout=int(config.get("ai_timeout") or 60)
    )
    model = (
        config.get("ai_vision_model") or config.get("ai_model") or "granite3.2-vision"
    )

    content = [{"type": "text", "text": f"Original filename: {original_filename}"}]
    for img_b64 in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high",
                },
            }
        )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


_VISION_PROVIDERS = {
    "openai": _call_openai_vision,
    "anthropic": _call_anthropic_vision,
    "ollama": _call_ollama_vision,
}


# -- Parse AI response ----------------------------------------------------


_VALID_DOCUMENT_TYPES = {
    "bill",
    "invoice",
    "receipt",
    "bank_statement",
    "insurance",
    "medical",
    "tax",
    "legal",
    "correspondence",
    "report",
    "other",
}

# Maps common AI-generated type variations to valid types
_DOCUMENT_TYPE_ALIASES = {
    "pre-auth letter": "insurance",
    "pre-auth": "insurance",
    "preauth": "insurance",
    "eob": "insurance",
    "explanation of benefits": "insurance",
    "claim": "insurance",
    "coverage": "insurance",
    "policy": "insurance",
    "statement": "bank_statement",
    "contract": "legal",
    "letter": "correspondence",
    "newsletter": "correspondence",
}


def _normalize_document_type(raw_type: str | None) -> str:
    """Coerce AI-generated document type to a valid enum value."""
    if not raw_type:
        return "other"
    normalized = raw_type.strip().lower()
    if normalized in _VALID_DOCUMENT_TYPES:
        return normalized
    if normalized in _DOCUMENT_TYPE_ALIASES:
        return _DOCUMENT_TYPE_ALIASES[normalized]
    # Try substring matching as fallback
    for alias, valid_type in _DOCUMENT_TYPE_ALIASES.items():
        if alias in normalized or normalized in alias:
            return valid_type
    logger.warning("Unknown document_type '%s', defaulting to 'other'", raw_type)
    return "other"


def _parse_response(raw: str) -> AIAnalysisResult:
    """Parse AI JSON response into an AIAnalysisResult."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    data = json.loads(cleaned)

    return AIAnalysisResult(
        suggested_name=data.get("suggested_name"),
        document_type=_normalize_document_type(data.get("document_type")),
        suggested_tags=data.get("suggested_tags") or [],
        extracted_metadata=data.get("extracted_metadata") or {},
        confidence_score=float(data.get("confidence_score", 0.0)),
    )


# -- Public API ------------------------------------------------------------


def analyze_document(
    text: str, original_filename: str, config: dict | None = None
) -> AIAnalysisResult:
    """Analyze document text using the configured AI provider.

    Args:
        text: Extracted document text (from OCR).
        original_filename: The original uploaded filename.
        config: Optional AI config dict. If not provided, loads from DB/env.

    Returns:
        AIAnalysisResult with classification, naming, and metadata.

    Raises:
        ValueError: If AI_PROVIDER is "none" or not configured.
        RuntimeError: If the AI call or response parsing fails.
    """
    if config is None:
        config = _load_ai_config()

    provider = (config.get("ai_provider") or "none").lower()

    if provider == "none" or not provider:
        raise ValueError("AI_PROVIDER is set to 'none' — AI analysis is disabled")

    if provider != "ollama" and not config.get("ai_api_key"):
        raise ValueError(f"AI_API_KEY is not set for provider '{provider}'")

    call_fn = _PROVIDERS.get(provider)
    if call_fn is None:
        raise ValueError(
            f"Unknown AI_PROVIDER: '{provider}'. Supported: {', '.join(_PROVIDERS)}"
        )

    model = config.get("ai_model") or "(default)"
    logger.info(
        "Calling AI provider '%s' (model: %s) for '%s'",
        provider,
        model,
        original_filename,
    )

    raw_response = call_fn(text, original_filename, config)
    logger.debug("Raw AI response: %s", raw_response[:500])

    result = _parse_response(raw_response)
    logger.info(
        "AI analysis complete: type=%s, name=%s, confidence=%.2f",
        result.document_type,
        result.suggested_name,
        result.confidence_score,
    )
    return result


def analyze_document_vision(
    images: list[str], original_filename: str, config: dict | None = None
) -> AIAnalysisResult:
    """Analyze document page images using the configured AI provider's vision model.

    Args:
        images: List of base64-encoded PNG strings (one per page).
        original_filename: The original uploaded filename.
        config: Optional AI config dict. If not provided, loads from DB/env.

    Returns:
        AIAnalysisResult with classification, naming, and metadata.

    Raises:
        ValueError: If AI_PROVIDER is "none" or not configured.
        RuntimeError: If the AI call or response parsing fails.
    """
    if config is None:
        config = _load_ai_config()

    provider = (config.get("ai_provider") or "none").lower()

    if provider == "none" or not provider:
        raise ValueError("AI_PROVIDER is set to 'none' — AI analysis is disabled")

    if provider != "ollama" and not config.get("ai_api_key"):
        raise ValueError(f"AI_API_KEY is not set for provider '{provider}'")

    call_fn = _VISION_PROVIDERS.get(provider)
    if call_fn is None:
        raise ValueError(
            f"Unknown AI_PROVIDER: '{provider}'. Supported: {', '.join(_VISION_PROVIDERS)}"
        )

    vision_model = (
        config.get("ai_vision_model") or config.get("ai_model") or "(default)"
    )
    logger.info(
        "Calling AI provider '%s' vision (model: %s) for '%s' (%d pages)",
        provider,
        vision_model,
        original_filename,
        len(images),
    )

    raw_response = call_fn(images, original_filename, config)
    logger.debug("Raw AI vision response: %s", raw_response[:500])

    result = _parse_response(raw_response)
    logger.info(
        "AI vision analysis complete: type=%s, name=%s, confidence=%.2f",
        result.document_type,
        result.suggested_name,
        result.confidence_score,
    )
    return result
