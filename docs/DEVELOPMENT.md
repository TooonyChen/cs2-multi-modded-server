# Development

Run commands from the repository root. Production deployments use the public image pinned in `compose.yaml`; `docker build .` builds the same runtime source locally.

| Path | Purpose |
| --- | --- |
| `compose.yaml` | Default updater + three example server services; copy a service to add N |
| `Dockerfile` | Steam Runtime 4, SteamCMD, Python supervisor/updater, and attribution |
| `runtime/` | Runtime, RCON client, entrypoint, private snapshot importer, tests and offline fixture |
| `game/csgo/` | Bundled upstream mod overlay, mounted by the updater; not baked into the image |
| `private/`, `data/` | Ignored operator credentials and persistent instance/overlay files |
| `scripts/update/` | Maintainer-only tools for reviewed updates to bundled mods and `docs/UPSTREAM.md` |
| `tools/legacy-maintenance/` | Historical sanitized helpers and documented limitations, never started by Compose |
| `docs/` | Operations, migration, attribution and validation evidence |

```sh
python3 -m unittest discover -s runtime -v
python3 -m unittest discover -s tools/legacy-maintenance -v
mkdir -p private
for n in 1 2 3; do cp runtime/server.env.example private/server$n.env; done
docker compose config --quiet
docker build --platform linux/amd64 -t cs2-multi-local:latest .
python3 runtime/docker_smoke.py
```

Copy examples only when initializing a checkout; preserve existing private files. `make test`, `make config`, `make build`, and `make smoke` wrap these checks. To try the local build in an isolated deployment, set `CS2_IMAGE=cs2-multi-local:latest` when running Compose. That starts a real Steam download unless you use the smoke test.

The smoke test uses a random project, disposable bind directories, no published ports or operator credentials, and an explicit offline Steam/process fixture. It exercises bootstrap, three read-only server mounts, independent host-editable cfg/admin files, automatic updates, failed-install quiescence and recovery. `SMOKE_IMAGE` selects another image; `COMPOSE` selects a standalone Compose executable. No real CS2 gameplay is exercised.

The image build uses an allowlist context containing only runtime code, license and attribution. Tests, game resources, private data, credentials, and historical scripts never enter the context. `.github/workflows/fleet.yml` runs tests, root Compose validation, build and Docker smoke. A separate trusted job publishes default-branch SHA/latest tags and semantic version tags after checks pass; PRs have no registry write permission. Release tags must belong to the default branch. Never overwrite a released semantic version; runtime changes need a new release. Release `0.1.1` packages the root layout and documentation with the same runtime source and bundled game resources as `0.1.0`; the earlier semantic image remains unchanged.

The upstream single-server Docker/host/Windows/Kubernetes launchers, cloud scripts, custom-file examples and inherited disabled workflows were removed. Git history preserves them. Existing deployments that used `-f multi/compose.yaml` should keep their old checkout through migration, or switch to root Compose and move `multi/private/serverN.env` to `private/serverN.env`. Root bind paths still resolve to the same repository `data/` and `game/csgo/`; project and named-volume identities remain `cs2-multi`. This source cleanup does not migrate, stop or restart any deployment.
