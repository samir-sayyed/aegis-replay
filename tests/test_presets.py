from pathlib import Path

from aegis_replay.config import load_target


def test_named_junit_presets_share_safe_argv_contract(tmp_path: Path) -> None:
    for runner in ("gradle-junit", "pytest-junit", "jest-junit", "xcode-junit"):
        config = tmp_path / "aegis.yaml"
        config.write_text(f"schema_version: 1\ntargets:\n  - name: sample\n    runner: {runner}\n    command: ['python', '-m', 'pytest']\n    junit_xml: reports/junit.xml\n")
        assert load_target(config, "sample").name == "sample"


def test_target_accepts_safe_scope_and_aegis_owned_selector(tmp_path: Path) -> None:
    config = tmp_path / "aegis.yaml"
    config.write_text(
        "schema_version: 1\ntargets:\n  - name: swift\n    runner: xcode-junit\n"
        "    command: ['./run-tests.sh']\n    junit_xml: reports/junit.xml\n"
        "    scope: [Sources, Tests]\n"
        "    environment: {AEGIS_XCODE_ONLY_TESTING: 'AppTests/StatusTests/testActive'}\n"
    )
    target = load_target(config, "swift")
    assert target.scope == ("Sources", "Tests")
    assert target.environment["AEGIS_XCODE_ONLY_TESTING"] == "AppTests/StatusTests/testActive"


def test_python_bytecode_control_is_a_safe_runtime_environment(tmp_path: Path) -> None:
    config = tmp_path / "aegis.yaml"
    config.write_text(
        "schema_version: 1\ntargets:\n  - name: python\n    runner: pytest-junit\n"
        "    command: [python, -m, pytest]\n    junit_xml: reports/junit.xml\n"
        "    environment: {PYTHONDONTWRITEBYTECODE: '1'}\n"
    )
    assert load_target(config, "python").environment["PYTHONDONTWRITEBYTECODE"] == "1"
