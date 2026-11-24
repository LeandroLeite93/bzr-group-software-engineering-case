"""Contratos para leitura dos arquivos sem alterar os insumos."""

from pathlib import Path

from precatorios.models import TribunalRecord


def read_json_records(path: Path) -> list[dict[str, object]]:
    """Lê uma lista JSON preservando números decimais com exatidão."""

    raise NotImplementedError


def read_tribunal(path: Path) -> list[TribunalRecord]:
    """Lê o CSV real do tribunal e registra sua linha de origem."""

    raise NotImplementedError
