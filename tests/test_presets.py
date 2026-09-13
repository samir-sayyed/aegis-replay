from pathlib import Path

from aegis_replay.config import load_target


def test_named_junit_presets_share_safe_argv_contract(tmp_path: Path) -> None:
    for runner in ("gradle-junit", "pytest-junit", "jest-junit", "xcode-junit"):
        config = tmp_path / "aegis.yaml"
        config.write_text(f"schema_version: 1\ntargets:\n  - name: sample\n    runner: {runner}\n    command: ['python', '-m', 'pytest']\n    junit_xml: reports/junit.xml\n")
        assert load_target(config, "sample").name == "sample"
