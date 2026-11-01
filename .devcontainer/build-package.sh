#!/usr/bin/env bash
set -euo pipefail

# Builds the project as a distributable package.
#
#   build-package.sh WORKDIR [OWNER/REPOSITORY]
#
# The template describes an environment through requirements.txt, so it has no
# package of its own. A package is generated in WORKDIR with `uv init
# --package`, which writes a pyproject.toml and a src layout, and the
# requirements become its development dependencies, so the two do not drift
# apart. The artifacts are left in WORKDIR/dist.
#
# PACKAGE_VERSION sets the version; without it the version that uv init wrote is
# used unchanged.

workdir="${1:?usage: build-package.sh WORKDIR [OWNER/REPOSITORY]}"
repository="${2:-}"
package_name="${PACKAGE_NAME:-mypython-template-fufurobot}"
project_dir="$workdir/project"

repo_root="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")"
requirements_file="$repo_root/requirements.txt"
dev_requirements_file="$repo_root/requirements-dev.txt"

# Build for the Python version the project declares.
python_version=""
if [[ -f "$requirements_file" ]]; then
  python_version="$(awk 'tolower($1) == "python-must" { $1 = ""; print; exit }' "$requirements_file" \
    | sed -E 's/[[:space:]]//g; s/^[<>=!~^]+//; s/,.*//')"
fi

rm -rf "$project_dir"
mkdir -p "$project_dir"
uv init --package ${python_version:+--python "$python_version"} \
  --name "$package_name" "$project_dir"

# The requirements are read, never modified. They also carry things that are
# not packages: python-must, which is a directive of this template, and the
# `# <name>` group headers, which document groups for the watcher.
plain_requirements() {
  if [[ ! -f "$1" ]]; then
    return 0
  fi
  sed -E '/^[[:space:]]*(#|$)/d' "$1" \
    | sed -E '/^[[:space:]]*python-must([[:space:]]|<|>|=|!|~|$)/Id'
}

main_requirements="$workdir/main-requirements.txt"
dev_requirements="$workdir/dev-requirements.txt"

# PACKAGE_VERSION wins over whatever version uv init chose.
if [[ -n "${PACKAGE_VERSION:-}" ]]; then
  sed -i -E "s|^version = \".*\"\$|version = \"${PACKAGE_VERSION}\"|" "$project_dir/pyproject.toml"
fi

plain_requirements "$requirements_file" > "$main_requirements"
plain_requirements "$dev_requirements_file" > "$dev_requirements"

if [[ -s "$main_requirements" ]]; then
  uv add --project "$project_dir" --dev --requirements "$main_requirements"
fi
if [[ -s "$dev_requirements" ]]; then
  uv add --project "$project_dir" --dev --requirements "$dev_requirements"
fi

# uv init writes no classifiers, and the python-versions badge on an index
# reads "Programming Language :: Python :: X.Y" rather than requires-python,
# so the versions the project supports are listed here.
# uv init writes no classifiers, and the python-versions badge on an index
# reads "Programming Language :: Python :: X.Y" rather than requires-python.
python3 - "$project_dir/pyproject.toml" "$repository" "${python_version:-3.10}" <<'PY'
import re
import sys

path, repository, minimum = sys.argv[1:]
text = open(path, encoding="utf-8").read()

# The python-versions badge on an index reads these classifiers rather than
# requires-python, and uv init writes none.
known = [(3, 10), (3, 11), (3, 12), (3, 13)]
try:
    lower = tuple(int(part) for part in minimum.split(".")[:2])
except ValueError:
    lower = (3, 10)
classifiers = ["Programming Language :: Python :: 3"]
classifiers += [
    f"Programming Language :: Python :: {major}.{minor}"
    for major, minor in known
    if (major, minor) >= lower
]

block = "classifiers = [\n" + "".join(f'    "{c}",\n' for c in classifiers) + "]"
if not re.search(r"^classifiers\s*=", text, re.MULTILINE):
    anchor = re.search(r"^requires-python\s*=.*$", text, re.MULTILINE)
    if anchor:
        text = text[: anchor.end()] + "\n" + block + text[anchor.end():]
    else:
        raise SystemExit("pyproject.toml has no requires-python to anchor on")

if repository and "[project.urls]" not in text:
    text = text.rstrip("\n") + f'\n\n[project.urls]\nRepository = "https://github.com/{repository}"\n'

open(path, "w", encoding="utf-8").write(text)
PY

uv build --project "$project_dir" --out-dir "$workdir/dist"
