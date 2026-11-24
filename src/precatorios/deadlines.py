"""Contratos para datas de apresentação e prazos constitucionais."""

from datetime import date, datetime, tzinfo


def business_date(presented_at: datetime, *, timezone: tzinfo) -> date:
    """Converte um instante na data civil do fuso usado pela operação."""

    raise NotImplementedError


def calculate_payment_deadline(presented_on: date) -> date:
    """Calcula o dia 31 de dezembro aplicando o corte de 2 de abril."""

    raise NotImplementedError
