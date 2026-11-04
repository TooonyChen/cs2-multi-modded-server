# Historical single-server Docker deployment

This directory retains the useful original single-server Docker deployment from commit `61a9377b`, based on [Kus’ CS2 Modded Server](https://github.com/kus/cs2-modded-server). The original installer is preserved unchanged; Docker COPY paths and Compose paths have been adapted to this directory. The root `game/csgo` pack is reused, with no second copy in the repository. The source remains under the root LGPL license and bundled component notices.

The supported fleet product starts from the [root README](../../README.md). This historical installer has its own game volume, downloads/updates Steam on startup, copies mod defaults and overlays, and launches one server. It does not participate in fleet locks or update coordination. Do not share its volume or writable state with the fleet. Its original launcher prints launch arguments including credentials into logs; treat all legacy logs as private. The historical path has only configuration/syntax validation in this cleanup, not CS2 startup or gameplay acceptance.

For a separate development host, from the repository root:

```sh
mkdir -p private data/single-server/custom_files
cp legacy/single-server/server.env.example private/single-server.env
# Edit credentials and settings; do not overwrite an existing env file.
docker compose -f legacy/single-server/compose.yaml config --quiet
# Optional historical deployment: builds a separate image containing the mod pack.
docker compose -f legacy/single-server/compose.yaml up -d --build
```

The example uses the original game ports and must not run alongside another deployment using those ports/GSLTs. Its project/volume names are separate from root Compose. Host/GCP/Windows/Kubernetes deployment scripts, destructive process-kill helpers, duplicate examples and old scheduled workflows remain removed; Git history retains them.
