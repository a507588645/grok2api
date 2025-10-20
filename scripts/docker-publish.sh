#!/usr/bin/env bash
set -euo pipefail

# Simple helper to build and optionally push a Docker image for this project.
# Usage examples:
#   IMAGE=username/grok2api:latest ./scripts/docker-publish.sh
#   IMAGE=ghcr.io/your-org/grok2api:1.0.0 PLATFORMS=linux/amd64,linux/arm64 ./scripts/docker-publish.sh
#   IMAGE=username/grok2api:dev PUSH=false ./scripts/docker-publish.sh
#
# Env vars:
#   IMAGE       (required) Full image name, e.g. username/grok2api:latest or ghcr.io/org/grok2api:v1
#   PLATFORMS   Target platforms for buildx. Default: linux/amd64. Example: linux/amd64,linux/arm64
#   PUSH        If true, push to registry after build (or use --push with buildx). Default: true
#   BUILD_CTX   Build context directory. Default: .

IMAGE=${IMAGE:-}
PLATFORMS=${PLATFORMS:-linux/amd64}
PUSH=${PUSH:-true}
BUILD_CTX=${BUILD_CTX:-.}

if [[ -z "${IMAGE}" ]]; then
  echo "[ERROR] Please set IMAGE=<registry>/<repo>:<tag>, e.g. IMAGE=username/grok2api:latest"
  exit 1
fi

# Detect if buildx is available
has_buildx=false
if docker buildx version >/dev/null 2>&1; then
  has_buildx=true
fi

if ${has_buildx}; then
  echo "[INFO] Using docker buildx to build image: ${IMAGE}"
  if [[ "${PUSH}" == "true" ]]; then
    echo "[INFO] Building and pushing for platforms: ${PLATFORMS}"
    docker buildx build \
      --platform "${PLATFORMS}" \
      -t "${IMAGE}" \
      "${BUILD_CTX}" \
      --push
  else
    # If multiple platforms requested but not pushing, fall back to linux/amd64 with --load
    if [[ "${PLATFORMS}" == *","* ]]; then
      echo "[WARN] Multiple platforms requested but PUSH=false. Falling back to linux/amd64 with --load."
      PLATFORMS=linux/amd64
    fi
    echo "[INFO] Building and loading image locally for platform: ${PLATFORMS}"
    docker buildx build \
      --platform "${PLATFORMS}" \
      -t "${IMAGE}" \
      "${BUILD_CTX}" \
      --load
  fi
else
  echo "[INFO] docker buildx not found. Using classic docker build for linux/amd64."
  docker build -t "${IMAGE}" "${BUILD_CTX}"
  if [[ "${PUSH}" == "true" ]]; then
    echo "[INFO] Pushing image: ${IMAGE}"
    docker push "${IMAGE}"
  else
    echo "[INFO] Built image locally: ${IMAGE}"
  fi
fi

echo "[DONE] Image processed: ${IMAGE}"
