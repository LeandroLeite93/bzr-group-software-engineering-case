"""Datas de apresentação e prazos constitucionais."""

from datetime import date, datetime, tzinfo


def business_date(presented_at: datetime, *, timezone: tzinfo) -> date:
    """Converte um instante na data civil do fuso usado pela operação."""

    if not isinstance(presented_at, datetime):
        raise TypeError("a apresentação deve ser uma data e hora")
    if presented_at.tzinfo is None or presented_at.utcoffset() is None:
        raise ValueError("a data e hora de apresentação deve informar o fuso")
    if not isinstance(timezone, tzinfo):
        raise TypeError("o fuso de negócio deve implementar tzinfo")
    return presented_at.astimezone(timezone).date()


def calculate_payment_deadline(presented_on: date) -> date:
    """Calcula o dia 31 de dezembro aplicando o corte de 2 de abril."""

    if isinstance(presented_on, datetime) or not isinstance(presented_on, date):
        raise TypeError("o prazo deve ser calculado a partir de uma data civil")

    cutoff = date(presented_on.year, 4, 2)
    years_until_deadline = 1 if presented_on <= cutoff else 2
    return date(presented_on.year + years_until_deadline, 12, 31)
