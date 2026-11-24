from decimal import Decimal

import pytest

from precatorios.normalization import (
    entity_match_key,
    normalize_process_number,
    parse_money,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (
            "0012345-10.2019.8.26.0053",
            "0012345-10.2019.8.26.0053",
        ),
        (
            "00234562120208260053",
            "0023456-21.2020.8.26.0053",
        ),
        (
            " 0023456-21.2020.8.26.0053 ",
            "0023456-21.2020.8.26.0053",
        ),
    ],
)
def test_normalize_process_number_accepts_formatted_and_unformatted_values(
    raw_value: str,
    expected: str,
) -> None:
    assert normalize_process_number(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    ["", "123", "0023456-XX.2020.8.26.0053", None],
)
def test_normalize_process_number_rejects_missing_or_malformed_values(
    raw_value: str | None,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_process_number(raw_value)


def test_entity_match_key_ignores_only_cosmetic_differences() -> None:
    assert entity_match_key("  MUNICÍPIO   DE SÃO PAULO ") == "municipio de sao paulo"
    assert entity_match_key("Município de São Paulo") == "municipio de sao paulo"
    assert entity_match_key("União") != entity_match_key("Município de Santos")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2.500,50", Decimal("2500.50")),
        ("45000.00", Decimal("45000.00")),
        (Decimal("12500.00"), Decimal("12500.00")),
        (8000, Decimal("8000")),
    ],
)
def test_parse_money_uses_decimal_without_losing_precision(
    raw_value: str | Decimal | int,
    expected: Decimal,
) -> None:
    assert parse_money(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [None, "", True, 15000.0, Decimal("NaN"), Decimal("Infinity")],
)
def test_parse_money_rejects_ambiguous_or_unsafe_values(raw_value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        parse_money(raw_value)
