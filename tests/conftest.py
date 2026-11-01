from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class SampleCase:
    name: str
    input_path: Path
    output_path: Path


def sample_case_files(problem_id: str | None) -> list[SampleCase]:
    if not problem_id:
        return []
    data_dir = Path(__file__).parent / "data" / problem_id
    cases = []
    for input_path in sorted(data_dir.glob("sample-*.in")):
        output_path = input_path.with_suffix(".out")
        if not output_path.is_file():
            raise FileNotFoundError(f"Missing expected output file for {input_path}")
        cases.append(SampleCase(input_path.stem, input_path, output_path))
    return cases


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--problem-id",
        default=None,
        help="Codeforces problem ID fixture set",
    )
    parser.addoption("--source-code", default=None, help="Python solution to execute")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "sample_case" not in metafunc.fixturenames:
        return
    problem_id = metafunc.config.getoption("--problem-id")
    try:
        cases = sample_case_files(problem_id)
    except FileNotFoundError as error:
        raise pytest.UsageError(str(error)) from error
    if cases:
        metafunc.parametrize("sample_case", cases, ids=[case.name for case in cases])
    else:
        metafunc.parametrize("sample_case", [None], ids=["no-samples"])


@pytest.fixture
def source_code(pytestconfig: pytest.Config) -> Path:
    source = pytestconfig.getoption("--source-code")
    if not source:
        pytest.skip("Select a Python solution with --source-code to run sample tests.")
    source_path = Path(source).resolve()
    if not source_path.is_file():
        pytest.fail(f"Source file does not exist: {source_path}")
    return source_path
