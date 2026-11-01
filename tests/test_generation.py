from __future__ import annotations

import json
import zipfile
from pathlib import Path

from mycodeforces.codeforces import map_pages_to_problems, parse_samples
from mycodeforces.wiki import (
    import_wiki,
    index_source_pages,
    read_source_page,
    rewrite_asset_links,
    system_language,
    translate_markdown,
    translate_page_on_demand,
    user_cache_directory,
)


def test_translation_preserves_code_math_and_link_destinations() -> None:
    seen: list[str] = []

    def translate(text: str) -> str:
        seen.append(text)
        return text.replace("中文标题", "English title").replace("文字", "text")

    translated = translate_markdown(
        "## 中文标题\n\n保留 `代码` 与 $x^2$ 和 [链接](https://example.com).\n",
        translate,
    )

    assert translated == (
        "## English title\n\n保留 `代码` 与 $x^2$ 和 [链接](https://example.com).\n"
    )
    assert all("代码" not in text and "x^2" not in text for text in seen)
    assert all("https://example.com" not in text for text in seen)


def test_rewrite_asset_links_keeps_local_wiki_links() -> None:
    markdown = "![图](./images/tree.svg) [其他页](../graph/bfs.md)"

    rewritten = rewrite_asset_links(markdown, "ds/fenwick")

    assert rewritten == (
        "![图](https://oi-wiki.org/ds/images/tree.svg) [其他页](../graph/bfs.md)"
    )


def test_import_wiki_keeps_page_hierarchy_and_attribution(tmp_path: Path) -> None:
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.comment = b"abc123"
        archive.writestr(
            "OI-wiki-master/docs/graph/flow.md",
            "# 流\n\n## 最大流\n",
        )
        archive.writestr("OI-wiki-master/docs/index.md", "# 首页\n")
        archive.writestr("OI-wiki-master/README.md", "not a page")
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Project\n\n<!-- BEGIN OI WIKI OUTLINE -->\n<!-- END OI WIKI OUTLINE -->\n",
        encoding="utf-8",
    )

    pages = import_wiki(tmp_path, archive_path, lambda text: text.replace("首页", "Home").replace("流", "Flow"))

    assert [page["path"] for page in pages] == ["graph/flow", "index"]
    generated = (tmp_path / "docs" / "graph" / "flow.md").read_text(encoding="utf-8")
    assert "https://github.com/OI-wiki/OI-wiki/blob/master/docs/graph/flow.md" in generated
    assert "CC BY-SA 4.0" in generated
    manifest = json.loads((tmp_path / "docs" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_commit"] == "abc123"
    outline = readme.read_text(encoding="utf-8")
    assert "- Graph\n  - [Flow](docs/graph/flow.md)" in outline


def test_index_source_pages_does_not_translate_or_create_pages(tmp_path: Path) -> None:
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("OI-wiki-master/docs/ds/fenwick.md", "# 树状数组\n")
    (tmp_path / "docs").mkdir()

    pages = index_source_pages(tmp_path, archive_path)

    assert pages[0]["path"] == "ds/fenwick"
    assert pages[0]["title"] == "树状数组"
    assert not (tmp_path / "docs" / "ds" / "fenwick.md").exists()


def test_on_demand_translation_is_cached_per_language_and_source(
    tmp_path: Path,
) -> None:
    markdown = "# 中文标题\n\n保留 `code`\n"
    calls: list[str] = []

    def translate(text: str) -> str:
        calls.append(text)
        return text.replace("中文标题", "English title")

    english = translate_page_on_demand(markdown, "ds/fenwick", "en", tmp_path, translate)
    calls_after_translation = len(calls)
    cached = translate_page_on_demand(
        markdown,
        "ds/fenwick",
        "en",
        tmp_path,
        lambda _: (_ for _ in ()).throw(AssertionError("cache was not used")),
    )
    spanish = translate_page_on_demand(
        markdown,
        "ds/fenwick",
        "es",
        tmp_path,
        lambda text: text.replace("中文标题", "Título"),
    )

    assert english == cached
    assert "English title" in english
    assert "Título" in spanish
    assert calls_after_translation == 2
    assert len(calls) == calls_after_translation


def test_read_source_page_from_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("OI-wiki-master/docs/ds/fenwick.md", "# 树状数组\n")

    assert read_source_page(archive_path, "ds/fenwick") == "# 树状数组\n"


def test_partial_translation_cache_survives_provider_failure(tmp_path: Path) -> None:
    markdown = "# 中文标题\n\n第二段中文\n"
    first_calls: list[str] = []

    def rate_limited_after_first_chunk(text: str) -> str:
        first_calls.append(text)
        if len(first_calls) == 2:
            raise RuntimeError("rate limited")
        return "English title"

    try:
        translate_page_on_demand(
            markdown,
            "ds/fenwick",
            "en",
            tmp_path,
            rate_limited_after_first_chunk,
        )
    except RuntimeError as error:
        assert str(error) == "rate limited"
    else:
        raise AssertionError("expected translation failure")

    retry_calls: list[str] = []
    translated = translate_page_on_demand(
        markdown,
        "ds/fenwick",
        "en",
        tmp_path,
        lambda text: retry_calls.append(text) or "Second paragraph",
    )

    assert len(first_calls) == 2
    assert len(retry_calls) == 1
    assert "English title" in translated
    assert "Second paragraph" in translated


def test_system_language_uses_user_locale(monkeypatch) -> None:
    monkeypatch.setenv("LC_ALL", "pt_BR.UTF-8")
    monkeypatch.setenv("LC_MESSAGES", "ja_JP.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    assert system_language() == "pt"


def test_user_cache_directory_respects_xdg_cache_home(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("mycodeforces.wiki.sys.platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    assert user_cache_directory() == tmp_path / "cache" / "mycodeforce"


def test_map_pages_selects_five_tag_matched_problems() -> None:
    problems = [
        {
            "contestId": contest_id,
            "index": "A",
            "type": "PROGRAMMING",
            "rating": 800 + contest_id,
            "tags": ["data structures"],
        }
        for contest_id in range(1, 7)
    ]

    mapping = map_pages_to_problems(
        [{"path": "ds/fenwick"}],
        {"problems": problems},
        count=5,
    )

    assert len(mapping["ds/fenwick"]) == 5
    assert "6A" not in mapping["ds/fenwick"]


def test_map_pages_assigns_unique_problems_across_topics() -> None:
    problems = [
        {
            "contestId": contest_id,
            "index": "A",
            "type": "PROGRAMMING",
            "rating": 800 + contest_id,
            "tags": ["data structures"],
        }
        for contest_id in range(1, 13)
    ]

    mapping = map_pages_to_problems(
        [{"path": "ds/fenwick"}, {"path": "ds/segment-tree"}],
        {"problems": problems},
        count=5,
    )

    assert all(len(problem_ids) == 5 for problem_ids in mapping.values())
    assert len({problem_id for ids in mapping.values() for problem_id in ids}) == 10
    assert not set(mapping["ds/fenwick"]).intersection(mapping["ds/segment-tree"])


def test_map_pages_skips_problem_without_fetchable_samples() -> None:
    problems = [
        {
            "contestId": contest_id,
            "index": "A",
            "type": "PROGRAMMING",
            "rating": 800 + contest_id,
            "tags": ["graphs"],
        }
        for contest_id in range(1, 6)
    ]
    problems.append(
        {
            "contestId": 1090,
            "index": "E",
            "type": "PROGRAMMING",
            "rating": 800,
            "tags": ["graphs"],
        }
    )

    mapping = map_pages_to_problems(
        [{"path": "graph"}],
        {"problems": problems},
        count=5,
    )

    assert len(mapping["graph"]) == 5
    assert "1090E" not in mapping["graph"]


def test_parse_samples_preserves_newlines_and_output() -> None:
    html = """
    <div class="sample-test">
      <div class="input"><pre><div>2</div><div>3 4</div></pre></div>
      <div class="output"><pre><div>7</div></pre></div>
      <div class="input"><pre>8<br>9</pre></div>
      <div class="output"><pre>17</pre></div>
    </div>
    """

    assert parse_samples(html, "https://codeforces.com/problemset/problem/1/A") == [
        ("2\n3 4\n", "7\n"),
        ("8\n9\n", "17\n"),
    ]
