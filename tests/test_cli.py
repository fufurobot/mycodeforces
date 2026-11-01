from __future__ import annotations

import json
import shutil
from pathlib import Path

import mycodeforces.cli as cli
from mycodeforces.cli import (
    codeforces_problem_url,
    list_problems,
    normalize_entry,
    page_entries,
    page_title,
    resolve_page,
    run_test,
)


def test_page_entries_and_resolution(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested_page = docs / "graph" / "flow" / "max-flow.md"
    nested_page.parent.mkdir(parents=True)
    nested_page.write_text("# Maximum flow\n", encoding="utf-8")
    (docs / "graph" / "index.md").write_text("# Graphs\n", encoding="utf-8")

    entries = page_entries(docs)

    assert [name for name, _ in entries] == ["graph/flow/max-flow", "graph/index"]
    assert page_title(nested_page) == "Maximum flow"
    assert resolve_page(entries, "graph/flow/max_flow") == (
        "graph/flow/max-flow",
        nested_page,
    )
    assert normalize_entry(" Graph/Max_Flow ") == "graph/max-flow"
    assert codeforces_problem_url("1840B") == (
        "https://codeforces.com/problemset/problem/1840/B"
    )


def test_project_root_uses_bundled_package_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package = tmp_path / "package" / "mycodeforces"
    (package / "data" / "docs").mkdir(parents=True)
    (package / "data" / "tests").mkdir()
    (package / "cli.py").write_text("", encoding="utf-8")
    (tmp_path / "working-directory").mkdir()
    monkeypatch.setattr(cli, "__file__", str(package / "cli.py"))

    assert cli.project_root(tmp_path / "working-directory") == package / "data"


def test_problem_list_combines_manifest_and_sample_fixtures(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "manifest.json").write_text(
        json.dumps({"pages": [{"path": "ds/fenwick", "codeforces": ["4A", "1A"]}]}),
        encoding="utf-8",
    )
    data = tmp_path / "tests" / "data" / "3A"
    data.mkdir(parents=True)

    assert list_problems(tmp_path) == ["1A", "3A", "4A"]


def test_list_uses_indexed_metadata_before_pages_are_translated(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "manifest.json").write_text(
        json.dumps(
            {
                "pages": [
                    {"path": "ds/fenwick", "title": "树状数组", "codeforces": ["4A", "1A"]},
                    {"path": "ds/segment-tree", "title": "线段树", "codeforces": ["3A"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "project_root", lambda: tmp_path)

    assert cli.main(["list", "ds/fenwick"]) == 0
    assert "ds/fenwick: 4A, 1A" in capsys.readouterr().out
    assert cli.main(["list", "ds"]) == 0
    listing = capsys.readouterr().out
    assert "ds/fenwick: 4A, 1A" in listing
    assert "ds/segment-tree: 3A" in listing


def test_run_test_rejects_missing_sample_data(tmp_path: Path, capsys) -> None:
    source = tmp_path / "solution.py"
    source.write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tests" / "test_examples.py").parent.mkdir(parents=True)

    result = run_test(tmp_path, "4A", source)

    assert result == 2
    assert "No sample input/output fixtures" in capsys.readouterr().err


def test_run_test_executes_all_sample_fixtures(tmp_path: Path) -> None:
    project = tmp_path / "project"
    tests_dir = project / "tests"
    data_dir = tests_dir / "data" / "999999A"
    data_dir.mkdir(parents=True)
    test_sources = Path(__file__).parent
    shutil.copy(test_sources / "conftest.py", tests_dir / "conftest.py")
    shutil.copy(test_sources / "test_examples.py", tests_dir / "test_examples.py")
    (data_dir / "sample-1.in").write_text("2 3\n", encoding="utf-8")
    (data_dir / "sample-1.out").write_text("5\n", encoding="utf-8")
    (data_dir / "sample-2.in").write_text("12 30\n", encoding="utf-8")
    (data_dir / "sample-2.out").write_text("42\n", encoding="utf-8")
    source = tmp_path / "solution.py"
    source.write_text(
        "print(sum(map(int, input().split())))\n",
        encoding="utf-8",
    )

    assert run_test(project, "999999A", source) == 0
    source.write_text("print(0)\n", encoding="utf-8")
    assert run_test(project, "999999A", source) != 0
