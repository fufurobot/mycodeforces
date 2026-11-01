from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import requests


PROBLEM_ID = re.compile(r"^([0-9]+)([A-Za-z][0-9]?)$")


def project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    package_data = Path(__file__).resolve().parent / "data"
    if (package_data / "docs").is_dir() and (package_data / "tests").is_dir():
        return package_data
    raise FileNotFoundError("Could not find a project root containing pyproject.toml.")


def page_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            return heading.group(1)
    return path.stem.replace("-", " ").title()


def page_entries(docs_dir: Path) -> list[tuple[str, Path]]:
    entries = []
    if docs_dir.is_dir():
        for path in sorted(docs_dir.rglob("*.md")):
            entries.append((path.relative_to(docs_dir).with_suffix("").as_posix(), path))
    return entries


def normalize_entry(value: str) -> str:
    parts = [part.strip().lower().replace("_", "-") for part in value.split("/")]
    return "/".join(part for part in parts if part)


def codeforces_problem_url(problem_id: str) -> str:
    match = PROBLEM_ID.fullmatch(problem_id)
    if not match:
        raise ValueError(f"Invalid Codeforces problem ID in page metadata: {problem_id!r}")
    return f"https://codeforces.com/problemset/problem/{match.group(1)}/{match.group(2)}"


def print_pages(entries: list[tuple[str, Path]], prefix: str = "") -> None:
    selected = [
        (name, path)
        for name, path in entries
        if not prefix or name == prefix or name.startswith(prefix.rstrip("/") + "/")
    ]
    if not selected:
        raise FileNotFoundError(f"No wiki pages found for {prefix!r}.")
    for name, path in selected:
        print(f"{name}: {page_title(path)}")


def resolve_page(entries: list[tuple[str, Path]], entry: str) -> tuple[str, Path] | None:
    normalized = normalize_entry(entry)
    for name, path in entries:
        if normalize_entry(name) == normalized:
            return name, path
    basename_matches = [
        (name, path)
        for name, path in entries
        if normalize_entry(Path(name).name) == normalized
    ]
    if len(basename_matches) == 1:
        return basename_matches[0]
    if len(basename_matches) > 1:
        names = ", ".join(name for name, _ in basename_matches)
        raise ValueError(f"Ambiguous wiki page {entry!r}; use its full path: {names}")
    return None


def manifest_page_problems(root: Path) -> dict[str, list[str]]:
    manifest_path = root / "docs" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        page["path"]: list(page.get("codeforces", []))
        for page in manifest.get("pages", [])
    }


def manifest_page_titles(root: Path) -> dict[str, str]:
    manifest_path = root / "docs" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        page["path"]: str(page.get("title", ""))
        for page in manifest.get("pages", [])
    }


def list_problems(root: Path) -> list[str]:
    problems = {
        problem_id
        for ids in manifest_page_problems(root).values()
        for problem_id in ids
    }
    data_dir = root / "tests" / "data"
    if data_dir.is_dir():
        problems.update(
            path.name
            for path in data_dir.iterdir()
            if path.is_dir() and PROBLEM_ID.fullmatch(path.name)
        )
    return sorted(problems, key=lambda problem_id: (int(re.match(r"\d+", problem_id).group()), problem_id))


def run_test(root: Path, problem_id: str, source_code: Path) -> int:
    if not PROBLEM_ID.fullmatch(problem_id):
        print(f"Invalid Codeforces problem ID: {problem_id!r}", file=sys.stderr)
        return 2
    source_path = source_code.resolve()
    if not source_path.is_file():
        print(f"Source file does not exist: {source_path}", file=sys.stderr)
        return 2
    case_dir = root / "tests" / "data" / problem_id
    if not case_dir.is_dir() or not list(case_dir.glob("sample-*.in")):
        print(f"No sample input/output fixtures found for {problem_id} in {case_dir}", file=sys.stderr)
        return 2
    test_file = root / "tests" / "test_examples.py"
    if not test_file.is_file():
        print(f"Pytest example runner is missing: {test_file}", file=sys.stderr)
        return 2

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(test_file),
        f"--problem-id={problem_id}",
        f"--source-code={source_path}",
    ]
    try:
        return subprocess.run(command, cwd=root, check=False).returncode
    except OSError as error:
        print(f"Could not start pytest: {error}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mycodeforce")
    commands = parser.add_subparsers(dest="command", required=True)

    test_parser = commands.add_parser("test", help="run a Python solution on stored sample cases")
    test_parser.add_argument("problem_id")
    test_parser.add_argument("source_code", type=Path)

    page_parser = commands.add_parser("page", help="show a wiki page or browse the page outline")
    page_parser.add_argument("entry", nargs="?")
    page_parser.add_argument("sub_name", nargs="?")

    list_parser = commands.add_parser("list", help="list wiki pages or Codeforces problems")
    list_parser.add_argument("entry", nargs="?")

    sync_parser = commands.add_parser(
        "sync",
        help="translate OI Wiki pages and fetch related Codeforces sample cases",
    )
    sync_parser.add_argument(
        "--archive",
        type=Path,
        help="use a previously downloaded OI Wiki source ZIP instead of downloading it",
    )
    sync_parser.add_argument(
        "--limit",
        type=int,
        help="process only the first N wiki pages (useful for a small trial run)",
    )
    sync_parser.add_argument(
        "--skip-problems",
        action="store_true",
        help="translate pages only; do not generate Codeforces mappings or fixtures",
    )
    sync_parser.add_argument(
        "--problems-only",
        action="store_true",
        help="index source pages and fetch Codeforces data without translating pages",
    )
    sync_parser.add_argument(
        "--translator",
        choices=("google", "mymemory"),
        default="google",
        help="free translation provider (default: google)",
    )
    return parser


def sync(
    root: Path,
    archive_path: Path | None,
    limit: int | None,
    skip_problems: bool,
    translator_name: str,
    problems_only: bool,
) -> int:
    import time

    from mycodeforces.wiki import import_wiki, index_source_pages

    if root == Path(__file__).resolve().parent / "data":
        raise RuntimeError("Run `sync` from the source checkout, not an installed package.")
    cache_dir = root / ".mycodeforce"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if archive_path is None:
        archive_path = cache_dir / "OI-wiki-master.zip"
        if not archive_path.is_file():
            response = requests.get(
                "https://codeload.github.com/OI-wiki/OI-wiki/zip/refs/heads/master",
                timeout=120,
            )
            response.raise_for_status()
            archive_path.write_bytes(response.content)
    if not archive_path.is_file():
        raise FileNotFoundError(f"OI Wiki archive does not exist: {archive_path}")
    if problems_only:
        pages = index_source_pages(root, archive_path, limit)
    else:
        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator
            from deep_translator.exceptions import BaseError, RequestError, TooManyRequests
        except ImportError as error:
            raise RuntimeError(
                "The translation extra is missing. Install development dependencies "
                "with `uv sync --group dev`."
            ) from error

        if translator_name == "google":
            translator = GoogleTranslator(source="auto", target="en")
            translation_limit = 4500
        else:
            translator = MyMemoryTranslator(source="zh-CN", target="en")
            translation_limit = 400

        def translate(text: str) -> str:
            time.sleep(0.15)
            try:
                return translator.translate(text)
            except (BaseError, RequestError, TooManyRequests) as error:
                raise RuntimeError(
                    f"The {translator_name} translation provider failed: {error}"
                ) from error

        pages = import_wiki(
            root,
            archive_path,
            translate,
            limit,
            max_translation_chars=translation_limit,
        )
        print(f"Translated or reused {len(pages)} OI Wiki pages.")
    if skip_problems:
        return 0

    from mycodeforces.codeforces import (
        fetch_and_save_all_samples,
        fetch_problemset,
        map_pages_to_problems,
        update_manifest_mappings,
    )

    problemset_cache = cache_dir / "codeforces-problemset.json"
    if problemset_cache.is_file():
        problemset = json.loads(problemset_cache.read_text(encoding="utf-8"))
    else:
        problemset = fetch_problemset()
        problemset_cache.write_text(
            json.dumps(problemset, ensure_ascii=False),
            encoding="utf-8",
        )
    mappings = map_pages_to_problems(pages, problemset)
    update_manifest_mappings(root, mappings)
    print(
        f"Mapped {len(pages)} wiki pages to five Codeforces practice candidates each."
    )
    fetch_and_save_all_samples(root, mappings)
    problem_count = len({problem_id for ids in mappings.values() for problem_id in ids})
    mapping_count = sum(len(problem_ids) for problem_ids in mappings.values())
    print(
        f"Sample fixtures available for {problem_count} unique problems across "
        f"{mapping_count} page/problem mappings."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = project_root()
        entries = page_entries(root / "docs")
        if args.command == "test":
            return run_test(root, args.problem_id, args.source_code)
        if args.command == "sync":
            if args.limit is not None and args.limit < 1:
                print("--limit must be a positive integer.", file=sys.stderr)
                return 2
            if args.problems_only and args.skip_problems:
                print("--problems-only cannot be combined with --skip-problems.", file=sys.stderr)
                return 2
            return sync(
                root,
                args.archive,
                args.limit,
                args.skip_problems,
                args.translator,
                args.problems_only,
            )
        if args.command == "page":
            if not entries:
                print(
                    "No translated OI Wiki pages are available. Run `mycodeforce sync` first.",
                    file=sys.stderr,
                )
                return 2
            if not args.entry:
                print_pages(entries)
                return 0
            requested = "/".join(filter(None, (args.entry, args.sub_name)))
            match = resolve_page(entries, requested)
            if match is None:
                prefix = normalize_entry(requested)
                print_pages(entries, prefix)
                return 0
            name, path = match
            print(f"# {page_title(path)}\n")
            print(f"OI Wiki page: https://oi-wiki.org/{name}/\n")
            print(path.read_text(encoding="utf-8"))
            problem_ids = manifest_page_problems(root).get(name, [])
            if problem_ids:
                print("\n## Codeforces practice candidates\n")
                for problem_id in problem_ids:
                    print(f"- [{problem_id}]({codeforces_problem_url(problem_id)})")
            return 0
        if args.entry and args.entry.lower() in {"codeforces", "cf"}:
            problems = list_problems(root)
            if not problems:
                print("No Codeforces problem mappings have been generated yet.")
                return 0
            print("\n".join(problems))
            return 0
        if args.entry:
            match = resolve_page(entries, args.entry)
            if match:
                name, _ = match
                ids = manifest_page_problems(root).get(name, [])
                if ids:
                    print(f"{name}: {', '.join(ids)}")
                else:
                    print(f"{name}: no Codeforces problems mapped yet")
                return 0
            prefix = normalize_entry(args.entry)
            page_problems = manifest_page_problems(root)
            mapped_pages = [
                (name, ids)
                for name, ids in sorted(page_problems.items())
                if name == prefix or name.startswith(prefix.rstrip("/") + "/")
            ]
            if mapped_pages:
                for name, ids in mapped_pages:
                    print(f"{name}: {', '.join(ids) if ids else 'no Codeforces problems mapped yet'}")
                return 0
            print_pages(entries, prefix)
            return 0
        if not entries:
            page_titles = manifest_page_titles(root)
            if page_titles:
                for name, title in sorted(page_titles.items()):
                    print(f"{name}: {title}")
                return 0
            print("No wiki pages are indexed yet. Run `mycodeforce sync` first.")
            return 0
        print_pages(entries)
        return 0
    except (FileNotFoundError, ValueError, requests.RequestException, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
