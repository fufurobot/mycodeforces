#!/usr/bin/env bash
set -euo pipefail

script_path="$(realpath "${BASH_SOURCE[0]}")"
repo_root="$(dirname "$(dirname "$script_path")")"
requirements_file="$repo_root/requirements.txt"
dev_requirements_file="$repo_root/requirements-dev.txt"
pyproject_file="$repo_root/pyproject.toml"
environment_file="$repo_root/environment.yml"
python_version_file="$repo_root/.python-version"
binder_environment_file="$repo_root/binder/environment.yml"
env_file="$repo_root/.env"
readme_file="$repo_root/README.md"
badges_script="$repo_root/.devcontainer/readme-badges.sh"
watcher_log="${TMPDIR:-/tmp}/stupidinfer-dependencies-watcher.log"
lock_file="${TMPDIR:-/tmp}/stupidinfer-dependencies-watcher.lock"

project_name="$(basename "$repo_root" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g')"

# ---------------------------------------------------------------------------
# Requirements files
#
# A comment whose whole content is a group name opens a group in
# requirements.txt, and the requirements after it belong to that group:
#
#   numpy
#   # tools
#   ruff
#   black
#
# leaves numpy ungrouped and puts ruff and black in the `tools` group. Other
# comments are ignored. requirements-dev.txt is a plain list without groups and
# is installed into the development group.
# ---------------------------------------------------------------------------

# print_group FILE GROUP: the requirements of one group, one per line. The group
# is "" for the requirements before the first group.
print_group() {
  awk -v group="$2" '
    {
      sub(/\r$/, "")
      sub(/^[[:space:]]+/, "")
      sub(/[[:space:]]+$/, "")
      if ($0 == "") {
        next
      }
      if ($0 ~ /^#/) {
        header = $0
        sub(/^#[[:space:]]*/, "", header)
        if (header ~ /^[A-Za-z0-9][A-Za-z0-9._-]*$/) {
          section = header
        }
        next
      }
      if (tolower($0) ~ /^python-must([[:space:]<>=!~]|$)/) {
        next
      }
      if (section == group) {
        print
      }
    }
  ' "$1"
}

# print_groups FILE: the names of the groups of FILE, one per line.
print_groups() {
  awk '
    {
      sub(/\r$/, "")
      sub(/^[[:space:]]+/, "")
      sub(/[[:space:]]+$/, "")
      if ($0 !~ /^#/) {
        next
      }
      header = $0
      sub(/^#[[:space:]]*/, "", header)
      if (header ~ /^[A-Za-z0-9][A-Za-z0-9._-]*$/ && !(header in seen)) {
        seen[header] = 1
        print header
      }
    }
  ' "$1"
}

read_python_constraint() {
  if [[ ! -f "$requirements_file" ]]; then
    return 0
  fi
  awk '
    {
      sub(/\r$/, "")
      if (tolower($1) == "python-must") {
        $1 = ""
        sub(/^[[:space:]]+/, "")
        print
        count++
      }
    }
    END { if (count > 1) exit 1 }
  ' "$requirements_file" | tr -d '[:space:]'
}

# in_binder: whether this workspace runs on a Binder instance. Binder sets
# these variables for the repository that it built, and nothing else does.
in_binder() {
  [[ -n "${BINDER_LAUNCH_HOST:-}" || -n "${BINDER_REPO_URL:-}" \
    || -n "${BINDER_REF_URL:-}" || -n "${BINDER_SERVICE_HOST:-}" ]]
}

# prepare_binder_workspace: Binder provides its environment through conda, so a
# workspace built there is treated like a notebook project: notebooks/ makes the
# dependency manager resolve to micromamba, which then reuses the Binder
# environment instead of creating a second one.
prepare_binder_workspace() {
  if ! in_binder; then
    return 0
  fi
  if [[ ! -d "$repo_root/notebooks" ]]; then
    mkdir -p "$repo_root/notebooks"
    printf 'Binder workspace detected: created %s\n' "$repo_root/notebooks"
  fi
  printf 'Binder workspace detected: using the conda environment provided by Binder\n'
}

# write_python_version: materializes python-must as .python-version, the file
# that uv, pdm and asdf read. Only a concrete version can be written, so a
# constraint such as ">=3.10" becomes its lower bound.
write_python_version() {
  local constraint version
  constraint="$(read_python_constraint)"
  if [[ -z "$constraint" ]]; then
    return 0
  fi

  # ">=3.12,<3.14" names its lower bound, "==3.11.*" its series, and a
  # trailing comment is not part of the version.
  constraint="${constraint%%#*}"
  version="$(sed -E 's/^[[:space:]]*[<>=!~^]+//; s/[<>=!~^]//g; s/[[:space:]]+//g' <<<"$constraint")"
  version="${version%%,*}"
  # "3.11.*" names the 3.11 series; any other trailing part is a real version.
  version="${version%.\*}"
  if [[ ! "$version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    printf 'Skipping %s: python-must "%s" does not name a version\n' \
      "$python_version_file" "$constraint" >&2
    return 0
  fi
  if [[ -f "$python_version_file" && "$(cat "$python_version_file")" == "$version" ]]; then
    return 0
  fi
  printf '%s\n' "$version" > "$python_version_file"
  printf 'Wrote %s with Python %s\n' "$python_version_file" "$version"
}

load_dependency_manager() {
  local manager="" line value

  if [[ -f "$env_file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%$'\r'}"
      if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?DEPENDENCY_MANAGER[[:space:]]*=(.*)$ ]]; then
        value="${BASH_REMATCH[2]}"
        value="${value%%#*}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
          value="${value:1:${#value}-2}"
        fi
        manager="$value"
      fi
    done < "$env_file"
  fi

  manager="${manager:-${DEPENDENCY_MANAGER:-}}"
  manager="${manager,,}"

  # Binder only provides a conda environment, so nothing can replace it there.
  if in_binder; then
    manager="micromamba"
  fi
  case "$manager" in
    uv)
      printf 'uv\n'
      ;;
    mamba | micromamba)
      printf 'micromamba\n'
      ;;
    pdm)
      printf 'pdm\n'
      ;;
    "")
      if [[ -d "$repo_root/notebooks" ]]; then
        printf 'micromamba\n'
      else
        printf 'uv\n'
      fi
      ;;
    *)
      printf 'Unsupported DEPENDENCY_MANAGER value: %s (use uv, pdm, or micromamba)\n' "$manager" >&2
      return 1
      ;;
  esac
}

require_requirements() {
  if [[ ! -f "$requirements_file" ]]; then
    printf 'Cannot synchronize dependencies: %s is missing\n' "$requirements_file" >&2
    return 1
  fi
}

initialize_uv_project() {
  local python_constraint
  python_constraint="$(read_python_constraint)"
  local uv_init_args=(init --bare --name "$project_name")
  if [[ -n "$python_constraint" ]]; then
    uv_init_args+=(--python "$python_constraint")
  fi
  uv "${uv_init_args[@]}" "$repo_root"
}

# uv_add GROUP FILE: lets uv add FILE, either to the dependency group GROUP or,
# for an empty GROUP, to the project dependencies.
uv_add() {
  local group="$1" file="$2"
  if [[ -n "$group" ]]; then
    uv add --project "$repo_root" --no-sync --group "$group" --requirements "$file"
  else
    uv add --project "$repo_root" --no-sync --requirements "$file"
  fi
}

sync_uv_project() (
  local temp_dir group
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  require_requirements
  if [[ ! -f "$pyproject_file" ]]; then
    initialize_uv_project
  fi

  print_group "$requirements_file" "" > "$temp_dir/requirements.txt"
  if [[ -s "$temp_dir/requirements.txt" ]]; then
    uv_add "" "$temp_dir/requirements.txt"
  fi
  while IFS= read -r group; do
    print_group "$requirements_file" "$group" > "$temp_dir/$group.txt"
    if [[ -s "$temp_dir/$group.txt" ]]; then
      uv_add "$group" "$temp_dir/$group.txt"
    fi
  done < <(print_groups "$requirements_file")

  if [[ -f "$dev_requirements_file" ]]; then
    uv add --project "$repo_root" --no-sync --dev --requirements "$dev_requirements_file"
  fi

  uv sync --project "$repo_root"
)

initialize_environment() {
  python3 - "$environment_file" "$project_name" "$(read_python_constraint)" <<'PY'
import json
import re
import sys

path, name, constraint = sys.argv[1:]
python = "python" + (re.sub(r"\s+", "", constraint) or ">=3.10")
lines = [f"name: {json.dumps(name)}", "channels:", "  - conda-forge", "dependencies:", f"  - {python}", "  - pip"]
with open(path, "w", encoding="utf-8") as environment:
    environment.write("\n".join(lines) + "\n")
PY
}

# link_binder_environment: Binder reads binder/environment.yml, so that file is
# a symlink to the generated root one. A symlink that already points at the
# right file is left untouched; a regular file is never removed, since it may
# hold edits.
link_binder_environment() {
  local binder_dir link_target
  binder_dir="$(dirname "$binder_environment_file")"
  link_target="$(realpath --relative-to="$binder_dir" "$environment_file")"

  if [[ -L "$binder_environment_file" ]]; then
    if [[ "$(readlink "$binder_environment_file")" == "$link_target" ]]; then
      return 0
    fi
    rm -f "$binder_environment_file"
  elif [[ -e "$binder_environment_file" ]]; then
    printf 'Skipping the Binder symlink: %s is a regular file\n' "$binder_environment_file" >&2
    return 0
  fi

  mkdir -p "$binder_dir"
  ln -s "$link_target" "$binder_environment_file"
  printf 'Linked %s -> %s\n' "$binder_environment_file" "$link_target"
}

# read_requirements_of FILE: the requirements of FILE as arguments, one per
# line. pdm takes the requirements as arguments rather than as a file.
read_requirements_of() {
  local file="$1" requirement
  if [[ ! -s "$file" ]]; then
    return 0
  fi
  while IFS= read -r requirement; do
    requirement="${requirement%$'\r'}"
    # pdm takes the requirements as arguments, so comments and blank lines
    # have to go: a comment reaches pdm as a specifier and fails with
    # "Expected package name at the start of dependency specifier".
    requirement="$(sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' <<<"$requirement")"
    [[ -n "$requirement" ]] || continue
    [[ "$requirement" == \#* ]] && continue
    printf '%s\0' "$requirement"
  done < "$file"
}

# pdm_add GROUP FILE: adds the requirements of FILE to the dependency group
# GROUP, or to the project dependencies for an empty GROUP. `-dG` is what puts
# a group in [dependency-groups] rather than in optional-dependencies.
pdm_add() {
  local group="$1" file="$2"
  local -a requirements=()
  local -a group_args=()
  mapfile -d '' -t requirements < <(read_requirements_of "$file")
  ((${#requirements[@]})) || return 0

  if [[ -n "$group" ]]; then
    group_args=(-dG "$group")
  fi
  pdm add --project "$repo_root" --no-sync ${group_args[@]+"${group_args[@]}"} "${requirements[@]}"
}

# pdm_add_dev FILE: adds the requirements of FILE to the dev group.
pdm_add_dev() {
  local file="$1"
  local -a requirements=()
  mapfile -d '' -t requirements < <(read_requirements_of "$file")
  ((${#requirements[@]})) || return 0
  pdm add --project "$repo_root" --no-sync --dev "${requirements[@]}"
}

sync_pdm_project() (
  local temp_dir group
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT

  require_requirements
  if [[ ! -f "$pyproject_file" ]]; then
    initialize_uv_project
  fi

  print_group "$requirements_file" "" > "$temp_dir/requirements.txt"
  pdm_add "" "$temp_dir/requirements.txt"
  while IFS= read -r group; do
    print_group "$requirements_file" "$group" > "$temp_dir/$group.txt"
    pdm_add "$group" "$temp_dir/$group.txt"
  done < <(print_groups "$requirements_file")

  if [[ -f "$dev_requirements_file" ]]; then
    pdm_add_dev "$dev_requirements_file"
  fi

  pdm install --project "$repo_root"
)

# micromamba_prefix: the environment to install into. On Binder that is the
# environment Binder built, which the CONDA_PREFIX and CONDA_DEFAULT_ENV
# variables point at, so no environment of our own is created there.
micromamba_prefix() {
  if in_binder && [[ -n "${CONDA_PREFIX:-}" ]]; then
    printf '%s\n' "$CONDA_PREFIX"
  else
    printf '%s\n' "$repo_root/.venv"
  fi
}

sync_micromamba_project() (
  local group file temp_dir prefix
  local -a group_files=()
  export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.cache/mamba}"

  require_requirements
  prefix="$(micromamba_prefix)"

  if [[ "$prefix" == "$repo_root/.venv" ]]; then
    if [[ ! -f "$environment_file" ]]; then
      initialize_environment
    fi
    link_binder_environment

    if [[ -f "$repo_root/.venv/conda-meta/history" ]]; then
      micromamba env update --yes --prefix "$repo_root/.venv" --file "$environment_file" --prune
    elif [[ -e "$repo_root/.venv" ]]; then
      printf 'Cannot use %s: it exists but is not a micromamba environment\n' "$repo_root/.venv" >&2
      return 1
    else
      micromamba create --yes --prefix "$repo_root/.venv" --file "$environment_file"
    fi
  else
    printf 'Installing requirements into the Binder environment at %s\n' "$prefix"
  fi

  # Groups are not a micromamba concept, so each one is pip-installed into the
  # environment on its own, as pip does not know about the group comments.
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT
  print_group "$requirements_file" "" > "$temp_dir/requirements.txt"
  while IFS= read -r group; do
    print_group "$requirements_file" "$group" > "$temp_dir/$group.txt"
    group_files+=("$temp_dir/$group.txt")
  done < <(print_groups "$requirements_file")

  if [[ -s "$temp_dir/requirements.txt" ]]; then
    micromamba run --prefix "$prefix" python -m pip install \
      --disable-pip-version-check -r "$temp_dir/requirements.txt"
  fi
  for file in ${group_files[@]+"${group_files[@]}"}; do
    if [[ -s "$file" ]]; then
      micromamba run --prefix "$prefix" python -m pip install \
        --disable-pip-version-check -r "$file"
    fi
  done
  if [[ -f "$dev_requirements_file" ]]; then
    micromamba run --prefix "$prefix" python -m pip install \
      --disable-pip-version-check -r "$dev_requirements_file"
  fi
)

# update_badges: refreshes the generated badges of the README. A README without
# the badge markers, or a missing injector, is not an error.
update_badges() {
  if [[ ! -f "$badges_script" ]]; then
    return 0
  fi
  bash "$badges_script" || printf 'Badge injection failed\n' >&2
  return 0
}

sync_project() {
  local manager
  prepare_binder_workspace
  write_python_version
  manager="$(load_dependency_manager)"
  printf 'Using %s for %s\n' "$manager" "$repo_root"

  case "$manager" in
    uv)
      sync_uv_project
      ;;
    pdm)
      sync_pdm_project
      ;;
    *)
      sync_micromamba_project
      ;;
  esac
  update_badges
}

input_hash() {
  local manager file
  manager="$(load_dependency_manager)"
  {
    printf '%s\n' "$manager"
    for file in "$env_file" "$pyproject_file" "$environment_file" \
      "$requirements_file" "$dev_requirements_file" "$python_version_file" "$readme_file"; do
      [[ ! -f "$file" ]] || sha256sum "$file"
    done
  } | sha256sum | awk '{print $1}'
}

if [[ "${1:-}" == "--once" ]]; then
  sync_project
  exit
fi

if [[ "${1:-}" == "--watch-loop" ]]; then
  exec 9>"$lock_file"
  flock -n 9 || exit 0

  last_hash="$(input_hash)"
  while true; do
    sleep 2
    current_hash="$(input_hash)"
    if [[ "$current_hash" != "$last_hash" ]]; then
      if sync_project; then
        last_hash="$(input_hash)"
      else
        printf 'Dependency synchronization failed at %s\n' "$(date -Is)" >>"$watcher_log"
        last_hash="$current_hash"
      fi
    fi
  done
fi

sync_project
nohup bash "$script_path" --watch-loop >"$watcher_log" 2>&1 </dev/null &
