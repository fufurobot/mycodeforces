#!/usr/bin/env bash
set -euo pipefail

script_path="$(realpath "${BASH_SOURCE[0]}")"
repo_root="$(dirname "$(dirname "$script_path")")"
readme_file="$repo_root/README.md"
badge_begin='<!-- BEGIN BADGE INJECTION -->'
badge_end='<!-- END BADGE INJECTION -->'

# inject_badges: rewrites the block between the badge markers of README.md from
# what the repository says about itself. A README without both markers is left
# alone, so the markers have to be added once by hand.
inject_badges() {
  if [[ ! -f "$readme_file" ]]; then
    return 0
  fi
  # The markers may also be quoted elsewhere in the README, so the pair to fill
  # is the first one, and a marker must be alone on its line to count.
  if [[ "$(grep -c -x -F "$badge_begin" "$readme_file" || true)" == "0" ]] \
    || [[ "$(grep -c -x -F "$badge_end" "$readme_file" || true)" == "0" ]]; then
    printf 'Skipping badges: %s needs a %s and a %s line\n' \
      "$readme_file" "$badge_begin" "$badge_end" >&2
    return 0
  fi

  python3 - "$repo_root" "$readme_file" "$badge_begin" "$badge_end" <<'PY'
import os
import re
import subprocess
import sys
import urllib.parse

root, readme_path, begin, end = sys.argv[1:]


def git(*args):
    try:
        result = subprocess.run(
            ("git",) + args, cwd=root, capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def read(name):
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def dynamic(kind, source, selector, label, link, color="blue", logo="", logo_color="white"):
    """A shields.io badge whose text is read from SOURCE at render time.

    A source that is missing or unparseable renders a placeholder such as
    "resource not found" rather than a stale value, which is the point: these
    badges describe the project as it is on GitHub, not as it was when the
    watcher last ran. JSON, YAML, and TOML sources take a JSONPath `query`; a
    plain-text source takes a `search` regex and a `replace` template.
    """
    selector_key = "search" if kind == "regex" else "query"
    params = [
        ("url", source),
        (selector_key, selector),
        ("label", label),
        ("color", color),
    ]
    if kind == "regex":
        params.append(("replace", "$1"))
    if logo:
        params.append(("logo", logo))
        params.append(("logoColor", logo_color))
    image = f"https://img.shields.io/badge/dynamic/{kind}?" + "&".join(
        f"{key}={urllib.parse.quote(value, safe='')}" for key, value in params
    )
    return f"[![{label}]({image})]({link})"


MANAGER_COLORS = {"uv": "dea584", "pdm": "9575cd", "micromamba": "6db33f"}


def badge_color(name):
    return MANAGER_COLORS.get(name, "blue")


def shields(label, message, color, link, logo=""):
    """A shields.io badge that links to link.

    shields.io wants `--` for a literal dash and `_` for a space; operators and
    other punctuation are URL-encoded.
    """
    def escape(text):
        text = urllib.parse.quote(str(text).replace("-", "--").replace(" ", "_"), safe="._")
        return text

    image = f"https://img.shields.io/badge/{escape(label)}-{escape(message)}-{color}"
    if logo:
        image += f"?logo={logo}&logoColor=white"
    return f"[![{label}]({image})]({link})"


# Repository identity, read the way Codespaces and Binder read it.
owner = repository = ""
match = re.search(
    r"github\.com[:/]+([^/]+)/([^/\s]+?)(?:\.git)?$",
    git("config", "--get", "remote.origin.url"),
)
if match:
    owner, repository = match.group(1), match.group(2)
# A detached HEAD or a fresh checkout reports no branch, so fall back to the
# branch that the remote repository uses.
branch = git("symbolic-ref", "--short", "-q", "HEAD")
if not branch:
    branch = "main"

# Facts about the project, from the files this template maintains.
requirements = read("requirements.txt")
python_constraint = ""
for line in requirements.splitlines():
    fields = line.split()
    if fields and fields[0].lower() == "python-must":
        python_constraint = "".join(fields[1:])
        break

manager = ""
for line in read(".env").splitlines():
    match = re.match(r"\s*(?:export\s+)?DEPENDENCY_MANAGER\s*=\s*(.*)", line)
    if match:
        value = match.group(1).split("#")[0].strip().strip("'\"")
        if value:
            manager = value.lower()
if not manager:
    manager = "micromamba" if os.path.isdir(os.path.join(root, "notebooks")) else "uv"

# The package that the release workflow publishes, and where it publishes it.
# build-package.sh defaults the name, and PACKAGE_NAME may override it, so the
# default is used only when the release workflow does not name one.
package_name = ""
release_workflow = read(os.path.join(".github", "workflows", "release.yml"))
match = re.search(r"^\s*PACKAGE_NAME:\s*(\S+)\s*$", release_workflow, re.MULTILINE)
if match:
    package_name = match.group(1).strip("'\"")
else:
    build_script = read(os.path.join(".devcontainer", "build-package.sh"))
    match = re.search(r"PACKAGE_NAME:-([A-Za-z0-9._-]+)", build_script)
    package_name = match.group(1) if match else ""

license_text = read("LICENSE")
licenses = [
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL-3.0"),
    ("Apache License", "Apache-2.0"),
    ("MIT License", "MIT"),
    ("BSD 3-Clause", "BSD-3-Clause"),
]
license_name = next((name for marker, name in licenses if marker in license_text), "")


def count_requirements(text):
    return len([
        line for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and not line.lower().startswith("python-must")
    ])


# The workflow the CI badge reports on: the one this template ships, else the
# first workflow file there is.
workflows_dir = os.path.join(root, ".github", "workflows")
workflow_files = (
    sorted(n for n in os.listdir(workflows_dir) if n.endswith((".yml", ".yaml")))
    if os.path.isdir(workflows_dir) else []
)
own_workflow = (
    "devcontainer.yml"
    if "devcontainer.yml" in workflow_files
    else (workflow_files[0] if workflow_files else "")
)

badges = []
# Where the repository is a GitHub one, its own state is the source of truth
# for every badge that can be read from it.
github = owner and repository
base = f"https://github.com/{owner}/{repository}"
raw = f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}"

if github:
    badges.append(
        shields("github", f"{owner}/{repository}", "181717", base, "github")
    )
    badges.append(
        dynamic("json", f"https://api.github.com/repos/{owner}/{repository}",
                "$.default_branch", "branch", base, "181717", "github")
    )
    # The latest release, which 404s into "no releases found" until one exists.
    badges.append(
        f"[![release](https://img.shields.io/github/v/release/{owner}/{repository}"
        f"?sort=semver&display_name=tag&logo=github)](https://github.com/"
        f"{owner}/{repository}/releases/latest)"
    )

# The interpreter pin, which the watcher materializes from python-must.
if github:
    badges.append(
        dynamic("regex", f"{raw}/.python-version", r"^(.+)$", "python",
                "https://www.python.org/downloads/", "3776AB", "python")
    )
elif python_constraint:
    python_message = re.sub(r"^[\^~=]+", "", python_constraint) or python_constraint
    badges.append(
        shields("python", python_message, "3776AB",
                "https://www.python.org/downloads/", "python")
    )

# The managers the CI workflow exercises, straight from its matrix.
if github:
    badges.append(
        dynamic("yaml", f"{raw}/.github/workflows/devcontainer.yml",
                "$.jobs.scripts.strategy.matrix.manager[*]", "managers", base,
                badge_color(manager))
    )

# Binder builds an environment from the repository, so it needs a repository
# that mybinder.org can clone, not just a checkout.
if github:
    badges.append(
        "[![Binder](https://mybinder.org/badge_logo.svg)]"
        f"(https://mybinder.org/v2/gh/{owner}/{repository}/{branch})"
    )

    badges.append(
        shields("codespaces", "open", "181717",
                f"https://codespaces.new/{owner}/{repository}?quickstart=1", "github")
    )

if own_workflow:
    badges.append(
        f"[![ci](https://img.shields.io/github/actions/workflow/status/{owner}/"
        f"{repository}/{own_workflow}?branch={branch}&logo=githubactions"
        f"&logoColor=white)]({base}/actions/workflows/{own_workflow})"
    )

if github:
    badges.append(
        f"[![license](https://img.shields.io/github/license/{owner}/{repository}"
        f"?logo=gnu&color=blue)]({base}/blob/{branch}/LICENSE)"
    )
    badges.append(
        f"[![last commit](https://img.shields.io/github/last-commit/{owner}/"
        f"{repository}?branch={branch})]({base}/commits/{branch})"
    )
elif license_name:
    badges.append(shields("license", license_name, "blue", "LICENSE"))

# The versions on TestPyPI, read from the index itself. Until a publish
# succeeds this renders "package not found" rather than a stale value.
if package_name:
    badges.append(
        f"[![TestPyPI](https://img.shields.io/pypi/pyversions/{package_name}"
        f"?pypiBaseUrl=https://test.pypi.org&logo=pypi&logoColor=white)]"
        f"(https://test.pypi.org/project/{package_name}/)"
    )

# Requirement counts have no remote source, so they stay local.
main_count = count_requirements(requirements)
dev_count = count_requirements(read("requirements-dev.txt"))
if main_count:
    badges.append(shields("dependencies", str(main_count), "blue", "requirements.txt"))
if dev_count:
    badges.append(
        shields("dev dependencies", str(dev_count), "blue", "requirements-dev.txt")
    )

with open(readme_path, encoding="utf-8") as handle:
    readme = handle.read()

block = "\n".join([begin, "", " ".join(badges), "", end]) + "\n"
updated = re.sub(
    re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
    lambda _: block,
    readme,
    count=1,
    flags=re.DOTALL,
)
if updated != readme:
    with open(readme_path, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"README badges updated ({len(badges)})")
PY
}

inject_badges
