from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SampleCase


def test_solution_matches_sample(
    sample_case: SampleCase | None,
    source_code: Path,
) -> None:
    if sample_case is None:
        pytest.skip("Select a problem with --problem-id to run sample tests.")
    result = subprocess.run(
        [sys.executable, str(source_code)],
        input=sample_case.input_path.read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (
        f"{sample_case.name} exited with {result.returncode}.\n"
        f"stderr:\n{result.stderr}"
    )
    expected = sample_case.output_path.read_text(encoding="utf-8").split()
    actual = result.stdout.split()
    assert actual == expected, (
        f"{sample_case.name} output mismatch.\n"
        f"expected: {expected}\n"
        f"actual:   {actual}\n"
        f"stderr:\n{result.stderr}"
    )
