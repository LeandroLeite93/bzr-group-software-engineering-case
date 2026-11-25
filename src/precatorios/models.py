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
class HubRecord:
    """Registro lido da exportação atual do Hub."""

    process_number: str
    debtor_entity: str
    face_value: Decimal
    presented_at: str
    reported_deadline: date
    source_line: int


@dataclass(frozen=True, slots=True)
class PresentationRecord:
    """Data de apresentação associada a um processo."""

    process_number: str
    presented_at: str
    source_record: int


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


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Correção, descarte ou decisão registrada pelo pipeline."""

    code: str
    action: str
    source_file: str
    source_record: int | None
    reference: str
    detail: str


@dataclass(frozen=True, slots=True)
class PendingItem:
    """Dado que exige confirmação humana antes de uso definitivo."""

    code: str
    source_file: str
    source_record: str
    reference: str
    reason: str


@dataclass(frozen=True, slots=True)
class PaymentValidationResult:
    """Resultado da validação individual dos eventos recebidos."""

    valid: tuple[PaymentEvent, ...]
    pending: tuple[PendingItem, ...]
    occurrences: tuple[AuditEntry, ...]


@dataclass(frozen=True, slots=True)
class CleanPrecatorio:
    """Precatório canônico com rastreabilidade da conciliação."""

    process_number: str
    debtor_entity: str
    face_value: Decimal
    presented_on: date
    calculated_deadline: date
    total_paid: Decimal
    balance: Decimal
    registration_source: str
    reconciliation_status: str
    pending_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Base conciliada e itens que ainda precisam de decisão."""

    records: tuple[CleanPrecatorio, ...]
    pending: tuple[PendingItem, ...]
    occurrences: tuple[AuditEntry, ...]


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Resultado completo disponibilizado pelo pipeline."""

    precatorios: tuple[CleanPrecatorio, ...]
    payments: tuple[PaymentEvent, ...]
    pending: tuple[PendingItem, ...]
    occurrences: tuple[AuditEntry, ...]
    summary: dict[str, object]
