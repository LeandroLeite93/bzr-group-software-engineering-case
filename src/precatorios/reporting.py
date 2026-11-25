"""Escrita determinística da base limpa e dos relatórios de auditoria."""

import csv
import json
from pathlib import Path
from typing import Iterable

from precatorios.models import PipelineResult
from precatorios.payments import event_effect


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_pipeline_outputs(result: PipelineResult, output_dir: Path) -> None:
    """Grava todos os artefatos de uma execução bem-sucedida."""

    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        output_dir / "precatorios.csv",
        [
            "numero_processo",
            "ente_devedor",
            "valor_face",
            "apresentado_em",
            "prazo_pagamento",
            "total_pago",
            "saldo",
            "fonte_cadastro",
            "status_conciliacao",
            "pendencias",
        ],
        (
            {
                "numero_processo": record.process_number,
                "ente_devedor": record.debtor_entity,
                "valor_face": f"{record.face_value:.2f}",
                "apresentado_em": record.presented_on.isoformat(),
                "prazo_pagamento": record.calculated_deadline.isoformat(),
                "total_pago": f"{record.total_paid:.2f}",
                "saldo": f"{record.balance:.2f}",
                "fonte_cadastro": record.registration_source,
                "status_conciliacao": record.reconciliation_status,
                "pendencias": "|".join(record.pending_codes),
            }
            for record in result.precatorios
        ),
    )

    _write_csv(
        output_dir / "pagamentos.csv",
        [
            "evento_id",
            "numero_processo",
            "tipo",
            "valor",
            "efeito_contabil",
            "pago_em",
            "atualizado_em",
            "registro_origem",
        ],
        (
            {
                "evento_id": payment.event_id,
                "numero_processo": payment.process_number,
                "tipo": payment.event_type,
                "valor": f"{payment.amount:.2f}",
                "efeito_contabil": (
                    f"{event_effect(payment.event_type, payment.amount):.2f}"
                ),
                "pago_em": payment.paid_on.isoformat(),
                "atualizado_em": payment.updated_at.isoformat(),
                "registro_origem": payment.source_record,
            }
            for payment in result.payments
        ),
    )

    _write_csv(
        output_dir / "pendencias.csv",
        ["codigo", "arquivo", "registro", "referencia", "motivo"],
        (
            {
                "codigo": item.code,
                "arquivo": item.source_file,
                "registro": item.source_record,
                "referencia": item.reference,
                "motivo": item.reason,
            }
            for item in result.pending
        ),
    )

    _write_csv(
        output_dir / "ocorrencias.csv",
        [
            "codigo",
            "acao",
            "arquivo",
            "registro",
            "referencia",
            "detalhe",
        ],
        (
            {
                "codigo": item.code,
                "acao": item.action,
                "arquivo": item.source_file,
                "registro": (
                    item.source_record if item.source_record is not None else ""
                ),
                "referencia": item.reference,
                "detalhe": item.detail,
            }
            for item in result.occurrences
        ),
    )

    (output_dir / "resumo.json").write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
