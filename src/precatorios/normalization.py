"""Contratos para normalização de identificadores e valores."""

from decimal import Decimal


def normalize_process_number(raw_value: object) -> str:
    """Retorna um número CNJ na representação pontuada canônica."""

    raise NotImplementedError


def entity_match_key(raw_value: object) -> str:
    """Cria uma chave de comparação sem apagar o valor original."""

    raise NotImplementedError


def parse_money(raw_value: object) -> Decimal:
    """Converte uma representação monetária segura para Decimal."""

    raise NotImplementedError
