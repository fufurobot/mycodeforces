# The devcontainer as a standalone image.
#
# It builds on mise's official Debian image, which is published for linux/amd64
# and linux/arm64 and already carries mise, curl, git and CA certificates. On
# top of that it creates the devcontainer user and runs post-install.sh, so uv,
# pdm, micromamba and bun are present. mise keeps its tools in /mise, outside
# the home directory, so one installed there survives a mounted ~.
#
# Build:
#   docker build -f .devcontainer/Dockerfile -t mypython-template .
# The release workflow builds it for both platforms and pushes it to the GitHub
# Container Registry.

FROM ghcr.io/jdx/mise:debian

USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# The image is slim, so the tools post-install.sh shells out to are installed
# explicitly: curl and bzip2 download and unpack micromamba, and bun's installer
# stops with "error: unzip is required" without unzip. sudo is there so the
# container can install packages the way the devcontainer spec expects.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git tar bzip2 unzip sudo \
 && rm -rf /var/lib/apt/lists/*

# A devcontainer runs as a non-root user, and sudo keeps it able to install
# packages the way the devcontainer spec expects. The whole home directory is
# handed to the user: creating only ~/.local/bin leaves ~/.local owned by root,
# and pdm, which writes ~/.local/share, then fails with
# "Permission denied: '/home/vscode/.local/share'".
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid "$USER_GID" "$USERNAME" \
 && useradd --uid "$USER_UID" --gid "$USER_GID" --create-home --shell /bin/bash "$USERNAME" \
 && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME" \
 && chmod 0444 "/etc/sudoers.d/$USERNAME" \
 && install -d -o "$USERNAME" -g "$USERNAME" "/home/$USERNAME/.local/bin" \
 && chown -R "$USERNAME:$USERNAME" "/home/$USERNAME"

# post-install.sh resolves $HOME, so it runs as the devcontainer user, with the
# PATH that devcontainer.json gives the container.
COPY --chown=vscode:vscode .devcontainer/post-install.sh /tmp/post-install.sh
RUN su "$USERNAME" -s /bin/bash -c \
      'PATH="/home/vscode/.local/bin:$PATH" bash /tmp/post-install.sh' \
 && rm -f /tmp/post-install.sh

# The tools installed above live in /home/vscode/.local/bin; the base image
# already has /mise/shims on PATH, so only that directory is prepended here.
# mise keeps its data, config, and cache in /mise, outside the home directory,
# so what mise installs survives a mounted ~, and MISE_YES keeps it from asking
# for confirmation. This precedes the check below, which resolves the same PATH
# the container will have.
ENV PATH="/home/vscode/.local/bin:${PATH}" \
    MISE_DATA_DIR="/mise" \
    MISE_CONFIG_DIR="/mise" \
    MISE_CACHE_DIR="/mise/cache" \
    MISE_YES="1"

# Fail the build rather than ship an image whose tools do not run.
RUN for tool in mise uv pdm micromamba bun; do \
      command -v "$tool" >/dev/null || { echo "$tool is missing" >&2; exit 1; }; \
    done

USER vscode
WORKDIR /workspaces

LABEL org.opencontainers.image.title="mypython-template" \
      org.opencontainers.image.description="Python project template: uv, pdm, and micromamba" \
      org.opencontainers.image.source="https://github.com/fufurobot/mypython-template" \
      org.opencontainers.image.licenses="AGPL-3.0"
