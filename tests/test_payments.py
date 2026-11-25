from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from precatorios.models import PaymentEvent
from precatorios.payments import event_effect, select_current_events


def make_event(
    *,
    event_id: str = "ev-001",
    amount: str = "15000.00",
    updated_at: str = "2025-03-10T13:00:00+00:00",
    source_record: int = 1,
) -> PaymentEvent:
    return PaymentEvent(
        event_id=event_id,
        process_number="0012345-10.2019.8.26.0053",
        amount=Decimal(amount),
        paid_on=date(2025, 3, 10),
        event_type="pagamento",
        updated_at=datetime.fromisoformat(updated_at),
        source_record=source_record,
    )


def test_select_current_events_ignores_an_exact_repeated_event() -> None:
    first = make_event(source_record=1)
    repeated = make_event(source_record=4)

    result = select_current_events([first, repeated])

    assert result.current == (first,)
    assert [occurrence.code for occurrence in result.occurrences] == [
        "duplicate_event_ignored"
    ]
    assert result.occurrences[0].source_record == 4


def test_select_current_events_keeps_only_the_latest_event_version() -> None:
    old = make_event(amount="15000.00", source_record=1)
    corrected = make_event(
        amount="15500.00",
        updated_at="2025-03-11T12:00:00+00:00",
        source_record=9,
    )

    result = select_current_events([old, corrected])

    assert result.current == (corrected,)
    assert [occurrence.code for occurrence in result.occurrences] == [
        "event_version_superseded"
    ]
    assert result.occurrences[0].source_record == 1


def test_latest_event_version_does_not_depend_on_input_order() -> None:
    old = make_event(amount="15000.00", source_record=1)
    corrected = make_event(
        amount="15500.00",
        updated_at="2025-03-11T12:00:00+00:00",
        source_record=9,
    )

    result = select_current_events([corrected, old])

    assert result.current == (corrected,)
    assert result.occurrences[0].source_record == 1


def test_conflicting_versions_with_same_update_time_are_not_guessed() -> None:
    first = make_event(amount="15000.00", source_record=1)
    conflicting = make_event(amount="15500.00", source_record=9)

    with pytest.raises(ValueError):
        select_current_events([first, conflicting])


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("pagamento", Decimal("5000.00")),
        ("estorno", Decimal("-5000.00")),
    ],
)
def test_event_effect_applies_the_type_as_the_accounting_sign(
    event_type: str,
    expected: Decimal,
) -> None:
    assert event_effect(event_type, Decimal("5000.00")) == expected


@pytest.mark.parametrize(
    ("event_type", "amount"),
    [
        ("pagamento", Decimal("0")),
        ("pagamento", Decimal("-200")),
        ("ajuste", Decimal("200")),
    ],
)
def test_event_effect_rejects_invalid_type_or_non_positive_amount(
    event_type: str,
    amount: Decimal,
) -> None:
    with pytest.raises(ValueError):
        event_effect(event_type, amount)
