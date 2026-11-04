# Fleet architecture and operations

The default image is `ghcr.io/tooonychen/cs2-multi-modded-server:0.1.1` for Linux amd64. Run `docker compose pull` followed by `docker compose up -d`; no local build or registry login is required for the public package. The default is pinned to release `0.1.1`; optionally set `CS2_IMAGE` to another release, a SHA tag or a digest. The image contains the runtime and SteamCMD, while CS2 is installed into the shared volume on first boot. Valve/Steam terms apply to downloaded game content. The source remains LGPL-3.0.

Use one project with `docker compose ...`. A service can be copied for any N; do not share an INSTANCE_ID or instance directory. Add every service ID to updater.INSTANCE_IDS for the empty policy. Docker named volumes must live on a local Linux filesystem with working flock; NFS/CIFS/distributed mounts are not supported by this implementation.

The updater alone mounts `game:/base` read-write. Servers mount the same volume read-only and build private directory trees under `/instance/installation`. Their resource/plugin files are symlinks into `/base`, so VPKs, DLLs, native libraries and gamedata are one shared copy. The small CS2 executable is copied on each start so executable-relative engine paths resolve into that instance tree. Configs and plugin settings are seeded once as regular private files. All newly generated data, logs, demos and plugin files live in private directories. HOME/Steam user data is also per instance. Central mod overlay files are mounted from `game/csgo` and `data/shared`; the latter and all instance data are gitignored. No secrets belong in the shared base or public repository.

The writable policy includes cfg/configs directories, gamemodes_server.txt, metaplugins.ini, and common JSON/CFG/INI/TOML/YAML/TXT/database settings; gamedata, translations and .NET deps/runtimeconfig manifests remain centrally managed. Existing unknown binary data formats may need an explicit policy addition in runtime.mutable before migration. Centrally updated defaults do not overwrite existing private settings. To adopt a new config schema, deliberately migrate that instance's private file; deleting its private copy while stopped allows the next start to seed the new default. Shared binaries are refreshed and removed centrally, including disabled plugins; removing a plugin from central overlays removes its old shared link on restart. Existing shared defaults should be edited in a stopped maintenance window, not while the sidecar hashes/copies them.

## Host-editable instance folders

Default mounts use adjacent host directories, not opaque volumes for configuration:

```text
data/
  shared/                          # private central addon/resource overlay
  instances/
    server1/
      cfg -> installation/game/csgo/cfg
      addons -> installation/game/csgo/addons
      logs -> installation/game/csgo/logs
      installation/                # private directories + shared binary symlinks
      home/                        # private Steam user data
    server2/                       # same layout, separate files
    server3/
```

The three convenience links are relative and usable from the host as well as the container. They appear during the first successful tree preparation. You can stage files earlier under installation/game/csgo. Actual edit locations for server1:

| Purpose | Host path |
| --- | --- |
| CS2 cfg | data/instances/server1/cfg/server.cfg and on_boot.cfg |
| CSS administrators | data/instances/server1/addons/counterstrikesharp/configs/admins.json |
| CSS groups / permission overrides | same configs directory: admin_groups.json / admin_overrides.json |
| CSS core | same configs directory: core.json |
| Plugin configs / GameModeManager | same configs directory: plugins/<plugin>/<plugin>.json |
| Plugin-local data / SQLite | data/instances/server1/addons/counterstrikesharp/plugins/<plugin>/ (plugin-defined filename) |
| Disabled mode plugin data | same plugins directory: disabled/<plugin>/ |
| CSS logs | data/instances/server1/addons/counterstrikesharp/logs/ |
| CS2 logs | data/instances/server1/logs/ |

Some plugins choose another working-directory-relative path; those paths still resolve inside that instance's installation. No SQLite database is shared. Existing cfg/config files and imported data are **regular private copies, never hardlinks**; the convenience directories are relative symlinks, while immutable binary links point to /base and may look broken when inspected directly from the host. Do not replace binary links with edited DLLs in an instance: stage a trusted central binary update instead. The shared game install and coordination remain local Docker named volumes `cs2-multi_game` and `cs2-multi_control` by default (project name changes the prefix).

An optional private `data/admin-template/` can hold the three CSS admin JSONs. Explicitly copy selected files into each instance's configs directory when you want identical permissions; they remain independent copies afterwards. Never link or copy an active SQLite database as a shared permissions mechanism. Host editing may require sudo or a deliberate host ACL/group because runtime files belong to UID/GID 10001. Imported trees must be recursively owned by that runtime user before first launch. Both data/ and private/ are excluded from Git and the image build context; env files remain in private/serverN.env.

## Automatic update protocol

1. The single sidecar takes updater.lock for its lifetime and polls SteamCMD public branch build ID plus a SHA-256 of central mod/custom overlay contents, every CHECK_INTERVAL seconds (default 300).
2. `force` starts regardless of player count. `empty` requires fresh running status with 0 humans from **every** configured ID; missing/unreachable/auth failures/unparseable/stale status defer. Bots do not block. Players can still join between a status sample and stop; empty is a best-effort precondition, not admission control. Bootstrap and recovery of an already begun transaction always finish before serving games, even under empty.
3. The sidecar creates `/control/updating`. Each supervisor sends SIGTERM to its entire game process group, waits up to STOP_TIMEOUT (45s), then kills an unresponsive group. Supervisors hold shared game.lock leases throughout game lifetime; leases are inherited by game children too. Even an unresponsive supervisor cannot permit the updater to write: the exclusive lock waits for all holders.
4. The updater obtains the exclusive lock, removes its previously managed mod files, runs SteamCMD app_update 730 validate once, checks the success message and installed build ID, reapplies central mods/custom files, patches the Metamod search path and records version metadata.
5. Only after successful installation does it mark ready and clear the stop marker. Supervisors resume, refresh their links and use their own private configs/data.

SteamCMD metadata and installation commands run in dedicated process groups. Timeout (`STEAMCMD_TIMEOUT`, default 7200 seconds) and SIGTERM/SIGINT shutdown terminate/kill the group and reap adopted descendants before releasing updater/game locks. The instance installation root, its ancestors and destination parent directories must be real directories; symlinked roots/manifests and escaping stale manifest paths are rejected. Instance trees must be trusted and edited while stopped; this is not protection against concurrent hostile filesystem changes.

This is **not an atomic snapshot rollback**. Any exception or killed updater leaves the marker in place, and all games stay stopped until a later successful retry repairs/validates the base. Steam/build lookup errors before a transaction leave a running fleet untouched. Update latency can include Steam metadata/download time; a new build appearing during installation causes a build mismatch and a safe retry. There is no plugin/gameplay health gate or automatic rollback after restart. Keep consistent private backups of the entire shared base, central overlay, control and instance volumes before deployment and upgrades.

Recovery: inspect `docker compose logs updater`, repair network/disk/overlay errors, and restart **only updater** if needed; it retries automatically. Never delete the updating marker to force mixed files into service. To restore a backup, stop the whole Compose project, restore a consistent set of volumes/overlay and metadata from one known-good backup, then start it. `down --volumes` destroys persistent state and is only used for disposable tests.

## Operating limits

Only launch games via these supervisors. Do not run the old installer, -autoupdate, host SteamCMD, an old cron/timer, or a second Compose project against this base: writers outside the lock protocol invalidate its safety. A second sidecar using the same control volume exits rather than competing. The control volume is trusted writable IPC among these services, not a security boundary between hostile tenants. Containers initialize bind/volume roots as root then run game/updater as UID 10001. They do not mount the Docker socket, request privileged mode or mount overlay filesystems.

Workshop resources already staged in the shared installation are shared. New resources downloaded dynamically by an individual running server remain private, so Workshop caches may duplicate. Stage required common Workshop/maps/materials before migration for identical resources; the sidecar does not discover/synchronize per-server Workshop downloads. Independent configs may intentionally select different modes/maps, but the central binary/resource set is common. Published host UDP/TCP ports are 27015/27016/27017; RCON shares the TCP game port, so restrict TCP with your host/network firewall. A separate GSLT is required for each public server.

Framework/menu package updates are deliberately pinned/staged, not automatically fetched as GitHub latest. The automatic sidecar applies staged overlay changes as well as Steam updates. Historical maintenance source is retained in tools/legacy-maintenance but is not run by this Compose. The active .github/workflows/fleet.yml tests PRs with read-only permissions and publishes the Linux amd64 image only after validation succeeds on trusted default-branch commits or version tags whose commits belong to that branch. Only the publishing job has packages:write. Images carry source/license labels, latest (default branch), full sha-<commit> and semantic version tags. See [validation evidence](VALIDATION.md) for actual run and pull evidence. For a local build, use the verification commands below and set CS2_IMAGE=cs2-multi-local:latest when starting Compose.

## Verification commands

```sh
python3 -m unittest discover -s runtime -v
docker compose config --quiet
docker build -t cs2-multi-local:latest .
python3 runtime/docker_smoke.py
```

The Docker smoke test uses a separate random project and an explicit offline Steam/process fixture, clears secret-bearing environment values, removes published ports, and cleans up its own volumes. It uses disposable host bind instance directories and exercises real containers, mounts, supervisor locks, automatic update detection and failure/retry, not real CS2 gameplay.
