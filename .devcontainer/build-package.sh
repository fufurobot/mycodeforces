#!/usr/bin/env bash
set -euo pipefail

# Builds the checked-in Python package in a temporary project directory.
#
#   build-package.sh WORKDIR [OWNER/REPOSITORY]
#
# Artifacts are left in WORKDIR/dist. PACKAGE_VERSION overrides the version
# only in the temporary copy, so the checked-in project metadata is untouched.

workdir="${1:?usage: build-package.sh WORKDIR [OWNER/REPOSITORY]}"
repository="${2:-}"
repo_root="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")"
workdir="$(mkdir -p "$workdir" && realpath "$workdir")"
build_dir="$(mktemp -d "$workdir/.mycodeforce-build.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT

cp "$repo_root/pyproject.toml" "$build_dir/pyproject.toml"
cp "$repo_root/README.md" "$build_dir/README.md"
cp "$repo_root/LICENSE" "$build_dir/LICENSE"
cp -R "$repo_root/src" "$build_dir/src"
mkdir -p "$build_dir/src/mycodeforces/data/tests"
cp -R "$repo_root/docs" "$build_dir/src/mycodeforces/data/docs"
cp "$repo_root/tests/conftest.py" "$repo_root/tests/test_examples.py" \
  "$build_dir/src/mycodeforces/data/tests/"
cp -R "$repo_root/tests/data" "$build_dir/src/mycodeforces/data/tests/data"

if [[ -n "${PACKAGE_VERSION:-}" ]]; then
  python3 - "$build_dir/pyproject.toml" "$PACKAGE_VERSION" <<'PY'
import re
import sys

path, version = sys.argv[1:]
text = open(path, encoding="utf-8").read()
updated, count = re.subn(
    r'(?m)^(?P<prefix>version\s*=\s*)"[^\"]+"$',
    lambda match: f'{match.group("prefix")}"{version}"',
    text,
    count=1,
)
if count != 1:
    raise SystemExit("Could not find [project].version in the copied pyproject.toml")
open(path, "w", encoding="utf-8").write(updated)
PY
fi

if [[ -n "$repository" ]]; then
  python3 - "$build_dir/pyproject.toml" "$repository" <<'PY'
import re
import sys

path, repository = sys.argv[1:]
text = open(path, encoding="utf-8").read()
url = f"https://github.com/{repository}"
if "[project.urls]" not in text:
    text = text.rstrip() + f'\n\n[project.urls]\nRepository = "{url}"\n'
else:
    text, count = re.subn(
        r'(?m)^Repository\s*=\s*"[^"]*"$',
        f'Repository = "{url}"',
        text,
        count=1,
    )
    if count == 0:
        raise SystemExit("[project.urls] exists without a Repository entry")
open(path, "w", encoding="utf-8").write(text)
PY
fi

uv build --project "$build_dir" --out-dir "$workdir/dist"
