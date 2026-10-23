"""Gmail-style search query parser."""

from datetime import date

from app.core.search_query import (
    normalize_type,
    parse_period,
    parse_query,
    parse_relative,
)


def keys(parsed):
    return [(t.key, t.value, t.negated) for t in parsed.terms]


def test_free_text_only():
    parsed = parse_query('water "city newsletter" -spam')
    assert parsed.text == 'water "city newsletter" -spam'
    assert parsed.terms == []


def test_operators_and_aliases():
    parsed = parse_query(
        "title:utah ocr:ford tag:bill name:x text:y from:acme year:2024"
    )
    assert keys(parsed) == [
        ("title", "utah", False),
        ("ocr", "ford", False),
        ("tag", "bill", False),
        ("title", "x", False),
        ("ocr", "y", False),
        ("company", "acme", False),
        ("date", "2024", False),
    ]
    assert parsed.text == ""


def test_operator_keys_are_case_insensitive():
    assert keys(parse_query("TAG:Bill")) == [("tag", "Bill", False)]


def test_negation_and_quoted_values():
    parsed = parse_query('electric -tag:paid title:"city newsletter" -"junk mail"')
    assert keys(parsed) == [("tag", "paid", True), ("title", "city newsletter", False)]
    assert parsed.text == 'electric -"junk mail"'


def test_unclosed_quote_takes_rest_of_query():
    assert keys(parse_query('title:"fountain green')) == [
        ("title", "fountain green", False)
    ]


def test_spans_point_at_original_text():
    q = 'rent -tag:paid title:"a b"'
    for term in parse_query(q).terms:
        raw = q[term.start : term.end]
        assert raw in ("-tag:paid", 'title:"a b"')


def test_unknown_operator_is_free_text():
    parsed = parse_query("https://example.com foo:bar")
    assert parsed.terms == []
    assert parsed.text == "https://example.com foo:bar"


def test_invalid_values_reported_not_applied():
    parsed = parse_query("is:shiny after:soon newer_than:abc has:wings")
    assert parsed.terms == []
    assert len(parsed.errors) == 4


def test_empty_operator_value_ignored_while_typing():
    parsed = parse_query('rent tag: title:""')
    assert parsed.terms == [] and parsed.errors == []
    assert parsed.text == "rent"


def test_parse_period():
    assert vars(parse_period("2024")) == {"start": "2024-01-01", "end": "2025-01-01"}
    assert vars(parse_period("2024-12")) == {"start": "2024-12-01", "end": "2025-01-01"}
    assert vars(parse_period("2024/3/5")) == {
        "start": "2024-03-05",
        "end": "2024-03-06",
    }
    assert parse_period("2024-13") is None
    assert parse_period("2024-02-30") is None
    assert parse_period("last week") is None


def test_parse_relative():
    today = date(2026, 10, 23)
    assert parse_relative("7d", today) == date(2026, 10, 16)
    assert parse_relative("2w", today) == date(2026, 10, 9)
    assert parse_relative("1Y", today) == date(2025, 10, 23)
    assert parse_relative("99999999y", today) is None
    assert parse_relative("soon", today) is None


def test_normalize_type():
    assert normalize_type("Bank Statement") == "bank_statement"
    assert normalize_type("bank-statement") == "bank_statement"


def test_boundary_and_oversized_values_are_errors_not_crashes():
    parsed = parse_query("date:9999-12-31 newer_than:" + "9" * 5000 + "d")
    assert parsed.terms == []
    assert len(parsed.errors) == 2


def test_duplicate_errors_reported_once():
    assert len(parse_query("is:shiny is:shiny").errors) == 1
