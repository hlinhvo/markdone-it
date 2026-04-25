#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-markdone-universal}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
POD_NAME="${POD_NAME:-markdone-universal}"

cd "${PROJECT_DIR}"

echo "Building container image ${IMAGE_NAME}:${IMAGE_TAG}"
podman build -t "localhost/${IMAGE_NAME}:${IMAGE_TAG}" -f ./Containerfile .

if podman pod exists "${POD_NAME}" >/dev/null 2>&1; then
  echo "Stopping existing pod ${POD_NAME}"
  podman pod stop "${POD_NAME}" || true
  echo "Removing existing pod ${POD_NAME}"
  podman pod rm "${POD_NAME}" || true
fi

echo "Injecting VAULT_PATH into kube manifest"
VAULT_PATH="$(cd "${PROJECT_DIR}/../outputs" && pwd)"
sed "s|{{VAULT_PATH}}|${VAULT_PATH}|g" ./podman-kube.yaml > ./podman-kube-generated.yaml

echo "Deploying with podman kube play"
podman kube play --replace ./podman-kube-generated.yaml

echo "Cleaning up temporary manifest"
rm ./podman-kube-generated.yaml

echo
echo "Deployment complete."
echo "Application URL: http://localhost:7482"
echo "Health URL: http://localhost:7482/health"

# Made with Bob
