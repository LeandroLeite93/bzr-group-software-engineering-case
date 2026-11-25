"""Orquestração da limpeza, conciliação e geração dos resultados."""

from collections import Counter, defaultdict
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from precatorios.models import (
    AuditEntry,
    PaymentEvent,
    PendingItem,
    PipelineResult,
)
from precatorios.payments import event_effect, select_current_events
from precatorios.readers import (
    read_hub,
    read_json_records,
    read_presentations,
    read_tribunal,
)
from precatorios.reconciliation import reconcile_precatorios
from precatorios.reporting import write_pipeline_outputs
from precatorios.validation import validate_payment_records


def _select_payment_versions(
    events: tuple[PaymentEvent, ...],
) -> tuple[list[PaymentEvent], list[PendingItem], list[AuditEntry]]:
    grouped: dict[str, list[PaymentEvent]] = defaultdict(list)
    for event in events:
        grouped[event.event_id].append(event)

    current: list[PaymentEvent] = []
    pending: list[PendingItem] = []
    audit: list[AuditEntry] = []
    for event_id, versions in grouped.items():
        try:
            selection = select_current_events(versions)
        except ValueError as error:
            pending.append(
                PendingItem(
                    code="ambiguous_event_versions",
                    source_file="pagamentos.json",
                    source_record="|".join(
                        str(version.source_record) for version in versions
                    ),
                    reference=event_id,
                    reason=str(error),
                )
            )
            audit.append(
                AuditEntry(
                    code="ambiguous_event_versions",
                    action="rejeitado",
                    source_file="pagamentos.json",
                    source_record=None,
                    reference=event_id,
                    detail=str(error),
                )
            )
            continue

        current.extend(selection.current)
        for occurrence in selection.occurrences:
            if occurrence.code == "duplicate_event_ignored":
                action = "descartado"
                detail = "repetição exata do mesmo evento"
            else:
                action = "substituído"
                detail = "versão anterior substituída por atualizado_em mais recente"
            audit.append(
                AuditEntry(
                    code=occurrence.code,
                    action=action,
                    source_file="pagamentos.json",
                    source_record=occurrence.source_record,
                    reference=occurrence.event_id,
                    detail=detail,
                )
            )
    return current, pending, audit


def run_pipeline(raw_dir: Path, output_dir: Path) -> PipelineResult:
    """Executa uma limpeza completa mantendo cada decisão auditável."""

    data_dir = raw_dir / "dados"
    tribunal_records = read_tribunal(data_dir / "tribunal.csv")
    hub_records = read_hub(data_dir / "hub.csv")
    presentation_records = read_presentations(data_dir / "apresentacoes.json")
    raw_payments = read_json_records(data_dir / "pagamentos.json")

    reconciliation = reconcile_precatorios(
        tribunal_records,
        hub_records,
        presentation_records,
    )
    payment_validation = validate_payment_records(raw_payments)
    selected, version_pending, version_audit = _select_payment_versions(
        payment_validation.valid
    )

    known_processes = {record.process_number for record in reconciliation.records}
    accepted_payments: list[PaymentEvent] = []
    reference_pending: list[PendingItem] = []
    reference_audit: list[AuditEntry] = []
    for payment in selected:
        if payment.process_number in known_processes:
            accepted_payments.append(payment)
            continue
        reference_pending.append(
            PendingItem(
                code="payment_process_not_found",
                source_file="pagamentos.json",
                source_record=str(payment.source_record),
                reference=payment.event_id,
                reason=f"processo não encontrado: {payment.process_number}",
            )
        )
        reference_audit.append(
            AuditEntry(
                code="payment_process_not_found",
                action="rejeitado",
                source_file="pagamentos.json",
                source_record=payment.source_record,
                reference=payment.event_id,
                detail=f"processo não encontrado: {payment.process_number}",
            )
        )

    totals_by_process: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for payment in accepted_payments:
        totals_by_process[payment.process_number] += event_effect(
            payment.event_type,
            payment.amount,
        )

    enriched_precatorios = tuple(
        replace(
            record,
            total_paid=totals_by_process[record.process_number],
            balance=record.face_value - totals_by_process[record.process_number],
        )
        for record in reconciliation.records
    )

    pending = (
        reconciliation.pending
        + payment_validation.pending
        + tuple(version_pending)
        + tuple(reference_pending)
    )
    layout_audit = AuditEntry(
        code="tribunal_layout_differs_from_documentation",
        action="adaptado",
        source_file="tribunal.csv",
        source_record=None,
        reference="tribunal.csv",
        detail="lido como ISO-8859-1, separado por ';' e decimal brasileiro",
    )
    occurrences = (
        (layout_audit,)
        + reconciliation.occurrences
        + payment_validation.occurrences
        + tuple(version_audit)
        + tuple(reference_audit)
    )

    pending_by_code = Counter(item.code for item in pending)
    occurrence_by_code = Counter(item.code for item in occurrences)
    total_face_value = sum(
        (item.face_value for item in enriched_precatorios),
        Decimal("0"),
    )
    total_paid_value = sum(totals_by_process.values(), Decimal("0"))
    summary: dict[str, object] = {
        "entradas": {
            "precatorios_tribunal": len(tribunal_records),
            "precatorios_hub": len(hub_records),
            "apresentacoes": len(presentation_records),
            "eventos_pagamento": len(raw_payments),
        },
        "saidas": {
            "precatorios": len(enriched_precatorios),
            "eventos_pagamento_aceitos": len(accepted_payments),
            "pendencias": len(pending),
            "ocorrencias": len(occurrences),
        },
        "pendencias_por_codigo": dict(sorted(pending_by_code.items())),
        "ocorrencias_por_codigo": dict(sorted(occurrence_by_code.items())),
        "totais": {
            "valor_face": f"{total_face_value:.2f}",
            "valor_pago_liquido": f"{total_paid_value:.2f}",
        },
    }
    result = PipelineResult(
        precatorios=enriched_precatorios,
        payments=tuple(accepted_payments),
        pending=pending,
        occurrences=occurrences,
        summary=summary,
    )
    write_pipeline_outputs(result, output_dir)
    return result
