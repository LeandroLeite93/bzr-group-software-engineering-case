from pathlib import Path

import pytest


@pytest.fixture
def raw_data_dir() -> Path:
    """Diretório dos dados recebidos, sempre tratado como somente leitura."""

    return Path(__file__).parents[1] / "data" / "raw"
