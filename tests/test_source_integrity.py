import hashlib
from pathlib import Path


def test_raw_files_match_the_recorded_sha256_manifest(raw_data_dir: Path) -> None:
    manifest = raw_data_dir / "SHA256SUMS"

    for entry in manifest.read_text(encoding="ascii").splitlines():
        expected_hash, relative_path = entry.split(maxsplit=1)
        source_file = raw_data_dir.parents[1] / relative_path
        actual_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()

        assert actual_hash == expected_hash, relative_path
