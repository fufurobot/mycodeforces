from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


API_PROBLEMS_URL = "https://codeforces.com/api/problemset.problems"
PROBLEM_URL = "https://codeforces.com/problemset/problem/{contest_id}/{index}"
USER_AGENT = "mycodeforces/0.1.0 (competitive-programming sample fetcher)"
TOPIC_TAGS = {
    "basic": ("implementation",),
    "contest": ("implementation",),
    "dp": ("dp",),
    "ds": ("data structures",),
    "edit-landing": ("implementation",),
    "geometry": ("geometry",),
    "graph": ("graphs",),
    "index": ("implementation",),
    "intro": ("implementation",),
    "lang": ("implementation",),
    "math": ("math",),
    "misc": ("implementation",),
    "search": ("implementation",),
    "string": ("strings",),
    "topic": ("implementation",),
    "tools": ("implementation",),
}
SLUG_TAGS = {
    "binary-search": ("binary search",),
    "bitmask": ("bitmasks",),
    "bitmasks": ("bitmasks",),
    "combinatorics": ("combinatorics",),
    "convex-hull": ("geometry",),
    "divide-and-conquer": ("divide and conquer",),
    "fft": ("fft",),
    "flow": ("flows",),
    "game-theory": ("games",),
    "geometry": ("geometry",),
    "graph": ("graphs",),
    "greedy": ("greedy",),
    "hash": ("hashing",),
    "matching": ("matchings",),
    "matrix": ("matrices",),
    "number-theory": ("number theory",),
    "probability": ("probabilities",),
    "shortest-path": ("shortest paths",),
    "sort": ("sortings",),
    "sorting": ("sortings",),
    "string": ("strings",),
    "tree": ("trees",),
    "trees": ("trees",),
}


def fetch_problemset(session: requests.Session | None = None) -> dict[str, Any]:
    client = session or requests.Session()
    response = client.get(
        API_PROBLEMS_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "OK":
        raise RuntimeError(f"Codeforces API returned an error: {payload!r}")
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("problems"), list):
        raise ValueError("Codeforces API response did not contain a problem list.")
    return result


def _topic_tags(page_path: str, available_tags: set[str]) -> set[str]:
    parts = page_path.lower().split("/")
    tags = set(TOPIC_TAGS.get(parts[0], ()))
    for part in parts:
        tags.update(SLUG_TAGS.get(part, ()))
        normalized = part.replace("-", " ")
        if normalized in available_tags:
            tags.add(normalized)
    return tags & available_tags


def map_pages_to_problems(
    pages: list[dict[str, Any]],
    problemset: dict[str, Any],
    count: int = 5,
) -> dict[str, list[str]]:
    problems = problemset["problems"]
    stats = problemset.get("problemStatistics", [])
    available_tags = {
        tag
        for problem in problems
        for tag in problem.get("tags", [])
    }
    stats_by_id = {
        (stat.get("contestId"), stat.get("index")): stat
        for stat in stats
    }
    usable = [
        problem
        for problem in problems
        if problem.get("contestId") is not None
        and problem.get("index")
        and problem.get("type", "PROGRAMMING") == "PROGRAMMING"
    ]

    candidates_by_page: dict[str, list[tuple[int, int, int, tuple[int, str]]]] = {}
    for page in pages:
        page_path = str(page["path"])
        tags = _topic_tags(page_path, available_tags)
        candidates = []
        for problem in usable:
            matched = tags.intersection(problem.get("tags", []))
            if not matched:
                continue
            problem_key = (problem["contestId"], problem["index"])
            solved = stats_by_id.get(problem_key, {}).get("solvedCount", 0)
            candidates.append(
                (
                    -len(matched),
                    problem.get("rating", 10000),
                    -solved,
                    problem_key,
                )
            )
        candidates.sort()
        if len(candidates) < count:
            raise ValueError(
                f"Only found {len(candidates)} Codeforces candidates for {page_path}; "
                f"need {count}. Matched tags: {', '.join(sorted(tags)) or 'none'}."
            )
        candidates_by_page[page_path] = candidates

    mappings = {page_path: [] for page_path in candidates_by_page}
    assigned: set[tuple[int, str]] = set()
    page_order = sorted(
        candidates_by_page,
        key=lambda page_path: (len(candidates_by_page[page_path]), page_path),
    )
    for round_index in range(count):
        for page_path in page_order:
            for _, _, _, problem_key in candidates_by_page[page_path]:
                if problem_key not in assigned:
                    assigned.add(problem_key)
                    contest_id, index = problem_key
                    mappings[page_path].append(f"{contest_id}{index}")
                    break
            if len(mappings[page_path]) < round_index + 1:
                tags = _topic_tags(page_path, available_tags)
                raise ValueError(
                    f"Only found {len(mappings[page_path])} globally unique "
                    f"Codeforces candidates for {page_path}; need {count}. "
                    f"Matched tags: {', '.join(sorted(tags)) or 'none'}."
                )
    return mappings


def parse_samples(html: str, problem_url: str = "") -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    sample_test = soup.select_one(".sample-test")
    if sample_test is None:
        if soup.select_one(".error") or "problemset/problem" not in problem_url:
            raise ValueError(f"No Codeforces sample block found at {problem_url or 'statement page'}.")
        raise ValueError(
            f"No sample cases found at {problem_url}; the statement markup may have changed."
        )
    inputs = sample_test.select(".input pre")
    outputs = sample_test.select(".output pre")
    if not inputs or len(inputs) != len(outputs):
        raise ValueError(f"Unmatched Codeforces sample input/output blocks at {problem_url}.")

    def preserve_pre(pre: Any) -> str:
        for br in pre.find_all("br"):
            br.replace_with("\n")
        for div in pre.find_all("div"):
            div.insert_before("\n")
        return pre.get_text().lstrip("\n").rstrip() + "\n"

    return [(preserve_pre(inp), preserve_pre(out)) for inp, out in zip(inputs, outputs)]


def fetch_samples(
    problem_id: str,
    session: requests.Session | None = None,
) -> list[tuple[str, str]]:
    match = re.fullmatch(r"([0-9]+)([A-Za-z][0-9]?)", problem_id)
    if not match:
        raise ValueError(f"Invalid Codeforces problem ID: {problem_id!r}")
    contest_id, index = match.groups()
    url = PROBLEM_URL.format(contest_id=contest_id, index=index)
    client = session or requests.Session()
    response = client.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return parse_samples(response.text, url)


def save_problem_samples(root: Path, problem_id: str, samples: list[tuple[str, str]]) -> None:
    if not samples:
        raise ValueError(f"Codeforces problem {problem_id} has no sample cases.")
    data_dir = root / "tests" / "data" / problem_id
    data_dir.mkdir(parents=True, exist_ok=True)
    for number, (sample_input, sample_output) in enumerate(samples, start=1):
        input_path = data_dir / f"sample-{number}.in"
        output_path = data_dir / f"sample-{number}.out"
        input_path.write_text(sample_input, encoding="utf-8")
        output_path.write_text(sample_output, encoding="utf-8")


def update_manifest_mappings(
    root: Path,
    mappings: dict[str, list[str]],
) -> list[dict[str, Any]]:
    manifest_path = root / "docs" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = manifest.get("pages", [])
    for page in pages:
        page["codeforces"] = mappings.get(page["path"], page.get("codeforces", []))
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return pages


def fetch_and_save_all_samples(
    root: Path,
    mappings: dict[str, list[str]],
    session: requests.Session | None = None,
    delay: float = 1.0,
) -> None:
    problem_ids = sorted({problem_id for ids in mappings.values() for problem_id in ids})
    client = session or requests.Session()
    for index, problem_id in enumerate(problem_ids):
        data_dir = root / "tests" / "data" / problem_id
        input_files = sorted(data_dir.glob("sample-*.in")) if data_dir.is_dir() else []
        if input_files and all(path.with_suffix(".out").is_file() for path in input_files):
            continue
        if index:
            time.sleep(delay)
        samples = fetch_samples(problem_id, client)
        save_problem_samples(root, problem_id, samples)
