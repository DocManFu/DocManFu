# Builds the API and frontend images together, in parallel.
# CI (.github/workflows/docker-publish.yml) adds tags and labels on top of this.
#
# Local example (builds for the current platform only):
#   docker buildx bake -f docker-bake.hcl --set '*.platform=' --load

variable "REGISTRY" {
  default = "ghcr.io/docmanfu/docmanfu"
}

group "default" {
  targets = ["api", "frontend"]
}

# Filled in by docker/metadata-action in CI
target "docker-metadata-action-api" {}
target "docker-metadata-action-frontend" {}

target "_common" {
  platforms = ["linux/amd64", "linux/arm64"]
}

target "api" {
  inherits   = ["_common", "docker-metadata-action-api"]
  context    = "."
  cache-from = ["type=registry,ref=${REGISTRY}/api:buildcache"]
}

target "frontend" {
  inherits   = ["_common", "docker-metadata-action-frontend"]
  context    = "frontend"
  cache-from = ["type=registry,ref=${REGISTRY}/frontend:buildcache"]
}
