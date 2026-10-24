# Builds the DocManFu image (API, worker and web frontend in one image).
# CI (.github/workflows/docker-publish.yml) adds tags and labels on top of this.
#
# Local example (builds for the current platform only):
#   docker buildx bake -f docker-bake.hcl --set '*.platform=' --load

variable "REGISTRY" {
  default = "ghcr.io/docmanfu/docmanfu"
}

group "default" {
  targets = ["docmanfu"]
}

# Filled in by docker/metadata-action in CI
target "docker-metadata-action" {}

target "docmanfu" {
  inherits   = ["docker-metadata-action"]
  context    = "."
  platforms  = ["linux/amd64", "linux/arm64"]
  cache-from = ["type=registry,ref=${REGISTRY}:buildcache"]
}
