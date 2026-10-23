# Image Build Runners

Every merge to `main` (and every published release) builds and pushes the Docker images to GHCR:

- `ghcr.io/docmanfu/docmanfu/api`
- `ghcr.io/docmanfu/docmanfu/frontend`

Both are built for `linux/amd64` and `linux/arm64` by [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml) from [`docker-bake.hcl`](../docker-bake.hcl). See [DEPLOYMENT.md](DEPLOYMENT.md#image-tags) for the tags.

## Why self-hosted runners

GitHub-hosted runners start every build with an empty cache, and building arm64 on them means QEMU emulation. Self-hosted runners keep a persistent BuildKit builder, so a typical merge (a code change, with no new dependencies) only rebuilds the final `COPY` layers. Times measured on the Mac mini, for both architectures together:

| Build | Time |
|-------|------|
| Code-only change (warm cache) | ~10 s |
| Cold, no cache | ~75 s |

The Dockerfiles are arranged for this: application code is copied last with no `RUN` after it, and the frontend's Node build runs once on the native platform (`--platform=$BUILDPLATFORM`), since its output is static files.

## The machines

| Runner | Host | Label | Role |
|--------|------|-------|------|
| `mac-mini` | Mac mini M4, 192.168.1.6 | `docmanfu-mac` | Primary. Builds arm64 natively and amd64 through Docker Desktop's emulation |
| `beast` | Beast, Ubuntu x86_64, 192.168.1.4 | `docmanfu-beast` | Backup. Builds amd64 natively and arm64 through QEMU (`qemu-user-static`), so it's much slower when cold |

The workflow's `failover` job (on a GitHub-hosted runner) watches the Mac mini build. If no runner has picked the build up after two minutes, or the build fails, it starts the workflow again with `runner=beast` and cancels the original run. Both runners also push a registry cache (`:buildcache` tags), so Beast reuses the Mac mini's layers instead of starting cold.

To build on a specific machine by hand: **Actions → Publish Docker Images → Run workflow**, then choose the runner (or `gh workflow run docker-publish.yml -f runner=beast`).

## Security

The repository is public and these runners are machines on a home network, so:

- `docker-publish.yml` must never run on `pull_request` events. The only triggers are pushes to `main`, releases and manual runs.
- The repository requires approval before workflows run for **all** outside contributors (Settings → Actions → General → "Fork pull request workflows from outside collaborators"). Otherwise a fork PR could edit a workflow to target these runners.
- The runners are registered with `--no-default-labels`, so only workflows asking for `docmanfu-mac` / `docmanfu-beast` explicitly can land on them.
- Each runner has its own `DOCKER_CONFIG` (`~/actions-runner-docmanfu/.docker`), so registry logins from builds never touch the host user's Docker credentials.

## Setting up a runner

Each runner lives in `~/actions-runner-docmanfu` and runs as the logged-in user (`dustin`), who must be able to run `docker`.

```bash
# On your workstation: a registration token (valid for an hour; needs repo admin)
gh api -X POST repos/DocManFu/DocManFu/actions/runners/registration-token --jq .token
```

On the build machine (latest version at <https://github.com/actions/runner/releases>; use `osx-arm64` on the Mac mini, `linux-x64` on Beast):

```bash
mkdir -p ~/actions-runner-docmanfu && cd ~/actions-runner-docmanfu
curl -fsSL https://github.com/actions/runner/releases/download/v2.338.1/actions-runner-linux-x64-2.338.1.tar.gz | tar xz

./config.sh --unattended --url https://github.com/DocManFu/DocManFu --token <TOKEN> \
  --name beast --labels docmanfu-beast --no-default-labels --work _work

# Runner-only Docker config (Mac: also link Docker Desktop's CLI plugins)
mkdir -p .docker
ln -sfn ~/.docker/cli-plugins .docker/cli-plugins   # Mac only
echo "DOCKER_CONFIG=$HOME/actions-runner-docmanfu/.docker" > .env
# PATH for jobs. Mac mini: /Users/dustin/.docker/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
echo "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" > .path

# The persistent builder the workflow uses. Its cache is garbage-collected
# above maxUsedSpace (40GB on the Mac mini, 20GB on Beast)
printf '[worker.oci]\n  gc = true\n  maxUsedSpace = "20GB"\n' > buildkitd.toml
DOCKER_CONFIG=$PWD/.docker docker buildx create --name docmanfu \
  --driver docker-container --buildkitd-config buildkitd.toml --bootstrap

# Start on boot
sudo ./svc.sh install dustin && sudo ./svc.sh start   # Linux (systemd)
./svc.sh install && ./svc.sh start                    # macOS (LaunchAgent, runs while logged in)
```

Linux runners also need QEMU to build arm64 images: `sudo apt-get install qemu-user-static`. Docker Desktop on the Mac handles amd64 emulation itself. On the Mac mini, Docker Desktop must be running (it starts at login).

## Maintenance

```bash
# Runner status
gh api repos/DocManFu/DocManFu/actions/runners --jq '.runners[] | "\(.name) \(.status) \(.busy)"'

# Service logs
journalctl -u 'actions.runner.DocManFu-DocManFu.beast' -f      # Beast
tail -f ~/Library/Logs/actions.runner.DocManFu-DocManFu.mac-mini/*.log   # Mac mini

# Builder cache size, and clearing it (the next build is cold)
export DOCKER_CONFIG=~/actions-runner-docmanfu/.docker
docker buildx du --builder docmanfu | tail -3
docker buildx prune --builder docmanfu -af
```

The runner updates itself. To remove one: `./svc.sh stop && ./svc.sh uninstall` (with `sudo` on Linux), then `./config.sh remove --token <token from: gh api -X POST repos/DocManFu/DocManFu/actions/runners/remove-token --jq .token>`.

If the `docmanfu` builder is deleted, the workflow fails until it's recreated with the `docker buildx create` command above.
