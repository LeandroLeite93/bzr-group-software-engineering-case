"""Conciliação do cadastro do tribunal com a exportação do Hub."""

from decimal import Decimal
from typing import Iterable

from precatorios.deadlines import calculate_payment_deadline
from precatorios.models import (
    AuditEntry,
    CleanPrecatorio,
    HubRecord,
    PendingItem,
    PresentationRecord,
    ReconciliationResult,
    TribunalRecord,
)
from precatorios.normalization import entity_match_key, normalize_process_number
from precatorios.validation import parse_presentation_date


def _add_unique(
    destination: dict[str, object],
    process_number: str,
    record: object,
    source_name: str,
) -> None:
    if process_number in destination:
        raise ValueError(f"processo duplicado em {source_name}: {process_number}")
    destination[process_number] = record


def reconcile_precatorios(
    tribunal_records: Iterable[TribunalRecord],
    hub_records: Iterable[HubRecord],
    presentation_records: Iterable[PresentationRecord],
) -> ReconciliationResult:
    """Produz uma visão canônica sem esconder divergências entre fontes."""

    tribunal_by_process: dict[str, TribunalRecord] = {}
    hub_by_process: dict[str, HubRecord] = {}
    presentations_by_process: dict[str, PresentationRecord] = {}
    occurrences: list[AuditEntry] = []
    pending: list[PendingItem] = []

    for record in tribunal_records:
        process_number = normalize_process_number(record.process_number)
        _add_unique(
            tribunal_by_process,
            process_number,
            record,
            "tribunal.csv",
        )

    for record in hub_records:
        process_number = normalize_process_number(record.process_number)
        _add_unique(hub_by_process, process_number, record, "hub.csv")
        if record.process_number != process_number:
            occurrences.append(
                AuditEntry(
                    code="process_number_normalized",
                    action="corrigido",
                    source_file="hub.csv",
                    source_record=record.source_line,
                    reference=process_number,
                    detail=f"{record.process_number!r} -> {process_number}",
                )
            )

    for record in presentation_records:
        process_number = normalize_process_number(record.process_number)
        _add_unique(
            presentations_by_process,
            process_number,
            record,
            "apresentacoes.json",
        )

    all_processes = sorted(
        tribunal_by_process.keys()
        | hub_by_process.keys()
        | presentations_by_process.keys()
    )
    clean_records: list[CleanPrecatorio] = []

    for process_number in all_processes:
        tribunal = tribunal_by_process.get(process_number)
        hub = hub_by_process.get(process_number)
        presentation = presentations_by_process.get(process_number)
        pending_codes: list[str] = []

        if tribunal is None:
            pending_codes.append("missing_in_tribunal")
            pending.append(
                PendingItem(
                    code="missing_in_tribunal",
                    source_file="tribunal.csv",
                    source_record="-",
                    reference=process_number,
                    reason="processo presente no Hub, mas ausente na lista do tribunal",
                )
            )
        if hub is None:
            pending_codes.append("missing_in_hub")
            pending.append(
                PendingItem(
                    code="missing_in_hub",
                    source_file="hub.csv",
                    source_record="-",
                    reference=process_number,
                    reason="processo presente no tribunal, mas ausente no Hub",
                )
            )

        if tribunal is not None and hub is not None:
            tribunal_entity_key = entity_match_key(tribunal.debtor_entity)
            hub_entity_key = entity_match_key(hub.debtor_entity)
            source_records = f"tribunal:{tribunal.source_line};hub:{hub.source_line}"

            if tribunal_entity_key != hub_entity_key:
                pending_codes.append("debtor_entity_conflict")
                pending.append(
                    PendingItem(
                        code="debtor_entity_conflict",
                        source_file="tribunal.csv|hub.csv",
                        source_record=source_records,
                        reference=process_number,
                        reason=(
                            f"tribunal={tribunal.debtor_entity!r}; "
                            f"hub={hub.debtor_entity!r}"
                        ),
                    )
                )
            elif tribunal.debtor_entity != hub.debtor_entity:
                occurrences.append(
                    AuditEntry(
                        code="entity_name_matched_by_normalization",
                        action="conciliado",
                        source_file="tribunal.csv|hub.csv",
                        source_record=hub.source_line,
                        reference=process_number,
                        detail=(
                            f"{hub.debtor_entity!r} corresponde a "
                            f"{tribunal.debtor_entity!r}"
                        ),
                    )
                )

            if tribunal.face_value != hub.face_value:
                pending_codes.append("face_value_conflict")
                pending.append(
                    PendingItem(
                        code="face_value_conflict",
                        source_file="tribunal.csv|hub.csv",
                        source_record=source_records,
                        reference=process_number,
                        reason=(
                            f"tribunal={tribunal.face_value:.2f}; "
                            f"hub={hub.face_value:.2f}"
                        ),
                    )
                )

        if presentation is not None:
            presented_on = parse_presentation_date(presentation.presented_at)
            if "T" in presentation.presented_at:
                occurrences.append(
                    AuditEntry(
                        code="presentation_datetime_to_business_date",
                        action="normalizado",
                        source_file="apresentacoes.json",
                        source_record=presentation.source_record,
                        reference=process_number,
                        detail=(
                            f"{presentation.presented_at!r} -> "
                            f"{presented_on.isoformat()}"
                        ),
                    )
                )
        elif hub is not None:
            presented_on = parse_presentation_date(hub.presented_at)
            pending_codes.append("missing_presentation_record")
            pending.append(
                PendingItem(
                    code="missing_presentation_record",
                    source_file="apresentacoes.json",
                    source_record="-",
                    reference=process_number,
                    reason="data obtida apenas da exportação do Hub",
                )
            )
        else:
            pending.append(
                PendingItem(
                    code="missing_presentation_date",
                    source_file="apresentacoes.json|hub.csv",
                    source_record="-",
                    reference=process_number,
                    reason="não há data disponível para calcular o prazo",
                )
            )
            continue

        calculated_deadline = calculate_payment_deadline(presented_on)
        if hub is not None and hub.reported_deadline != calculated_deadline:
            pending_codes.append("deadline_conflict")
            pending.append(
                PendingItem(
                    code="deadline_conflict",
                    source_file="hub.csv",
                    source_record=str(hub.source_line),
                    reference=process_number,
                    reason=(
                        f"hub={hub.reported_deadline.isoformat()}; "
                        f"calculado={calculated_deadline.isoformat()}"
                    ),
                )
            )
            occurrences.append(
                AuditEntry(
                    code="deadline_recalculated",
                    action="corrigido",
                    source_file="hub.csv",
                    source_record=hub.source_line,
                    reference=process_number,
                    detail=(
                        f"{hub.reported_deadline.isoformat()} -> "
                        f"{calculated_deadline.isoformat()}"
                    ),
                )
            )

        registration = tribunal if tribunal is not None else hub
        if registration is None:
            continue
        registration_source = "tribunal" if tribunal is not None else "hub"
        clean_records.append(
            CleanPrecatorio(
                process_number=process_number,
                debtor_entity=registration.debtor_entity,
                face_value=registration.face_value,
                presented_on=presented_on,
                calculated_deadline=calculated_deadline,
                total_paid=Decimal("0.00"),
                balance=registration.face_value,
                registration_source=registration_source,
                reconciliation_status=(
                    "conciliado" if not pending_codes else "pendente"
                ),
                pending_codes=tuple(pending_codes),
            )
        )

    return ReconciliationResult(
        records=tuple(clean_records),
        pending=tuple(pending),
        occurrences=tuple(occurrences),
    )
