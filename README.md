# my python project template

<!-- BEGIN BADGE INJECTION -->

[![github](https://img.shields.io/badge/github-fufurobot%2Fmypython--template-181717?logo=github&logoColor=white)](https://github.com/fufurobot/mypython-template) [![branch](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Ffufurobot%2Fmypython-template&query=%24.default_branch&label=branch&color=181717&logo=github&logoColor=white)](https://github.com/fufurobot/mypython-template) [![release](https://img.shields.io/github/v/release/fufurobot/mypython-template?sort=semver&display_name=tag&logo=github)](https://github.com/fufurobot/mypython-template/releases/latest) [![python](https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Ffufurobot%2Fmypython-template%2Fmain%2F.python-version&search=%5E%28.%2B%29%24&label=python&color=3776AB&replace=%241&logo=python&logoColor=white)](https://www.python.org/downloads/) [![managers](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2Ffufurobot%2Fmypython-template%2Fmain%2F.github%2Fworkflows%2Fdevcontainer.yml&query=%24.jobs.scripts.strategy.matrix.manager%5B%2A%5D&label=managers&color=dea584)](https://github.com/fufurobot/mypython-template) [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/fufurobot/mypython-template/main) [![codespaces](https://img.shields.io/badge/codespaces-open-181717?logo=github&logoColor=white)](https://codespaces.new/fufurobot/mypython-template?quickstart=1) [![ci](https://img.shields.io/github/actions/workflow/status/fufurobot/mypython-template/devcontainer.yml?branch=main&logo=githubactions&logoColor=white)](https://github.com/fufurobot/mypython-template/actions/workflows/devcontainer.yml) [![license](https://img.shields.io/github/license/fufurobot/mypython-template?logo=gnu&color=blue)](https://github.com/fufurobot/mypython-template/blob/main/LICENSE) [![last commit](https://img.shields.io/github/last-commit/fufurobot/mypython-template?branch=main)](https://github.com/fufurobot/mypython-template/commits/main) [![TestPyPI](https://img.shields.io/pypi/pyversions/mypython-template-fufurobot?pypiBaseUrl=https://test.pypi.org&logo=pypi&logoColor=white)](https://test.pypi.org/project/mypython-template-fufurobot/) [![dev dependencies](https://img.shields.io/badge/dev_dependencies-2-blue)](requirements-dev.txt)

<!-- END BADGE INJECTION -->

# features

- compatible with uv, pdm, and micromamba
- auto devcontainer that show respect to python version
- set `DEPENDENCY_MANAGER=uv`, `DEPENDENCY_MANAGER=pdm`, or `DEPENDENCY_MANAGER=micromamba` in `.env` to select the project dependency manager. If unset, projects with a root `notebooks/` directory use micromamba and other projects use uv.
- bun is installed to execute npm tools by bunx
- the selected manager syncs its root manifest directly into `.venv`; if that manifest is missing, it is initialized from `requirements.txt`. The other manager's manifest is generated through a temporary project.

# requirements

`requirements.txt` lists the dependencies. Its first line may set the Python
version with `python-must`:

```text
python-must >= 3.10
numpy
# tools
ruff
black
```

A comment that holds nothing but a name opens a dependency group, and every
requirement after it belongs to that group: `numpy` above is a project
dependency, while `ruff` and `black` are in the `tools` group. Other comments
and blank lines are ignored. Each group is installed by the manager itself,
as a uv dependency group or as a pip install into the micromamba environment.

`requirements-dev.txt` is optional, is a plain list without groups, and is
installed as development dependencies: `jupyterlab` lives there, because it is
not needed to run the project.

# generated manifests

`pyproject.toml` and `environment.yml` are generated from the name of the
project root, so this template does not commit them. Each project gets its own,
and neither is ignored, so they can be committed or edited by hand per project.

# badges

Everything between these two markers is generated, so the badges follow the
project instead of a hardcoded repository:

```text
<!-- BEGIN BADGE INJECTION -->
<!-- END BADGE INJECTION -->
```

The injector reads the `origin` remote, the current branch, `python-must`,
`DEPENDENCY_MANAGER`, `LICENSE`, `.github/workflows/`, and the requirements
files, then writes the repository, Python, manager, Codespaces, Binder, CI,
license, and dependency badges. Leave the markers in place: without both of
them the README is left alone, and everything outside them is preserved.

# Binder

`binder/environment.yml` configures [Binder](https://mybinder.org): repo2docker
builds the project with its Miniconda image. It is a symlink to the generated
root `environment.yml`, so the environment is defined once.

The symlink is expected to dangle in a fresh clone: the root `environment.yml`
is generated per project and is not committed. The dependency watcher creates
the link once the root file exists, replaces a link that points elsewhere, and
leaves a regular file alone, since that one may hold hand edits.

Because the environment comes from the generated file, its Python version is
the one derived from `python-must`, so keep that line on a version repo2docker
ships a lock file for.

A Binder workspace is recognised by the `BINDER_*` variables that Binder sets.
In one, the dependency manager is always micromamba: a root `notebooks/`
directory is created so that the default resolution agrees, and the
requirements are installed into the conda environment that Binder already
built, instead of into a project `.venv`. `DEPENDENCY_MANAGER` cannot override
this, because uv cannot manage a conda environment.

Note that `notebooks/` is tracked once created, so a Binder visit can leave an
untracked directory behind in a checkout.

# tokens

`.env` also holds `GITHUB_TOKEN`, a personal access token with which the
scripts can manage the remote CI configuration. `git` ignores `.env`, and
`.env.example` carries a placeholder instead of a real token, so copy that file
and fill in the value:

```bash
cp .env.example .env
chmod 600 .env
```

# continuous integration

`.github/workflows/devcontainer.yml` runs `post-install.sh` and a one-shot
synchronization on a GitHub runner for each dependency manager, then checks the
generated manifest and badges. Use it instead of running the scripts locally
when the network is unreliable: `gh workflow run devcontainer.yml`, or push
under `.devcontainer/`, `binder/`, or `requirements*.txt`.

# publishing

The template is not a Python package: it describes an environment through
`requirements.txt`. To publish one anyway, `.devcontainer/build-package.sh`
generates a package in a scratch directory with `uv init --package`, which
writes a `pyproject.toml` and a `src` layout, and adds both requirements files
as its development dependencies, so the package and the environment cannot
drift apart. `python-must` and the `# <name>` group headers are dropped on the
way, since neither is a package.

```bash
bash .devcontainer/build-package.sh "$TMPDIR/mypython-template" fufurobot/mypython-template
# artifacts in $TMPDIR/mypython-template/dist
```

`.github/workflows/release.yml` runs that script and publishes to TestPyPI
through a [Trusted Publisher](https://docs.pypi.org/trusted-publishers/): the
workflow asks GitHub for an OIDC token, so no API token or password is stored.
The pending publisher on TestPyPI has to name, exactly:

| Field | Value |
| --- | --- |
| Project | `mypython-template-fufurobot` |
| Owner | `fufurobot` |
| Repository | `mypython-template` |
| Workflow | `release.yml` |
| Environment | `testpypi` |

Publishing happens on a `v*` tag or by running the workflow by hand:

```bash
git tag v0.1.0 && git push origin v0.1.0
gh workflow run release.yml
```

TestPyPI refuses a version that already exists, so every publish needs a new
one. A tag only triggers the workflow: it does not set the version. The version
is whatever `uv init` wrote into the generated `pyproject.toml`, so bumping it
between publishes is what makes each run uploadable.

## attestations

### what they are

An attestation is a signed statement about an uploaded file. When the package
is published, the workflow can also send a small in-toto document per file that
says, in effect, *this exact wheel, with this exact hash, was built and
published by this specific GitHub Actions workflow of this repository*.

The signature does not come from a stored key. GitHub Actions mints a
short-lived OIDC token, Sigstore exchanges it for a certificate, the attestation
is signed with that certificate's key, and the signature is recorded in
Sigstore's transparency log, [Rekor](https://www.sigstore.dev/), so it can be
verified later by anyone, not just by PyPI.

These are the same OIDC mechanics that a Trusted Publisher uses for
authentication, reused to make a claim that outlives the upload. PyPI stores
the attestations it receives next to the files it serves, and they can be
checked afterwards with tooling such as `pypi-attestations` and
`pip install --attest` (see [PyPI's attestation
docs](https://docs.pypi.org/attestations/) and
[PEP 740](https://peps.python.org/pep-0740/)).

### why they matter for PyPI

- **Provenance.** A consumer can check that a wheel really came from this
  repository's release workflow, not from someone who rebuilt it, or uploaded a
  lookalike to another index.
- **Tamper evidence.** The signature binds the file contents to a hash, so a
  differ-by-one-byte substitution no longer goes unnoticed.
- **A durable audit trail.** The Trusted Publisher token that authorised the
  upload expires in minutes; the attestation remains, and names the workflow
  and repository that published it.
- **They are what PyPI is moving toward.** PyPI verifies publisher identity at
  upload time regardless, but attestations are the part that a downstream user
  can verify for themselves, without trusting the index's word for it.

None of this makes an upload work or fail, which is why turning them off is a
real choice rather than a break: the package still installs, it just arrives
without a verifiable statement about where it came from.

### why they are off on TestPyPI

The publish step runs with `attestations: false` for one concrete reason:
Rekor answered `502 Bad Gateway` to this repository's runners, twice in a row,
while being healthy when probed from elsewhere. Because signing happens before
the upload, the failure aborted the publish and nothing reached TestPyPI at
all:

```text
sigstore._internal.rekor.RekorClientError: Rekor returned an unknown error with HTTP 502
```

TestPyPI is a rehearsal target: it exists to prove that the packaging and the
publisher configuration work, its uploads are disposable, and nobody installs
from it expecting a provenance guarantee. Taking on a dependency on a third
party's uptime, to add signatures nobody consumes there, is the wrong trade.

For PyPI proper the opposite holds, and the line should be dropped:

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    # attestations: false        # remove this for PyPI proper
```

Before relying on it, confirm that Rekor is answering, since a `502` there
fails the publish before any upload starts.

### artifacts survive a failed publish

The `build` job is separate from `publish`, so a failed publish never loses the
work: the wheel and sdist remain attached to the run as the `dist` artifact,
and only the `publish` job needs to be re-run:

```bash
gh run rerun <run-id> --failed
```

## what a release publishes

`.github/workflows/release.yml` runs four jobs. `build` generates the package,
and the other three fan out from it:

| Job | Output | Needs |
| --- | --- | --- |
| `build` | wheel and sdist, kept as the `dist` artifact | — |
| `publish` | the package on TestPyPI | `id-token: write` (OIDC) |
| `image` | the devcontainer image, on the GitHub Container Registry | `packages: write` |
| `release` | a GitHub release with the artifacts | `contents: write` |

Every run does all four, whether it was triggered by a `v*` tag or by hand.
A tag push names the release after the tag; any other run names it after the
version the build published, `v` plus that pre-release, so the artifacts of a
rehearsal are kept rather than discarded. Re-running a version replaces its
assets instead of failing.

## versions and collisions

An index refuses a version it already holds, so a second publish of `0.1.0`
fails. The obvious fix, tagging each build with its commit as a local version
(`0.1.0+2f7369b`), does not work: PEP 440 forbids a local version on a public
index, and both PyPI and TestPyPI reject it with

```text
400 The use of local versions in <Version('0.1.0+2f7369b')> is not allowed.
```

A pre-release segment may carry the commit instead, so the build job numbers
each build `BASE.devN`, where `N` is the decimal value of the commit's short
SHA: `0.1.0.dev49755803`. `.dev` accepts only a number, which is why the hex
digits are read as a decimal. That is unique per commit, but it does **not**
sort chronologically — a later commit can have a smaller number — so it is a
stopgap for keeping rehearsals from colliding, not a versioning policy.

For versions that mean something, bump them on purpose with
[bump-my-version](https://pypi.org/project/bump-my-version/), the tool listed
in `requirements-dev.txt`. It is worth using because it rewrites the version in
every file that carries it and commits the change, so the number is chosen
rather than derived, it sorts correctly, and it can produce a matching tag:

```bash
uv run bump-my-version bump patch   # 0.1.0 -> 0.1.1
uv run bump-my-version bump minor   # 0.1.1 -> 0.2.0
```

Configure it in `pyproject.toml` with the files that hold the version, and
point it at your tags:

```toml
[tool.bumpversion]
current_version = "0.1.0"
commit = true
tag = true
tag_name = "v{new_version}"
```

Once a version is chosen that way, the commit-derived pre-release is noise; the
build job derives it only because nothing else supplies a number.

## the devcontainer image

`.devcontainer/Dockerfile` builds the development environment as a standalone
image. It starts from mise's official Debian image,
`ghcr.io/jdx/mise:debian`, which is published for `linux/amd64` and
`linux/arm64` and already carries mise, curl, git, and CA certificates; the
earlier Arch Linux base was published for `linux/amd64` alone. On top of it the
Dockerfile creates the `vscode` user, runs `post-install.sh` so uv, pdm,
micromamba, and bun are installed, and fails the build if any of them cannot
run. It is pushed to `ghcr.io/fufurobot/mypython-template` for both platforms.

`devcontainer.json` builds that Dockerfile rather than pulling the published
image, so a fork works without depending on an image this repository pushes.
The image also runs mise's directories from `/mise`, outside the home
directory, so mounting `~` does not hide anything installed during the build.

The workflow authenticates with the built-in `GITHUB_TOKEN`, whose
`packages: write` permission comes from the job, so no token has to be stored
for automation. `GITHUB_PACKAGES_TOKEN` in `.env` exists for pushing from a
workstation, where that token is not available:

```bash
set -a && . ./.env && set +a
echo "$GITHUB_PACKAGES_TOKEN" | docker login ghcr.io -u fufurobot --password-stdin
docker build -f .devcontainer/Dockerfile -t ghcr.io/fufurobot/mypython-template:dev .
docker push ghcr.io/fufurobot/mypython-template:dev
```

To develop inside the published image instead of building it, point
`devcontainer.json` at it, keeping the mount of this repository:

```json
{ "image": "ghcr.io/fufurobot/mypython-template:latest" }
```

The image does not include the project: it carries the tools, and the
workspace is mounted over `/workspaces` as usual.
