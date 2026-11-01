from __future__ import annotations

import hashlib
import json
import locale
import os
import posixpath
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable

from bs4 import BeautifulSoup


SOURCE_REPOSITORY = "OI-wiki/OI-wiki"
SOURCE_BRANCH = "master"
SOURCE_URL = f"https://github.com/{SOURCE_REPOSITORY}/blob/{SOURCE_BRANCH}/docs/"
SITE_URL = "https://oi-wiki.org/"
LICENSE_NOTICE = (
    "> Translated from OI Wiki and shared under "
    "[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). "
    "See the linked source page for the original contributors."
)
CHINESE_TEXT = re.compile(r"[\u3400-\u9fff]")
PROTECTED = re.compile(
    r"(`+[^`]*`+|\\\([^)]*\\\)|\\\[[\s\S]*?\\\]|"
    r"\$\$[\s\S]*?\$\$|\$(?!\$)[^$\n]+\$|"
    r"(?<=]\()[^)]*(?=\))|https?://[^\s)>]+|"
    r"<!--[\s\S]*?-->|<[^>]+>)"
)


def system_language() -> str:
    candidates = [
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ]
    try:
        candidates.append(locale.getlocale()[0])
    except (ValueError, TypeError):
        pass
    for candidate in candidates:
        if not candidate or candidate.upper().startswith(("C.", "POSIX")):
            continue
        locale_name = re.split(r"[.@]", candidate, maxsplit=1)[0].replace("_", "-")
        parts = locale_name.split("-")
        language = parts[0].lower()
        if language == "zh" and any(
            part.lower() == "hant" or part.upper() in {"TW", "HK", "MO"}
            for part in parts[1:]
        ):
            return "zh-TW"
        if re.fullmatch(r"[a-z]{2,3}", language):
            return language
    return "en"


def user_cache_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "mycodeforce"


def read_source_page(archive_path: Path, page_path: str) -> str:
    requested = f"{page_path}.md"
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            path = PurePosixPath(name)
            if (
                len(path.parts) >= 3
                and path.parts[1] == "docs"
                and PurePosixPath(*path.parts[2:]).as_posix() == requested
            ):
                return archive.read(name).decode("utf-8")
    raise FileNotFoundError(f"OI Wiki source page was not found: {page_path}")


def translate_page_on_demand(
    markdown: str,
    page_path: str,
    target_language: str,
    cache_dir: Path,
    translate: Callable[[str], str],
) -> str:
    source_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    cache_key = hashlib.sha256(
        f"{page_path}\0{target_language}\0{source_hash}".encode("utf-8")
    ).hexdigest()
    cache_path = cache_dir / "translations" / target_language / f"{cache_key}.md"
    if cache_path.is_file():
        return cache_path.read_text(encoding="utf-8")

    chunk_cache_path = cache_dir / "translations" / target_language / "chunks.json"
    chunk_cache: dict[str, str] = {}
    if chunk_cache_path.is_file():
        cached_chunks = json.loads(chunk_cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached_chunks, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in cached_chunks.items()
        ):
            raise ValueError(f"Invalid translation cache: {chunk_cache_path}")
        chunk_cache = cached_chunks

    try:
        translated = translate_markdown(markdown, translate, chunk_cache)
    finally:
        if chunk_cache:
            _write_json(chunk_cache_path, chunk_cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".md.tmp")
    temporary.write_text(translated, encoding="utf-8")
    temporary.replace(cache_path)
    return translated


def title_from_markdown(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            return BeautifulSoup(match.group(1), "html.parser").get_text(" ", strip=True)
    return fallback.replace("-", " ").title()


def rewrite_asset_links(markdown: str, page_path: str) -> str:
    page_directory = posixpath.dirname(page_path)

    def replace(match: re.Match[str]) -> str:
        destination = match.group(2)
        if (
            not destination
            or destination.startswith(("#", "/", "http://", "https://", "mailto:", "data:"))
            or destination.split("#", 1)[0].lower().endswith(".md")
        ):
            return match.group(0)
        asset_path = posixpath.normpath(posixpath.join(page_directory, destination))
        if asset_path == ".." or asset_path.startswith("../"):
            return match.group(0)
        return f"{match.group(1)}{SITE_URL}{asset_path}{match.group(3)}"

    return re.sub(r"(!?\[[^\]]*\]\()([^\s)]+)([^)]*\))", replace, markdown)


def source_pages(archive: zipfile.ZipFile) -> list[tuple[str, bytes]]:
    pages = []
    for name in archive.namelist():
        path = PurePosixPath(name)
        if (
            len(path.parts) >= 3
            and path.parts[1] == "docs"
            and path.suffix.lower() == ".md"
        ):
            relative = PurePosixPath(*path.parts[2:]).as_posix()
            pages.append((relative, archive.read(name)))
    return sorted(pages)


def _chunks(text: str, limit: int = 4500) -> list[str]:
    if len(text) <= limit:
        return [text]
    segments = re.split(r"(?<=[。！？；.!?;])\s*", text)
    chunks: list[str] = []
    current = ""
    for segment in segments:
        if not segment:
            continue
        if len(segment) > limit:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(segment), limit):
                chunks.append(segment[start : start + limit])
            continue
        if current and len(current) + len(segment) > limit:
            chunks.append(current)
            current = segment
        else:
            current += segment
    if current:
        chunks.append(current)
    return chunks


def translate_markdown(
    markdown: str,
    translate: Callable[[str], str],
    cache: dict[str, str] | None = None,
    max_chars: int = 4500,
) -> str:
    translations = cache if cache is not None else {}
    output: list[str] = []
    in_fence = False
    in_math = False
    html_block_end: str | None = None

    def translate_block(block: str) -> str:
        protected_values: list[str] = []

        def protect(match: re.Match[str]) -> str:
            token = f"ZXQPROTECTEDTOKEN{len(protected_values)}XZQ"
            protected_values.append(match.group(0))
            return token

        masked = PROTECTED.sub(protect, block)
        translated_chunks: list[str] = []
        token_pattern = re.compile(r"ZXQPROTECTEDTOKEN\d+XZQ")
        for chunk in _chunks(masked, max_chars):
            if not CHINESE_TEXT.search(chunk):
                translated_chunks.append(chunk)
                continue
            digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            if digest not in translations:
                result = translate(chunk)
                if not isinstance(result, str) or not result.strip():
                    raise ValueError("Translator returned an empty or invalid result.")
                translations[digest] = result
            translated = translations[digest]
            translated_chunks.append(translated)
        translated = "".join(translated_chunks)
        for index, value in reversed(list(enumerate(protected_values))):
            token = f"ZXQPROTECTEDTOKEN{index}XZQ"
            if token not in translated:
                raise ValueError("Translator altered a protected Markdown token.")
            translated = translated.replace(token, value)
        if token_pattern.search(translated):
            raise ValueError("Unresolved protected Markdown token after translation.")
        return translated

    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        if html_block_end:
            output.append(line)
            if html_block_end in stripped.lower():
                html_block_end = None
            continue
        html_tag = re.match(r"<(script|style|pre)\b", stripped, re.IGNORECASE)
        if html_tag:
            output.append(line)
            closing_tag = f"</{html_tag.group(1).lower()}>"
            if closing_tag not in stripped.lower():
                html_block_end = closing_tag
            continue
        if re.match(r"(```+|~~~+)", stripped):
            in_fence = not in_fence
            output.append(line)
            continue
        if in_fence:
            output.append(line)
            continue
        if "<!--" in line and "-->" not in line:
            output.append(line)
            html_block_end = "-->"
            continue
        if "$$" in line and line.count("$$") % 2:
            in_math = not in_math
            output.append(line)
            continue
        if in_math or not CHINESE_TEXT.search(line):
            output.append(line)
            continue

        ending = "\n" if line.endswith("\n") else ""
        content = line[:-1] if ending else line
        prefix_match = re.match(
            r"^(\s*(?:#{1,6}\s+|[-*+]\s+|>\s*|(?:\d+[.)]\s+)|"
            r"\?\?\??\+?\s*(?:note|tip|warning|example|abstract)\s+\")?)",
            content,
        )
        prefix = prefix_match.group(1) if prefix_match else ""
        translatable = content[len(prefix) :]
        output.append(prefix + translate_block(translatable) + ending)
    return "".join(output)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def update_readme_outline(root: Path, pages: list[dict[str, object]]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    start = "<!-- BEGIN OI WIKI OUTLINE -->"
    end = "<!-- END OI WIKI OUTLINE -->"
    content = readme.read_text(encoding="utf-8")
    if start not in content or end not in content:
        return
    tree: dict[str, object] = {}
    for page in pages:
        parts = str(page["path"]).split("/")
        node = tree
        for part in parts:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError(f"Invalid outline path: {page['path']}")
            node = child
        node["page"] = page

    lines: list[str] = []

    def page_link(page: dict[str, object]) -> str:
        title = str(page["title"]).replace("[", "\\[").replace("]", "\\]")
        return f"[{title}](docs/{page['path']}.md)"

    def render(nodes: dict[str, object], depth: int, parent_path: str = "") -> None:
        for name, value in sorted(nodes.items()):
            if name == "page" or not isinstance(value, dict):
                continue
            page = value.get("page")
            children = {key: item for key, item in value.items() if key != "page"}
            current_path = f"{parent_path}/{name}".strip("/")
            index_node = children.get("index")
            index_page = index_node.get("page") if isinstance(index_node, dict) else None
            if isinstance(page, dict):
                label = page_link(page)
            elif isinstance(index_page, dict):
                label = page_link(index_page)
            elif children:
                label = name.replace("-", " ").title()
            else:
                continue
            lines.append(f"{'  ' * depth}- {label}")
            nested = {
                key: item
                for key, item in children.items()
                if key != "index"
            }
            if nested:
                render(nested, depth + 1, current_path)

    render(tree, 0)
    outline = "\n".join(lines)
    content = content.replace(start + content.split(start, 1)[1].split(end, 1)[0] + end,
                              f"{start}\n{outline}\n{end}")
    readme.write_text(content, encoding="utf-8")


def import_wiki(
    root: Path,
    archive_path: Path,
    translate: Callable[[str], str],
    limit: int | None = None,
    max_translation_chars: int = 4500,
) -> list[dict[str, object]]:
    docs_dir = root / "docs"
    manifest_path = docs_dir / "manifest.json"
    cache_path = root / ".mycodeforce" / "translation-cache.json"
    previous_manifest: dict[str, object] = {}
    previous_cache: dict[str, str] = {}
    if manifest_path.is_file():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if cache_path.is_file():
        previous_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    previous_pages = {
        str(page["path"]): page
        for page in previous_manifest.get("pages", [])
        if isinstance(page, dict) and "path" in page
    }

    with zipfile.ZipFile(archive_path) as archive:
        source = source_pages(archive)
        if limit is not None:
            source = source[:limit]
        pages: list[dict[str, object]] = []
        for relative, content in source:
            relative_path = PurePosixPath(relative)
            page_path = relative_path.with_suffix("").as_posix()
            source_hash = hashlib.sha256(content).hexdigest()
            output_path = docs_dir / relative
            prior = previous_pages.get(page_path, {})
            if (
                output_path.is_file()
                and prior.get("source_sha256") == source_hash
            ):
                page = dict(prior)
                pages.append(page)
                continue

            original = content.decode("utf-8")
            translated = translate_markdown(
                original,
                translate,
                previous_cache,
                max_chars=max_translation_chars,
            )
            translated = rewrite_asset_links(translated, page_path)
            title = title_from_markdown(translated, relative_path.stem)
            source_link = SOURCE_URL + relative
            author = re.search(r"^author:\s*(.+)$", original, re.MULTILINE)
            attribution = f"<!-- Source: {source_link} -->\n"
            if author:
                attribution += f"<!-- Original authors: {author.group(1).strip()} -->\n"
            translated = f"{attribution}{LICENSE_NOTICE}\n\n{translated}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = output_path.with_suffix(output_path.suffix + ".tmp")
            temporary.write_text(translated, encoding="utf-8")
            temporary.replace(output_path)
            page = {
                "path": page_path,
                "title": title,
                "source": source_link,
                "source_sha256": source_hash,
                "codeforces": list(prior.get("codeforces", [])),
            }
            pages.append(page)
            _write_json(cache_path, previous_cache)
            progress_pages = {
                **previous_pages,
                **{str(current["path"]): current for current in pages},
            }
            current_manifest = {
                "source": f"https://github.com/{SOURCE_REPOSITORY}/tree/{SOURCE_BRANCH}/docs",
                "source_commit": archive.comment.decode("utf-8", errors="replace"),
                "pages": sorted(
                    progress_pages.values(),
                    key=lambda current: str(current["path"]),
                ),
            }
            _write_json(manifest_path, current_manifest)

    if limit is not None:
        processed = {str(page["path"]) for page in pages}
        pages.extend(page for path, page in previous_pages.items() if path not in processed)
    pages.sort(key=lambda page: str(page["path"]))
    manifest = {
        "source": f"https://github.com/{SOURCE_REPOSITORY}/tree/{SOURCE_BRANCH}/docs",
        "source_commit": archive.comment.decode("utf-8", errors="replace"),
        "pages": pages,
    }
    _write_json(manifest_path, manifest)
    update_readme_outline(root, pages)
    return pages


def index_source_pages(
    root: Path,
    archive_path: Path,
    limit: int | None = None,
) -> list[dict[str, object]]:
    docs_dir = root / "docs"
    manifest_path = docs_dir / "manifest.json"
    previous_manifest: dict[str, object] = {}
    if manifest_path.is_file():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous_pages = {
        str(page["path"]): page
        for page in previous_manifest.get("pages", [])
        if isinstance(page, dict) and "path" in page
    }

    pages = []
    with zipfile.ZipFile(archive_path) as archive:
        source = source_pages(archive)
        if limit is not None:
            source = source[:limit]
        for relative, content in source:
            page_path = PurePosixPath(relative).with_suffix("").as_posix()
            prior = previous_pages.get(page_path, {})
            source_hash = hashlib.sha256(content).hexdigest()
            original = content.decode("utf-8")
            page = {
                "path": page_path,
                "title": (
                    prior.get("title")
                    if prior.get("source_sha256") == source_hash
                    else title_from_markdown(original, PurePosixPath(relative).stem)
                ),
                "source": SOURCE_URL + relative,
                "source_sha256": source_hash,
                "codeforces": list(prior.get("codeforces", [])),
            }
            pages.append(page)
        if limit is not None:
            processed = {str(page["path"]) for page in pages}
            pages.extend(
                page for path, page in previous_pages.items() if path not in processed
            )
        pages.sort(key=lambda page: str(page["path"]))
        _write_json(
            manifest_path,
            {
                "source": f"https://github.com/{SOURCE_REPOSITORY}/tree/{SOURCE_BRANCH}/docs",
                "source_commit": archive.comment.decode("utf-8", errors="replace"),
                "pages": pages,
            },
        )
    return pages
