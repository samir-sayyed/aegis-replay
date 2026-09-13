from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "aegis_replay", *arguments], capture_output=True, text=True, check=False)


def git(directory: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=directory, capture_output=True, text=True, check=True).stdout


def test_prove_verifies_three_isolated_states_and_records_inputs(tmp_path: Path) -> None:
    (tmp_path / "state.txt").write_text("fixed\n")
    (tmp_path / "runner.py").write_text("from pathlib import Path\nstate=Path('state.txt').read_text().strip()\nfailed=state != 'fixed'\ncases='<testcase classname=\"fixture\" name=\"target\">' + ('<failure/>' if failed else '') + '</testcase>'\nif not failed: cases += '<testcase classname=\"fixture\" name=\"control\"/>'\nPath('result.xml').write_text('<testsuite>'+cases+'</testsuite>')\nraise SystemExit(1 if failed else 0)\n")
    (tmp_path / "aegis.yaml").write_text("schema_version: 1\ntargets:\n  - name: unit\n    runner: command-junit\n    command: ['" + sys.executable + "', 'runner.py']\n    junit_xml: result.xml\n")
    git(tmp_path, "init")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "base")
    known = tmp_path.parent / "known.patch"
    alternate = tmp_path.parent / "alternate.patch"
    (tmp_path / "state.txt").write_text("known\n")
    known.write_text(git(tmp_path, "diff"))
    (tmp_path / "state.txt").write_text("alternate\n")
    alternate.write_text(git(tmp_path, "diff"))
    git(tmp_path, "checkout", "--", "state.txt")
    created = run(tmp_path, "antibody", "create", "proof-demo", "--directory", str(tmp_path), "--invariant", "Target regression stays detected", "--target", "unit", "--test", "fixture#target", "--scope", "state.txt", "--proof-input", "source_revision=" + "a" * 64)
    assert created.returncode == 0, created.stdout
    git(tmp_path, "add", ".aegis")
    git(tmp_path, "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "record")
    result = run(tmp_path, "prove", "proof-demo", "--directory", str(tmp_path), "--known-bad", str(known), "--alternate-bad", str(alternate), "--control", "fixture#control")
    assert result.returncode == 0, result.stdout
    assert '"state": "proved"' in (tmp_path / ".aegis" / "proofs" / "proof-demo.json").read_text()
    explained = run(tmp_path, "antibody", "explain", "proof-demo", "--directory", str(tmp_path))
    assert "Freshness: fresh" in explained.stdout
    (tmp_path / "aegis.yaml").write_text((tmp_path / "aegis.yaml").read_text() + "# changed\n")
    stale = run(tmp_path, "antibody", "explain", "proof-demo", "--directory", str(tmp_path))
    assert "Freshness: stale" in stale.stdout
