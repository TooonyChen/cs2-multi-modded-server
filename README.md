# CS2 Multi Modded Server

[![Fleet checks and public image](https://github.com/TooonyChen/cs2-multi-modded-server/actions/workflows/fleet.yml/badge.svg)](https://github.com/TooonyChen/cs2-multi-modded-server/actions/workflows/fleet.yml)
[![Release](https://img.shields.io/github/v/release/TooonyChen/cs2-multi-modded-server)](https://github.com/TooonyChen/cs2-multi-modded-server/releases)
[![License: LGPL-3.0](https://img.shields.io/badge/License-LGPL--3.0-blue.svg)](LICENSE)

Run **one updater + N Counter-Strike 2 servers** with Docker Compose. Share one game installation and one set of plugin binaries and resources, while keeping each server's configuration, plugin data, logs, credentials and ports independent.

Based on [Kus' CS2 Modded Server](https://github.com/kus/cs2-modded-server), with its public mod resources preserved. This fork provides a coordinated multi-server runtime and a public deployment image:

```text
ghcr.io/tooonychen/cs2-multi-modded-server:0.1.1
```

No local image build or GHCR login is required. The image targets **Linux amd64**. CS2 itself is downloaded by SteamCMD on first startup.

> [!NOTE]
> v0.1.1 packages the root repository layout and English documentation. Runtime source and bundled game resources are unchanged from v0.1.0. The original v0.1.0 image remains available.

## Features

- **One shared installation:** the updater downloads and validates CS2 once; all servers use the same game files, plugin binaries, gamedata and translations.
- **Independent server state:** each instance has private cfg files, administrator permissions, plugin settings, databases, logs, demos and Steam user data.
- **Coordinated automatic updates:** supervisors stop all game processes before the updater writes to the shared installation. Linux file locks prevent concurrent readers and writes.
- **Two update policies:** update immediately with `force`, or defer until every configured server reports no human players with `empty`.
- **Host-editable configuration:** instance `cfg`, `addons` and `logs` shortcuts make private files accessible without copying files out of containers.
- **Bundled mod ecosystem:** the public upstream overlay includes Metamod:Source, CounterStrikeSharp, GameModeManager, MatchZy, movement and game-mode plugins. See the [complete versioned inventory](docs/UPSTREAM.md#mods-installed).
- **Public container releases:** GitHub Actions validates the runtime and publishes versioned Linux amd64 images to GHCR.
- **Private migration tooling:** import an operator-supplied offline server snapshot into shared resources and independent instance state.

## Quick Start

### Requirements

- A Linux amd64 host with Docker Engine and Docker Compose **v2.24 or newer**.
- Local Linux storage with working `flock`; sufficient space for a full CS2 installation, Workshop content and private data.
- Network access to Steam and GHCR.
- A separate [Game Server Login Token (GSLT)](https://steamcommunity.com/dev/managegameservers) for each public server.
- Available UDP game ports and TCP RCON ports; defaults are 27015, 27016 and 27017.

CPU, memory and disk requirements depend on player counts, maps and plugins. The shared installation reduces duplicate files; each server still runs its own CS2 process.

### 1. Clone and prepare private configuration

```sh
git clone https://github.com/TooonyChen/cs2-multi-modded-server.git
cd cs2-multi-modded-server
mkdir -p private data/shared data/instances/server1 data/instances/server2 data/instances/server3
for n in 1 2 3; do
  test -f private/server$n.env || cp runtime/server.env.example private/server$n.env
done
```

Edit each `private/serverN.env`:

```dotenv
STEAM_ACCOUNT=your_unique_gslt_for_this_server
RCON_PASSWORD=your_strong_unique_rcon_password
SERVER_PASSWORD=
MAXPLAYERS=32
```

Use different GSLTs and RCON passwords for each server. `SERVER_PASSWORD` is optional. Keep credentials private; `private/` and `data/` are excluded from Git and image builds.

### 2. Start the fleet

```sh
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose logs -f updater
```

On first startup the updater downloads and validates CS2, applies the bundled and private overlays, then releases the servers to start. This can take time. Each instance's convenience directories appear after its first successful preparation.

### 3. Connect and inspect

| Service | Host UDP game port | Host TCP RCON port | Private state |
| --- | --- | --- | --- |
| `server1` | 27015 | 27015 | `data/instances/server1/` |
| `server2` | 27016 | 27016 | `data/instances/server2/` |
| `server3` | 27017 | 27017 | `data/instances/server3/` |

Connect from the CS2 console with `connect YOUR_SERVER_IP:27015` (or 27016 / 27017).

```sh
docker compose ps
docker compose logs -f server1
```

Restrict TCP RCON access with your host or network firewall. The example publishes both protocols; Docker port publication alone does not restrict RCON to trusted clients.

> [!WARNING]
> The default `UPDATE_POLICY=force` interrupts active matches when an update is detected. Choose `empty` if updates should wait for every configured server to report zero human players.

## Architecture

```text
                       SteamCMD / Steam
                              |
                    updater (single writer)
                      |                 |
             game volume (RW)    control volume
                      |          locks and status
          +-----------+-----------+
          |           |           |
       server1     server2     server3 ... serverN
       /base RO    /base RO    /base RO
          |           |           |
       private     private     private
       instance    instance    instance
```

The updater mounts the shared game volume read-write at `/base`. Servers mount it read-only and build private directory trees under `/instance/installation`. Immutable resources are linked to the shared base; the small CS2 executable is copied into each tree so executable-relative paths resolve correctly. Configurations are seeded once as regular private files. Existing settings are preserved across updates.

The control volume coordinates file locks, update markers and per-instance status. Supervisors retain shared locks for the full lifetime of game processes. The updater obtains an exclusive lock before installation and keeps games stopped until a successful update completes.

| Repository path | Purpose |
| --- | --- |
| [compose.yaml](compose.yaml) | Default deployment: one updater and three example servers |
| [Dockerfile](Dockerfile) | Steam Runtime 4, SteamCMD and Python runtime image |
| [runtime/](runtime/) | Supervisor, updater, RCON client, importer and verification fixtures |
| [game/csgo/](game/csgo/) | Public bundled mods and configuration defaults, mounted by the updater |
| `data/shared/` | Private central resource overlay, applied after bundled resources |
| `data/instances/serverN/` | Independent persistent state for one server |
| `private/serverN.env` | Private credentials and instance environment |
| [docs/](docs/) | Operations, migration, development, attribution and validation |
| [scripts/update/](scripts/update/) | Maintainer tools for reviewed bundled mod updates |
| [tools/legacy-maintenance/](tools/legacy-maintenance/) | Historical helpers; not started by this Compose project |

The default named volumes are `cs2-multi_game` and `cs2-multi_control`. Changing the Compose project name changes their prefix. See [architecture and recovery](docs/OPERATIONS.md) for the complete locking, persistence and failure protocol.

## Configuration

### Deployment settings

Edit [compose.yaml](compose.yaml) for instance identities, maps, startup cfgs, mounts and ports.

| Setting | Default | Purpose |
| --- | --- | --- |
| `CS2_IMAGE` | `ghcr.io/tooonychen/cs2-multi-modded-server:0.1.1` | Compose image selection for updater and servers |
| `UPDATE_POLICY` | `force` | `force` or `empty` update admission policy |
| `CHECK_INTERVAL` | `300` | Seconds between updater checks; minimum effective interval is 5 seconds |
| `INSTANCE_IDS` | `server1 server2 server3` | Updater's complete list of participating instances |
| `INSTANCE_ID` | Unique per service | Instance status identity |
| `MAP` | `de_dust2` | Startup map |
| `EXEC` | `on_boot.cfg` | Startup cfg |
| `STEAM_ACCOUNT` | Empty example | Instance GSLT |
| `RCON_PASSWORD` | Empty example | Instance RCON password and status polling credential |
| `SERVER_PASSWORD` | Empty | Optional player connection password |
| `MAXPLAYERS` | `32` in env example | Instance player limit |

`CS2_IMAGE`, `UPDATE_POLICY` and `CHECK_INTERVAL` are interpolated by Compose from the shell or a local Compose `.env` file. The example explicitly sets `MAP` and `EXEC` in service `environment`; edit those entries to change them, because service environment takes precedence over `env_file`.

For example, select the empty-server policy:

```sh
UPDATE_POLICY=empty docker compose up -d
```

Advanced runtime settings include `STOP_TIMEOUT` (45 seconds) and `STEAMCMD_TIMEOUT` (7200 seconds). Add them explicitly to the appropriate service environment when needed. Keep Compose's stop grace period longer than the process cleanup deadline.

### Private files and administrator permissions

After the first successful startup:

```text
data/instances/server1/
├── cfg -> installation/game/csgo/cfg
├── addons -> installation/game/csgo/addons
├── logs -> installation/game/csgo/logs
├── installation/
└── home/
```

| Configure | Host path for server1 |
| --- | --- |
| CS2 server / startup settings | `data/instances/server1/cfg/server.cfg`, `on_boot.cfg` |
| CounterStrikeSharp administrators | `data/instances/server1/addons/counterstrikesharp/configs/admins.json` |
| Administrator groups / overrides | Same directory: `admin_groups.json`, `admin_overrides.json` |
| CounterStrikeSharp core | Same directory: `core.json` |
| Plugin / GameModeManager settings | Same directory: `plugins/<plugin>/<plugin>.json` |
| Plugin-local data and databases | `data/instances/server1/addons/counterstrikesharp/plugins/<plugin>/` |
| CounterStrikeSharp logs | `data/instances/server1/addons/counterstrikesharp/logs/` |

Runtime files belong to UID/GID `10001:10001`; host editing may require sudo or an appropriate group/ACL. Imported trees must have the correct ownership before startup. Stop affected services before staging configuration or resource changes.

To reuse administrator permissions, explicitly copy selected admin JSON files into each instance. They remain independent copies. Never share an active SQLite database between servers. Shared binary links point to container `/base` and may appear broken when viewed from the host; the three convenience directory links remain usable on the host.

### Configuration ownership

Bundled defaults initialize missing private files. Updating `game/csgo/` or `data/shared/` does **not** overwrite existing private settings. Migrate a changed configuration schema deliberately for each instance. While stopped, deleting a private configuration allows the next start to seed the current default.

Use `data/shared/` for trusted central binaries, gamedata, translations and resources that all servers should share. Keep credentials, player records and instance-specific settings out of central overlays. See [configuration ownership](docs/OPERATIONS.md) and [private snapshot import](docs/MIGRATION.md).

## Adding More Servers

Copy a server service in `compose.yaml`. Give every instance a unique identity, private env file, state directory and host ports, and add its ID to updater `INSTANCE_IDS`.

For example, add this entry under `services`:

```yaml
  server4:
    <<: *server
    environment:
      <<: *server-env
      INSTANCE_ID: server4
    env_file: ./private/server4.env
    volumes: ["game:/base:ro", "control:/control", "./data/instances/server4:/instance"]
    ports: ["27018:27015/udp", "27018:27015/tcp"]
```

Change updater's list to `INSTANCE_IDS: server1 server2 server3 server4`, then prepare and start it:

```sh
mkdir -p data/instances/server4
test -f private/server4.env || cp runtime/server.env.example private/server4.env
# Edit private/server4.env with a new GSLT and RCON password.
docker compose config --quiet
docker compose up -d
```

All servers listen on 27015 inside their own containers; host ports distinguish them. Do not share an instance directory or `INSTANCE_ID`. When removing a server, also remove its ID from the updater list so the `empty` policy does not wait for a missing instance.

## Update Policies

| Policy | Behavior |
| --- | --- |
| `force` (default) | Stop all game processes and update when a new Steam build or central overlay change is detected, regardless of player count |
| `empty` | Begin only when every configured instance has a fresh running status reporting zero human players; bots do not block updates |

Missing, stale, offline, unreachable or unparseable status defers an `empty` update. RCON authentication failures also defer it. Players can join between a sample and shutdown, so `empty` is a best-effort precondition. Bootstrap and recovery of an update already started must complete before games can run.

The updater checks Steam's public build ID and a SHA-256 of central overlays. During an update it requests shutdown, waits for all game locks, runs `app_update 730 validate`, reapplies overlays, patches the Metamod search path and records the successful version before allowing restarts.

> [!IMPORTANT]
> A failed or interrupted installation keeps all games stopped until the updater repairs it successfully. This is not an atomic snapshot rollback. Inspect `docker compose logs updater`, fix the underlying error and allow a retry; do not delete the update marker to bypass recovery.

Only this updater may write to the shared installation. Do not run a host SteamCMD job, another project, a legacy updater or `-autoupdate` against the same base. Back up a consistent set of shared game, control, overlay and private instance data. See [operations and recovery](docs/OPERATIONS.md#automatic-update-protocol).

## Mods

The repository preserves the public upstream mod overlay in [game/csgo/](game/csgo/). The updater mounts and applies it automatically. **These resources are not baked into the container image**; keep the repository overlay alongside Compose.

Bundled does not mean every plugin is loaded at startup. Plugins under `plugins/disabled/` are available for explicit loading by mode/settings cfgs. Actual activation depends on startup cfgs, CounterStrikeSharp/Metamod configuration and the selected mode. Loading every mutually incompatible game-mode plugin at once is not the default behavior.

The [complete mod inventory](docs/UPSTREAM.md#mods-installed) records versions and upstream links. It includes frameworks and utilities, plus competitive/practice, retake, deathmatch, GunGame, surf/bhop/timer, arena, prefire and fun-mode resources. This is an inventory, not a guarantee of compatibility with the latest CS2 build.

The public bundle contains official **GameModeManager 2.0.0** with its matching Panorama menu stack and Workshop addon `3831211166`. The [reviewed baseline](docs/BUNDLED-FIXES.md) records CSS/Metamod pins, allocator fixes, licenses, migration steps and acceptance limits, including the official FixRandomSpawn 1.2.0 package, its cross-mode random-spawn behavior and unknown upstream license metadata. All 34 public mode entries are preserved, with the Casual (1.6) cfg filename corrected to its existing Linux case. Fresh instances start with an empty CSS administrator list; existing private admin files are retained. Private custom mode lists, administrator IDs, credentials and player databases are not included. Import your own effective configuration from a private offline snapshot using the [migration guide](docs/MIGRATION.md).

Framework and plugin releases are deliberately staged and reviewed. The running updater applies changes to the central overlay; it does not fetch the latest GitHub release of every plugin. Maintainers can inspect updates with:

```sh
bash scripts/update/update.sh --dry-run --no-pull
bash scripts/update/update.sh --list --no-pull
```

Read the [mod maintenance instructions](scripts/update/README.md) before applying updates; the apply command modifies resources and creates commits.

## Docker

### Routine operations

```sh
docker compose ps
docker compose logs -f updater
docker compose logs -f server1
docker compose stop server1
docker compose start server1
docker compose stop
```

Stopping services preserves their data. Avoid `docker compose down --volumes` on a real deployment: it deletes the shared game and coordination volumes.

### Image upgrades and version pins

The default deployment pins release `0.1.1`. Pulling does not select a newer semantic version automatically. To select another published version, set `CS2_IMAGE` consistently for the whole project, for example in a private local `.env` file:

```dotenv
CS2_IMAGE=ghcr.io/tooonychen/cs2-multi-modded-server:0.1.1
```

Then run:

```sh
docker compose pull
docker compose up -d
```

An exact digest can also be used as `ghcr.io/tooonychen/cs2-multi-modded-server@sha256:<digest>`. Images carry source, license and revision labels. Releases publish semantic tags and supplementary `sha-<commit>` tags; default-branch builds also publish `latest`. Keep updater and servers on the same selected image.

Updating the image changes the runtime environment. Steam game updates and staged host mod overlays are managed separately by the updater. Preserve private files and back up persistent state before upgrades.

## Development

Deployments pull the public image. Local builds are available for development:

```sh
python3 -m unittest discover -s runtime -v
python3 -m unittest discover -s tools/legacy-maintenance -v
docker compose config --quiet
docker build --platform linux/amd64 -t cs2-multi-local:latest .
python3 runtime/docker_smoke.py
```

Prepare the example private env files before Compose validation. `make test`, `make config`, `make build` and `make smoke` wrap these commands. To use a local build in an isolated deployment, set `CS2_IMAGE=cs2-multi-local:latest`.

The Docker smoke test creates a disposable project using an explicit offline Steam/process fixture. It exercises three servers, read-only base mounts, independent host-editable settings, automatic updates, failed-install shutdown and recovery. `SMOKE_IMAGE` selects an image and `COMPOSE` selects a standalone Compose executable.

GitHub Actions runs tests, Compose validation, an image build and the fixture smoke before publishing. Pull requests have no package write permission. Release commits must belong to the default branch. Private files and game resources are excluded from the allowlisted image build context.

See [development details](docs/DEVELOPMENT.md) and [recorded validation](docs/VALIDATION.md). Historical single-server, host, Windows and Kubernetes launchers remain available in Git history; root Compose is the current deployment entry point. Existing users of `multi/compose.yaml` should read the layout transition notes in the development guide before switching.

## Known Limitations

- Linux amd64 and local Linux filesystems only; NFS/CIFS and distributed locks are unsupported.
- Updates stop the entire fleet. There is no rolling game update or automatic snapshot rollback.
- The shared binary/resource set is common to every instance, even when modes and configuration differ.
- Dynamically downloaded per-server Workshop content remains private and may duplicate; required common resources must be staged centrally.
- Existing private settings require deliberate schema migration after plugin changes.
- The coordination volume is trusted IPC, not isolation between hostile tenants.
- Automated checks validate orchestration with fixtures. Full CS2 installation and engine behavior, real client joining, plugin ABI compatibility, map transitions, Workshop downloads and menu rendering still require isolated gameplay acceptance.
- No production migration or cutover is performed by publishing this repository or release.

## Contributing

Report reproducible bugs through [GitHub Issues](https://github.com/TooonyChen/cs2-multi-modded-server/issues). Include the image version/revision, host platform, sanitized Compose configuration, relevant logs and reproduction steps. Remove GSLTs, RCON passwords, player data and private administrator identities.

Keep runtime changes focused, run the relevant checks above, and preserve upstream attribution and licenses. For bundled mod changes, update the version inventory alongside the resources and describe compatibility testing. Do not overwrite a released image tag; publish a new version.

## Credits

- [Kus and the original CS2 Modded Server contributors](https://github.com/kus/cs2-modded-server) for the upstream project, configuration and bundled mod ecosystem.
- The authors of [Metamod:Source](https://www.metamodsource.net/), [CounterStrikeSharp](https://github.com/roflmuffin/CounterStrikeSharp) and every plugin listed in the [upstream inventory](docs/UPSTREAM.md).
- Valve for Counter-Strike 2, SteamCMD and the Steam Runtime.

## License

Project source is licensed under [LGPL-3.0](LICENSE). Bundled third-party components retain their own licenses and notices; see [upstream attribution](docs/UPSTREAM.md) and the notices in `game/csgo/`. Downloaded game content remains subject to Valve/Steam terms.
