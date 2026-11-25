"""Normalização de identificadores e valores sem alterar a fonte."""

from decimal import Decimal, InvalidOperation
import re
import unicodedata


_FORMATTED_PROCESS = re.compile(
    r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$"
)
_UNFORMATTED_PROCESS = re.compile(r"^\d{20}$")
_BRAZILIAN_MONEY = re.compile(
    r"^[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{1,2}$"
)
_DECIMAL_MONEY = re.compile(r"^[+-]?\d+(?:\.\d{1,2})?$")


def normalize_process_number(raw_value: object) -> str:
    """Retorna um número CNJ na representação pontuada canônica."""

    if not isinstance(raw_value, str):
        raise TypeError("o número do processo deve ser texto")

    value = raw_value.strip()
    formatted_match = _FORMATTED_PROCESS.fullmatch(value)
    if formatted_match:
        return value

    if not _UNFORMATTED_PROCESS.fullmatch(value):
        raise ValueError("o número do processo não segue o formato CNJ")

    return (
        f"{value[:7]}-{value[7:9]}.{value[9:13]}."
        f"{value[13]}.{value[14:16]}.{value[16:]}"
    )


def entity_match_key(raw_value: object) -> str:
    """Cria uma chave de comparação sem apagar o valor original."""

    if not isinstance(raw_value, str):
        raise TypeError("o ente devedor deve ser texto")

    normalized = unicodedata.normalize("NFKD", raw_value)
    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    key = " ".join(without_accents.casefold().split())
    if not key:
        raise ValueError("o ente devedor não pode ser vazio")
    return key


def parse_money(raw_value: object) -> Decimal:
    """Converte uma representação monetária segura para Decimal."""

    if isinstance(raw_value, bool) or isinstance(raw_value, float):
        raise TypeError("valores monetários binários não são aceitos")

    if isinstance(raw_value, Decimal):
        value = raw_value
    elif isinstance(raw_value, int):
        value = Decimal(raw_value)
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if _BRAZILIAN_MONEY.fullmatch(text):
            text = text.replace(".", "").replace(",", ".")
        elif not _DECIMAL_MONEY.fullmatch(text):
            raise ValueError("formato monetário não reconhecido")

        try:
            value = Decimal(text)
        except InvalidOperation as error:
            raise ValueError("valor monetário inválido") from error
    else:
        raise TypeError("tipo de valor monetário não suportado")

    if not value.is_finite():
        raise ValueError("o valor monetário deve ser finito")
    if value.as_tuple().exponent < -2:
        raise ValueError("o valor monetário deve ter no máximo duas casas")
    return value
