"""Leitura dos arquivos sem alterar os insumos."""

import csv
from datetime import date
from decimal import Decimal
import io
import json
from pathlib import Path

from precatorios.models import HubRecord, PresentationRecord, TribunalRecord
from precatorios.normalization import parse_money


_TRIBUNAL_FIELDS = {"numero_processo", "ente_devedor", "valor_face"}
_HUB_FIELDS = {
    "processo",
    "ente",
    "valor_face",
    "apresentado_em",
    "prazo_pagamento",
}


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"constante JSON inválida: {value}")


def read_json_records(path: Path) -> list[dict[str, object]]:
    """Lê uma lista JSON preservando números decimais com exatidão."""

    content = path.read_text(encoding="utf-8")
    data = json.loads(
        content,
        parse_float=Decimal,
        parse_int=Decimal,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(data, list):
        raise ValueError("a raiz do arquivo JSON deve ser uma lista")
    if not all(isinstance(record, dict) for record in data):
        raise ValueError("cada item do arquivo JSON deve ser um objeto")
    return data


def read_tribunal(path: Path) -> list[TribunalRecord]:
    """Lê o CSV real do tribunal e registra sua linha de origem."""

    raw_content = path.read_bytes()
    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        content = raw_content.decode("iso-8859-1")

    reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=";")
    if reader.fieldnames is None or set(reader.fieldnames) != _TRIBUNAL_FIELDS:
        raise ValueError("cabeçalho inesperado no CSV do tribunal")

    records: list[TribunalRecord] = []
    for row in reader:
        process_number = row["numero_processo"]
        debtor_entity = row["ente_devedor"]
        face_value = row["valor_face"]
        if process_number is None or debtor_entity is None or face_value is None:
            raise ValueError(f"linha {reader.line_num} incompleta no CSV do tribunal")

        records.append(
            TribunalRecord(
                process_number=process_number.strip(),
                debtor_entity=debtor_entity.strip(),
                face_value=parse_money(face_value),
                source_line=reader.line_num,
            )
        )
    return records


def read_hub(path: Path) -> list[HubRecord]:
    """Lê a exportação UTF-8 do Hub."""

    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or set(reader.fieldnames) != _HUB_FIELDS:
            raise ValueError("cabeçalho inesperado no CSV do Hub")

        records: list[HubRecord] = []
        for row in reader:
            if any(row[field] is None for field in _HUB_FIELDS):
                raise ValueError(f"linha {reader.line_num} incompleta no CSV do Hub")
            try:
                reported_deadline = date.fromisoformat(row["prazo_pagamento"])
            except ValueError as error:
                raise ValueError(
                    f"prazo inválido na linha {reader.line_num} do CSV do Hub"
                ) from error

            records.append(
                HubRecord(
                    process_number=row["processo"].strip(),
                    debtor_entity=row["ente"].strip(),
                    face_value=parse_money(row["valor_face"]),
                    presented_at=row["apresentado_em"].strip(),
                    reported_deadline=reported_deadline,
                    source_line=reader.line_num,
                )
            )
    return records


def read_presentations(path: Path) -> list[PresentationRecord]:
    """Lê as apresentações preservando a representação recebida."""

    raw_records = read_json_records(path)
    records: list[PresentationRecord] = []
    for source_record, raw_record in enumerate(raw_records, start=1):
        process_number = raw_record.get("processo")
        presented_at = raw_record.get("apresentado_em")
        if not isinstance(process_number, str) or not isinstance(presented_at, str):
            raise ValueError(
                f"registro {source_record} inválido em apresentacoes.json"
            )
        records.append(
            PresentationRecord(
                process_number=process_number,
                presented_at=presented_at,
                source_record=source_record,
            )
        )
    return records
