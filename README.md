# mycodeforces

<!-- BEGIN BADGE INJECTION -->

[![github](https://img.shields.io/badge/github-fufurobot%2Fmycodeforces-181717?logo=github&logoColor=white)](https://github.com/fufurobot/mycodeforces) [![branch](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Ffufurobot%2Fmycodeforces&query=%24.default_branch&label=branch&color=181717&logo=github&logoColor=white)](https://github.com/fufurobot/mycodeforces) [![release](https://img.shields.io/github/v/release/fufurobot/mycodeforces?sort=semver&display_name=tag&logo=github)](https://github.com/fufurobot/mycodeforces/releases/latest) [![python](https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Ffufurobot%2Fmycodeforces%2Fmain%2F.python-version&search=%5E%28.%2B%29%24&label=python&color=3776AB&replace=%241&logo=python&logoColor=white)](https://www.python.org/downloads/) [![managers](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2Ffufurobot%2Fmycodeforces%2Fmain%2F.github%2Fworkflows%2Fdevcontainer.yml&query=%24.jobs.scripts.strategy.matrix.manager%5B%2A%5D&label=managers&color=dea584)](https://github.com/fufurobot/mycodeforces) [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/fufurobot/mycodeforces/main) [![codespaces](https://img.shields.io/badge/codespaces-open-181717?logo=github&logoColor=white)](https://codespaces.new/fufurobot/mycodeforces?quickstart=1) [![ci](https://img.shields.io/github/actions/workflow/status/fufurobot/mycodeforces/devcontainer.yml?branch=main&logo=githubactions&logoColor=white)](https://github.com/fufurobot/mycodeforces/actions/workflows/devcontainer.yml) [![license](https://img.shields.io/github/license/fufurobot/mycodeforces?logo=gnu&color=blue)](https://github.com/fufurobot/mycodeforces/blob/main/LICENSE) [![last commit](https://img.shields.io/github/last-commit/fufurobot/mycodeforces?branch=main)](https://github.com/fufurobot/mycodeforces/commits/main) [![TestPyPI](https://img.shields.io/pypi/pyversions/mycodeforces?pypiBaseUrl=https://test.pypi.org&logo=pypi&logoColor=white)](https://test.pypi.org/project/mycodeforces/) [![dependencies](https://img.shields.io/badge/dependencies-3-blue)](requirements.txt) [![dev dependencies](https://img.shields.io/badge/dev_dependencies-3-blue)](requirements-dev.txt)

<!-- END BADGE INJECTION -->

`mycodeforce` connects OI Wiki topics with Codeforces practice problems and
checks Python solutions against saved sample tests.

## Install

```bash
uv sync
```

## Commands

```bash
# Translate OI Wiki pages, map five Codeforces practice problems to each page,
# and fetch their sample input/output into tests/data/.
uv run mycodeforce sync

# Trial run with a small number of pages, or skip Codeforces data fetching.
uv run mycodeforce sync --limit 3 --skip-problems

# Map all pages and fetch Codeforces samples without translating wiki content.
uv run mycodeforce sync --problems-only

# Read a page by its path (subdirectories are separated by /).
uv run mycodeforce page ds/fenwick

# List wiki pages, a section, or all mapped Codeforces problems.
uv run mycodeforce list
uv run mycodeforce list graph
uv run mycodeforce list codeforces

# Run a Python solution against the stored Codeforces sample cases.
uv run mycodeforce test 4A solution.py
```

`sync` uses the OI Wiki `master` source archive and `deep-translator`. It
defaults to the free, unofficial Google Translate interface; use
`--translator mymemory` to select MyMemory when Google is unavailable. Both
providers may be rate-limited, and MyMemory has a shorter per-request limit.
Completed pages and translations are cached so a later run can resume.
Codeforces problem associations are selected using topic tags as practice
candidates, and statement sample fetching depends on Codeforces being reachable.
`--problems-only` is useful when translation is rate-limited; it leaves page
translation and the README outline for a later regular `sync`.

The generated `docs/` pages keep OI Wiki's hierarchy. Each translated page
links to its original source and carries the source content's CC BY-SA 4.0
attribution. Sample fixtures are stored under `tests/data/<problem-id>/` as
paired `sample-N.in` and `sample-N.out` files; the pytest fixtures in `tests/`
read and execute those cases.

## Wiki outline

<!-- BEGIN OI WIKI OUTLINE -->
Run `uv run mycodeforce sync --skip-problems` to generate translated pages and this outline.
<!-- END OI WIKI OUTLINE -->
