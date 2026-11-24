"""Contratos para consolidar e contabilizar eventos de pagamento."""

from decimal import Decimal
from typing import Iterable

from precatorios.models import EventSelectionResult, PaymentEvent


def select_current_events(events: Iterable[PaymentEvent]) -> EventSelectionResult:
    """Seleciona uma versão vigente por evento sem duplicar pagamentos."""

    raise NotImplementedError


def event_effect(event_type: str, amount: Decimal) -> Decimal:
    """Retorna o efeito contábil de um pagamento ou estorno."""

    raise NotImplementedError
