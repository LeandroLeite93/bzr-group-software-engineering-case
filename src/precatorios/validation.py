"""Validação dos registros antes da conciliação."""

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from precatorios.deadlines import business_date
from precatorios.models import (
    AuditEntry,
    PaymentEvent,
    PaymentValidationResult,
    PendingItem,
)
from precatorios.normalization import normalize_process_number, parse_money
from precatorios.payments import event_effect


BUSINESS_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def parse_presentation_date(raw_value: str) -> date:
    """Interpreta data ou instante no calendário operacional de São Paulo."""

    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("a data de apresentação deve ser informada")

    value = raw_value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    try:
        presented_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("data de apresentação inválida") from error
    return business_date(presented_at, timezone=BUSINESS_TIMEZONE)


def _parse_payment_date(raw_value: object) -> tuple[date, bool]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("a data de pagamento deve ser informada")

    value = raw_value.strip()
    try:
        return date.fromisoformat(value), False
    except ValueError:
        try:
            return datetime.strptime(value, "%d/%m/%Y").date(), True
        except ValueError as error:
            raise ValueError("data de pagamento inválida") from error


def _parse_updated_at(raw_value: object) -> datetime:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("o horário de atualização deve ser informado")
    try:
        updated_at = datetime.fromisoformat(
            raw_value.strip().replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ValueError("horário de atualização inválido") from error
    if updated_at.tzinfo is None or updated_at.utcoffset() is None:
        raise ValueError("o horário de atualização deve informar o fuso")
    return updated_at


def _required_event_id(raw_value: object) -> str:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("o identificador do evento deve ser informado")
    return raw_value.strip()


def validate_payment_records(
    raw_records: Iterable[dict[str, object]],
) -> PaymentValidationResult:
    """Valida eventos isoladamente e mantém os inválidos em quarentena."""

    valid: list[PaymentEvent] = []
    pending: list[PendingItem] = []
    occurrences: list[AuditEntry] = []

    for source_record, raw_record in enumerate(raw_records, start=1):
        raw_event_id = raw_record.get("evento_id")
        reference = (
            raw_event_id.strip()
            if isinstance(raw_event_id, str) and raw_event_id.strip()
            else f"registro-{source_record}"
        )
        try:
            event_id = _required_event_id(raw_event_id)
            raw_process = raw_record.get("processo")
            process_number = normalize_process_number(raw_process)
            amount = parse_money(raw_record.get("valor"))
            event_type = raw_record.get("tipo")
            if not isinstance(event_type, str):
                raise ValueError("o tipo do evento deve ser texto")
            event_effect(event_type, amount)
            paid_on, date_was_corrected = _parse_payment_date(
                raw_record.get("data_pagamento")
            )
            updated_at = _parse_updated_at(raw_record.get("atualizado_em"))

            valid.append(
                PaymentEvent(
                    event_id=event_id,
                    process_number=process_number,
                    amount=amount,
                    paid_on=paid_on,
                    event_type=event_type,
                    updated_at=updated_at,
                    source_record=source_record,
                )
            )

            if isinstance(raw_process, str) and raw_process.strip() != process_number:
                occurrences.append(
                    AuditEntry(
                        code="process_number_normalized",
                        action="corrigido",
                        source_file="pagamentos.json",
                        source_record=source_record,
                        reference=event_id,
                        detail=f"{raw_process!r} -> {process_number}",
                    )
                )
            if isinstance(raw_record.get("valor"), str):
                occurrences.append(
                    AuditEntry(
                        code="money_format_normalized",
                        action="corrigido",
                        source_file="pagamentos.json",
                        source_record=source_record,
                        reference=event_id,
                        detail=f"{raw_record['valor']!r} -> {amount:.2f}",
                    )
                )
            if date_was_corrected:
                occurrences.append(
                    AuditEntry(
                        code="payment_date_normalized",
                        action="corrigido",
                        source_file="pagamentos.json",
                        source_record=source_record,
                        reference=event_id,
                        detail=(
                            f"{raw_record['data_pagamento']!r} -> "
                            f"{paid_on.isoformat()}"
                        ),
                    )
                )
        except (TypeError, ValueError) as error:
            pending.append(
                PendingItem(
                    code="invalid_payment_event",
                    source_file="pagamentos.json",
                    source_record=str(source_record),
                    reference=reference,
                    reason=str(error),
                )
            )
            occurrences.append(
                AuditEntry(
                    code="payment_event_rejected",
                    action="rejeitado",
                    source_file="pagamentos.json",
                    source_record=source_record,
                    reference=reference,
                    detail=str(error),
                )
            )

    return PaymentValidationResult(
        valid=tuple(valid),
        pending=tuple(pending),
        occurrences=tuple(occurrences),
    )
