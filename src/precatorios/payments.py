"""Consolidação e contabilização de eventos de pagamento."""

from decimal import Decimal
from typing import Iterable

from precatorios.models import (
    EventSelectionResult,
    Occurrence,
    PaymentEvent,
)


def _same_version(left: PaymentEvent, right: PaymentEvent) -> bool:
    return (
        left.event_id == right.event_id
        and left.process_number == right.process_number
        and left.amount == right.amount
        and left.paid_on == right.paid_on
        and left.event_type == right.event_type
        and left.updated_at == right.updated_at
    )


def _validate_event_identity(event: PaymentEvent) -> None:
    if not event.event_id.strip():
        raise ValueError("o identificador do evento não pode ser vazio")
    if event.updated_at.tzinfo is None or event.updated_at.utcoffset() is None:
        raise ValueError("a atualização do evento deve informar o fuso")


def select_current_events(events: Iterable[PaymentEvent]) -> EventSelectionResult:
    """Seleciona uma versão vigente por evento sem duplicar pagamentos."""

    current_by_id: dict[str, PaymentEvent] = {}
    occurrences: list[Occurrence] = []

    for event in events:
        _validate_event_identity(event)
        current = current_by_id.get(event.event_id)
        if current is None:
            current_by_id[event.event_id] = event
            continue

        if _same_version(current, event):
            occurrences.append(
                Occurrence(
                    code="duplicate_event_ignored",
                    event_id=event.event_id,
                    source_record=event.source_record,
                )
            )
            continue

        if event.updated_at == current.updated_at:
            raise ValueError(
                f"o evento {event.event_id} tem versões conflitantes "
                "com o mesmo horário de atualização"
            )

        if event.updated_at > current.updated_at:
            superseded = current
            current_by_id[event.event_id] = event
        else:
            superseded = event

        occurrences.append(
            Occurrence(
                code="event_version_superseded",
                event_id=event.event_id,
                source_record=superseded.source_record,
            )
        )

    return EventSelectionResult(
        current=tuple(current_by_id.values()),
        occurrences=tuple(occurrences),
    )


def event_effect(event_type: str, amount: Decimal) -> Decimal:
    """Retorna o efeito contábil de um pagamento ou estorno."""

    if not isinstance(amount, Decimal):
        raise TypeError("o valor do evento deve ser Decimal")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("o valor do evento deve ser positivo e finito")
    if event_type == "pagamento":
        return amount
    if event_type == "estorno":
        return -amount
    raise ValueError(f"tipo de evento desconhecido: {event_type}")
