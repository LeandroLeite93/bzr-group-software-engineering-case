"""Leitura dos arquivos sem alterar os insumos."""

import csv
from decimal import Decimal
import io
import json
from pathlib import Path

from precatorios.models import TribunalRecord
from precatorios.normalization import parse_money


_TRIBUNAL_FIELDS = {"numero_processo", "ente_devedor", "valor_face"}


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
