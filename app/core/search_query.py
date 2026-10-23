"""Gmail-style search query parsing.

Turns a query like ``title:utah -tag:bill "water bill" after:2024`` into
free-text (for full-text search) plus structured filter terms. Each term keeps
its character span so the UI can remove a single filter from the query.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Operator aliases -> canonical key
OPERATORS = {
    "title": "title",
    "name": "title",
    "ocr": "ocr",
    "text": "ocr",
    "content": "ocr",
    "tag": "tag",
    "type": "type",
    "company": "company",
    "from": "company",
    "notes": "notes",
    "note": "notes",
    "is": "is",
    "has": "has",
    "after": "after",
    "since": "after",
    "before": "before",
    "date": "date",
    "year": "date",
    "newer_than": "newer_than",
    "older_than": "older_than",
}

IS_VALUES = {"untagged", "untyped", "unpaid", "paid", "overdue", "dismissed", "bill"}
HAS_VALUES = {"notes", "tags", "text", "type", "due"}

# key:"quoted value" | key:value | "quoted phrase" | bare word; optional leading -
_TOKEN = re.compile(
    r'(?P<neg>-)?(?:(?P<key>[A-Za-z_]+):(?:"(?P<qval>[^"]*)"?|(?P<val>[^\s"]*))'
    r'|"(?P<phrase>[^"]*)"?|(?P<word>[^\s"]+))'
)
_DATE = re.compile(r"^(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?$")
_RELATIVE = re.compile(r"^(\d{1,6})([dwmy])$")


@dataclass
class Term:
    key: str  # canonical operator key
    value: str
    negated: bool
    start: int  # span in the original query
    end: int


@dataclass
class ParsedQuery:
    text: str  # free text for websearch_to_tsquery ("" if none)
    terms: list[Term]
    errors: list[str]


class DateRange:
    """Half-open [start, end) range of ISO date strings."""

    def __init__(self, start: date, end: date):
        self.start = start.isoformat()
        self.end = end.isoformat()


def parse_period(value: str) -> DateRange | None:
    """Parse ``2024``, ``2024-03`` or ``2024-03-15`` (``/`` also accepted)."""
    m = _DATE.match(value)
    if not m:
        return None
    year, month, day = int(m[1]), m[2], m[3]
    try:
        if day:
            start = date(year, int(month), int(day))
            return DateRange(start, start + timedelta(days=1))
        if month:
            start = date(year, int(month), 1)
            end = date(year + (start.month == 12), start.month % 12 + 1, 1)
            return DateRange(start, end)
        return DateRange(date(year, 1, 1), date(year + 1, 1, 1))
    except (ValueError, OverflowError):  # e.g. 2024-02-30, 9999-12-31
        return None


def parse_relative(value: str, today: date | None = None) -> date | None:
    """``30d`` / ``2w`` / ``6m`` / ``1y`` -> the date that long before today."""
    m = _RELATIVE.match(value.lower())
    if not m:
        return None
    n, unit = int(m[1]), m[2]
    days = {"d": 1, "w": 7, "m": 30, "y": 365}[unit] * n
    try:
        return (today or date.today()) - timedelta(days=days)
    except OverflowError:
        return None


def normalize_type(value: str) -> str:
    """``Bank Statement`` / ``bank-statement`` -> ``bank_statement``."""
    return re.sub(r"[\s-]+", "_", value.strip().lower())


def _validate(key: str, value: str) -> str | None:
    """Return an error message if the operator value is unusable."""
    if key == "is" and value.lower() not in IS_VALUES:
        return f"is:{value} isn't supported (try {', '.join(sorted(IS_VALUES))})"
    if key == "has" and value.lower() not in HAS_VALUES:
        return f"has:{value} isn't supported (try {', '.join(sorted(HAS_VALUES))})"
    if key in ("after", "before", "date") and not parse_period(value):
        return f"{key}:{value} isn't a date (use 2024, 2024-03 or 2024-03-15)"
    if key in ("newer_than", "older_than") and not parse_relative(value):
        return f"{key}:{value} isn't a duration (use 30d, 2w, 6m or 1y)"
    return None


def parse_query(q: str) -> ParsedQuery:
    text_parts: list[str] = []
    terms: list[Term] = []
    errors: list[str] = []

    for m in _TOKEN.finditer(q):
        key = m["key"]
        canonical = OPERATORS.get(key.lower()) if key else None
        if canonical:
            value = (m["qval"] if m["qval"] is not None else m["val"] or "").strip()
            if not value:
                continue  # "tag:" with nothing after it yet — still being typed
            error = _validate(canonical, value)
            if error:
                if error not in errors:
                    errors.append(error)
                continue
            terms.append(Term(canonical, value, bool(m["neg"]), m.start(), m.end()))
        else:
            # Free text — including unknown "foo:bar" tokens, kept verbatim
            text_parts.append(m[0])

    return ParsedQuery(" ".join(text_parts).strip(), terms, errors)
