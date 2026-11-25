import csv
import json

from precatorios.pipeline import run_pipeline


def _read_csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def test_pipeline_produces_reconciled_base_and_audit(raw_data_dir, tmp_path) -> None:
    result = run_pipeline(raw_data_dir, tmp_path)

    assert result.summary["entradas"] == {
        "precatorios_tribunal": 5,
        "precatorios_hub": 5,
        "apresentacoes": 6,
        "eventos_pagamento": 13,
    }
    assert result.summary["saidas"]["precatorios"] == 6
    assert result.summary["saidas"]["eventos_pagamento_aceitos"] == 8
    assert result.summary["totais"] == {
        "valor_face": "126300.00",
        "valor_pago_liquido": "34200.50",
    }

    expected_files = {
        "precatorios.csv",
        "pagamentos.csv",
        "pendencias.csv",
        "ocorrencias.csv",
        "resumo.json",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected_files

    precatorios = {
        row["numero_processo"]: row
        for row in _read_csv(tmp_path / "precatorios.csv")
    }
    first = precatorios["0012345-10.2019.8.26.0053"]
    assert first["prazo_pagamento"] == "2026-12-31"
    assert first["total_pago"] == "18000.50"
    assert first["saldo"] == "26999.50"

    third = precatorios["0034567-32.2018.8.26.0405"]
    assert third["total_pago"] == "0.00"
    assert third["status_conciliacao"] == "conciliado"

    payments = _read_csv(tmp_path / "pagamentos.csv")
    assert len(payments) == 8
    latest_ev_001 = next(row for row in payments if row["evento_id"] == "ev-001")
    assert latest_ev_001["valor"] == "15500.00"
    ev_007 = next(row for row in payments if row["evento_id"] == "ev-007")
    assert ev_007["efeito_contabil"] == "-5000.00"

    pending_codes = {row["codigo"] for row in _read_csv(tmp_path / "pendencias.csv")}
    assert {
        "invalid_payment_event",
        "face_value_conflict",
        "debtor_entity_conflict",
        "deadline_conflict",
        "missing_in_hub",
        "missing_in_tribunal",
    } <= pending_codes

    summary_file = json.loads((tmp_path / "resumo.json").read_text(encoding="utf-8"))
    assert summary_file == result.summary
