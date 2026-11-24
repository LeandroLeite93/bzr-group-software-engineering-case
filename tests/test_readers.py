from decimal import Decimal

from precatorios.readers import read_json_records, read_tribunal


def test_read_tribunal_handles_the_actual_encoding_and_dialect(raw_data_dir) -> None:
    records = read_tribunal(raw_data_dir / "dados" / "tribunal.csv")

    assert len(records) == 5
    assert records[0].process_number == "0012345-10.2019.8.26.0053"
    assert records[0].debtor_entity == "Município de São Paulo"
    assert records[0].face_value == Decimal("45000.00")
    assert records[0].source_line == 2


def test_read_json_records_parses_json_numbers_as_decimal(raw_data_dir) -> None:
    records = read_json_records(raw_data_dir / "dados" / "pagamentos.json")

    assert len(records) == 13
    assert records[0]["valor"] == Decimal("15000.0")
    assert records[1]["valor"] == "2.500,50"
