from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from precatorios.deadlines import business_date, calculate_payment_deadline


@pytest.mark.parametrize(
    ("presented_on", "expected"),
    [
        (date(2025, 4, 2), date(2026, 12, 31)),
        (date(2025, 4, 3), date(2027, 12, 31)),
        (date(2024, 2, 29), date(2025, 12, 31)),
        (date(2023, 12, 31), date(2025, 12, 31)),
    ],
)
def test_calculate_payment_deadline_respects_april_second_cutoff(
    presented_on: date,
    expected: date,
) -> None:
    assert calculate_payment_deadline(presented_on) == expected


@pytest.mark.parametrize(
    ("presented_at", "expected"),
    [
        (
            datetime(
                2025,
                4,
                2,
                23,
                30,
                tzinfo=timezone(timedelta(hours=-3)),
            ),
            date(2025, 4, 2),
        ),
        (
            datetime(2025, 4, 3, 1, tzinfo=timezone.utc),
            date(2025, 4, 2),
        ),
    ],
)
def test_business_date_converts_instants_to_sao_paulo_calendar_date(
    presented_at: datetime,
    expected: date,
) -> None:
    assert business_date(
        presented_at,
        timezone=ZoneInfo("America/Sao_Paulo"),
    ) == expected


def test_business_date_rejects_datetime_without_timezone() -> None:
    with pytest.raises(ValueError):
        business_date(
            datetime(2025, 4, 2, 23, 30),
            timezone=ZoneInfo("America/Sao_Paulo"),
        )


def test_deadline_rejects_datetime_to_avoid_silent_timezone_loss() -> None:
    with pytest.raises(TypeError):
        calculate_payment_deadline(
            datetime(2025, 4, 2, 23, 30, tzinfo=timezone.utc)
        )
