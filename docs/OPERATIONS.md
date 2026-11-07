# Fleet architecture and operations

The default image is `ghcr.io/tooonychen/cs2-multi-modded-server:0.1.1` for Linux amd64. Run `docker compose pull` followed by `docker compose up -d`; no local build or registry login is required for the public package. The default is pinned to release `0.1.1`; optionally set `CS2_IMAGE` to another release, a SHA tag or a digest. The image contains the runtime and SteamCMD, while CS2 is installed into the shared volume on first boot. Valve/Steam terms apply to downloaded game content. The source remains LGPL-3.0.

Use one project with `docker compose ...`. A service can be copied for any N; do not share an INSTANCE_ID or instance directory. Add every service ID to updater.INSTANCE_IDS for the empty policy. Docker named volumes must live on a local Linux filesystem with working flock; NFS/CIFS/distributed mounts are not supported by this implementation.

The updater alone mounts `game:/base` read-write. Servers mount the same volume read-only and build private directory trees under `/instance/installation`. Their resource/plugin files are symlinks into `/base`, so VPKs, DLLs, native libraries and gamedata are one shared copy. The small CS2 executable is copied on each start so executable-relative engine paths resolve into that instance tree. CounterStrikeSharp's `addons/counterstrikesharp/api/` is also a real per-instance copy (a few MB), refreshed when the shared files change: managed CSS takes its plugins, shared, configs and admin root from that directory's resolved location, and the .NET host resolves symlinks there, so a linked `api/` would make every instance load plugins and settings from `/base`. Configs and plugin settings are seeded once as regular private files. All newly generated data, logs, demos and plugin files live in private directories. HOME/Steam user data is also per instance. Central mod overlay files are mounted from `game/csgo` and `data/shared`; the latter and all instance data are gitignored. No secrets belong in the shared base or public repository.

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
      instance.json, overlay/      # optional per-instance plugin set (see below)
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

## Per-instance plugin sets

By default every instance links the same shared plugin set and differs only in its private configuration. An instance that runs a different kind of game (for example a prop hunt server that must not load GameModeManager or Player Model Manager) can drop shared paths and add its own files. Both inputs live in the instance directory and are read by the supervisor on every start, so the result survives updates and restarts:

```text
data/instances/prophunt/
  instance.json          # optional: shared paths this instance does not use
  overlay/               # optional: private files, laid out like game/csgo
    addons/counterstrikesharp/plugins/<Plugin>/...
    addons/counterstrikesharp/configs/plugins/<Plugin>/<Plugin>.json
    cfg/prophunt.cfg
```

`instance.json` accepts one key. Each entry is a path relative to `game/csgo` and covers that file or directory and everything below it:

```json
{
  "exclude": [
    "addons/counterstrikesharp/plugins/GameModeManager",
    "addons/counterstrikesharp/shared/GameModeManager.Shared"
  ]
}
```

Unknown keys, absolute paths and `..` are rejected and the server does not start, so a typo cannot silently load the full shared set. An entry that matches no shared path is reported in the server log. Excluded shared links are removed from the instance tree and empty directories they leave are deleted. Private files are never deleted: seeded settings and plugin data under an excluded path stay where they are. Excluding a plugin does not exclude its dependencies; list each shared API directory, Metamod VDF or gamedata file the other servers still need but this one must not load.

The overlay is applied after the shared files and after exclusion, so it wins at any path, including inside an excluded directory. Binaries and resources are linked with relative links, which also resolve from the host. Settings that the runtime treats as mutable (cfg, configs, JSON and similar) are copied as regular private files. Such a copy is replaced when the overlay file changes; live edits made inside the instance survive restarts while the overlay file stays the same. Removing an overlay binary restores the shared file at that path, if any, on the next start. Removing an overlay setting leaves the live copy in place, like any other seeded setting. The overlay must be a real directory and must not contain symlinks.

Exclusion works because each instance has its own CSS root (see the copied `api/` above): CSS scans this instance's `plugins/` and `shared/`, not `/base`. Overlay files under `addons/counterstrikesharp/api/` are copied, never linked. Overlay and exclusion changes take effect when that server restarts (`docker compose restart prophunt`). They do not trigger the updater, and other instances never see them. Overlay files are not part of the central mod digest; stage changes while the server is stopped. The entrypoint gives `instance.json` and `overlay/` to UID/GID 10001 before dropping privileges, so files created by root or with a private umask still work. Directories the runtime creates are always mode 0755.

A different-mode server is a normal Compose service. Give it its own `INSTANCE_ID`, env file, instance directory and host ports, and add its ID to updater `INSTANCE_IDS`. It shares the downloaded game with the rest of the fleet, so it also stops and restarts with every fleet update.

### Upgrading an instance from v0.1.3: CSS configs become per instance

Before this change `api/` was linked, so managed CounterStrikeSharp resolved its root to `/base`. Each instance loaded the complete shared plugin set and read `configs/` (admins, groups, overrides, plugin settings) and plugin-local settings from the shared tree, including files staged through `data/shared`. The seeded instance copies of those files were not in effect, although native CSS read `configs/core.json` from the instance.

On the first start with this release, an instance whose previous tree linked `api/` adopts the shared files it was actually using: each mutable file under `addons/counterstrikesharp` whose instance copy differs from `/base` is replaced by the shared version, and the previous instance copy is saved under `installation/.css-root-migration/`. Each file is logged and listed in `installation/.css-root-migration.json`; the migration runs once. Excluded paths are not touched. Afterwards the instance files are authoritative: edit admins in `data/instances/<id>/addons/counterstrikesharp/configs/` and reload with `css_admins_reload`. A copy staged in `data/shared` only seeds new instances. Review the migration log, especially `core.json`, before relying on settings you previously edited in the instance tree.

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

Workshop resources already staged in the shared installation are shared. New resources downloaded dynamically by an individual running server remain private, so Workshop caches may duplicate. Every `steamapps/workshop` tree, and everything under `game/bin/linuxsteamrt64/steamapps` where CS2 keeps its Workshop downloads, belongs to the instance: it is never linked to the read-only base, links left there by earlier releases are removed, and the directory is created writable on every start. Stage required common Workshop/maps/materials before migration for identical resources; the sidecar does not discover/synchronize per-server Workshop downloads. Independent configs may intentionally select different modes/maps. The central binary/resource set is common unless an instance narrows or extends it with a [per-instance plugin set](#per-instance-plugin-sets). Published host UDP/TCP ports are 27015/27016/27017; RCON shares the TCP game port, so restrict TCP with your host/network firewall. A separate GSLT is required for each public server.

Framework/menu package updates are deliberately pinned/staged, not automatically fetched as GitHub latest. The automatic sidecar applies staged overlay changes as well as Steam updates. Historical maintenance source is retained in tools/legacy-maintenance but is not run by this Compose. The active .github/workflows/fleet.yml tests PRs with read-only permissions and publishes the Linux amd64 image only after validation succeeds on trusted default-branch commits or version tags whose commits belong to that branch. Only the publishing job has packages:write. Images carry source/license labels, latest (default branch), full sha-<commit> and semantic version tags. See [validation evidence](VALIDATION.md) for actual run and pull evidence. For a local build, use the verification commands below and set CS2_IMAGE=cs2-multi-local:latest when starting Compose.

## Verification commands

```sh
python3 -m unittest discover -s runtime -v
docker compose config --quiet
docker build -t cs2-multi-local:latest .
python3 runtime/docker_smoke.py
```

The Docker smoke test uses a separate random project and an explicit offline Steam/process fixture, clears secret-bearing environment values, removes published ports, and cleans up its own volumes. It uses disposable host bind instance directories and exercises real containers, mounts, supervisor locks, automatic update detection and failure/retry, not real CS2 gameplay.
