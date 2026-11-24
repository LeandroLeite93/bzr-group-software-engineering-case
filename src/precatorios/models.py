"""Modelos de domínio compartilhados pelo pipeline."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TribunalRecord:
    """Registro lido da lista enviada pelo tribunal."""

    process_number: str
    debtor_entity: str
    face_value: Decimal
    source_line: int


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    """Versão validada de um evento de pagamento."""

    event_id: str
    process_number: str
    amount: Decimal
    paid_on: date
    event_type: str
    updated_at: datetime
    source_record: int


@dataclass(frozen=True, slots=True)
class Occurrence:
    """Decisão auditável tomada durante a limpeza."""

    code: str
    event_id: str
    source_record: int


@dataclass(frozen=True, slots=True)
class EventSelectionResult:
    """Eventos vigentes e ocorrências produzidas pela deduplicação."""

    current: tuple[PaymentEvent, ...]
    occurrences: tuple[Occurrence, ...]
