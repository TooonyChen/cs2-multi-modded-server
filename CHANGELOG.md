# Changelog

## Unreleased

- Each instance can choose its own plugin set. `data/instances/<id>/instance.json` lists shared paths (relative to `game/csgo`) that the instance does not link, and `data/instances/<id>/overlay/` adds private files laid out like `game/csgo`. The supervisor applies both on every start, so excluded plugins stay out after restarts and updates, and stale links are removed. Overlay files win over shared files; overlay settings are copied and re-copied only when the overlay file changes. Invalid paths, unknown keys and symlinks in the overlay stop the server.
- CS2 Workshop and addon download caches (`steamapps/workshop` and `game/bin/linuxsteamrt64/steamapps`) are always private, writable instance directories. Links into the read-only base left there by earlier releases are removed on start.
- Managed CounterStrikeSharp now resolves its root inside each instance. `addons/counterstrikesharp/api/` is copied per instance instead of linked, because the .NET host resolves symlinks on `CounterStrikeSharp.API.dll` and CSS derives its plugins, shared, configs and admin paths from that location. Previously every instance scanned `/base` for plugins and read admins/plugin settings from `/base`, so per-instance plugin sets could not work and instance admin JSONs were not in effect. `runtime/css_root_harness` reproduces this through the hostfxr calls CSS makes and runs in CI.
- On upgrade, an instance that ran with a linked `api/` adopts the shared CSS settings it was actually using once, keeping its previous copies under `installation/.css-root-migration/`. See [the upgrade note](docs/OPERATIONS.md#upgrading-an-instance-from-v013-css-configs-become-per-instance).
- Directories created by the runtime are mode 0755 regardless of umask. The entrypoint hands `instance.json` and `overlay/` to UID/GID 10001 before starting the server.
- Tests cover exclusion across restarts, overlay precedence, instance isolation, path confinement, the Workshop cache and umask handling. The Docker smoke runs one server with its own plugin set from 0700 operator files.

## v0.1.3 — 2026-11-04

- Public GameModeManager now sets `Rotation.Enabled=true`, so GMM owns ordinary match-end map advancement. `ModeRotation`, `ModeSchedules`, `WhenServerEmpty` and `MapChooser.ModesInVotes` stay false. GG1 remains the map voter and immediate RTV handler. GG1 automatic end triggers and engine `mp_match_end_changelevel` stay disabled. Plugin binaries are unchanged from v0.1.2; only that bundled JSON default changes.
- Saved schema 12 or 13 files with `Rotation.Enabled=false` are not overwritten. `scripts/migrate-menu-config.py` requires `--map-change-owner gmm` or `--map-change-owner preserve`. `gmm` sets only `Rotation.Enabled` after the operator disables competing GG1 and engine automatic changes. `preserve` keeps the saved choice and warns; it does not prove an owner exists. Immediate RTV success is not evidence of match-end ownership.
- CI runs the source-backed C# regression against pinned GMM/GG1 sources and SDK 10.0.403 image `mcr.microsoft.com/dotnet/sdk@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b`, with execution offline. It covers five callback scenarios. It does not run CS2.
- Pin Compose and the deployment guide to image `0.1.3`. Update the checkout as well as the image because mods are host-mounted. Fleet runtime source is unchanged from v0.1.2; a rebuilt image can still have a new digest because the base tag moves. No production or staging change is part of this release.

## v0.1.2 — 2026-11-04

- Upgrade GameModeManager 1.0.62 to official 2.0.0 with PanoramaMenuManager/MenuManagerApi 1.3.01, GG1MapChooser/ggmcAPI 1.8.1 and PMM_GG1MapChooser 0.1.0. Disable the old WASDMenuAPI autoload and provide an offline schema-12 → 13 migration helper. `!modes` opens the mode menu.
- Upgrade CounterStrikeSharp 1.0.379 to official CI 1.0.380-1 with matching native/API artifacts. Retain Metamod 2.0.0-git1483 and MultiAddonManager 1.7.3; add its official autoload VDF and menu Workshop addon `3831211166`, preserving `3461824328`.
- Upgrade RetakesAllocator 2.4.2 to official CI 2.4.3, install pinned gamedata in both lookup locations and disable optional CanAcquire/weapon-paints hooks. Standard allocation remains; allocator-specific weapon paints integration is omitted. Signature auto-update is disabled.
- Include all six unmodified official FixRandomSpawn 1.2.0 package files. It enables `mp_randomspawn=1` across modes and needs mode-specific acceptance. Upstream license metadata is unknown; inclusion was explicitly approved by the maintainer and does not establish a license grant.
- Preserve all 34 public modes, correcting Linux filename case for Casual (1.6) and its settings execs. Seed fresh CSS administrator configuration with `{}`; preserve existing private configuration. Retain MatchZy 0.9.2, InventorySimulator 3.7.2 and public ServerListPlayersFix 2.1.
- Add exact update pins, package/file digests, corresponding source archives, third-party notices and nine bundle regression tests. Pin Compose and deployment examples to image `0.1.2`.

Update the repository checkout as well as the image: the mod bundle is host-mounted, not baked into the runtime image. Existing saved settings require deliberate migration; follow [bundled fixes and migration](docs/BUNDLED-FIXES.md). Fleet runtime behavior is unchanged by this release's resource upgrade.

Validation includes 21 runtime/bundle tests, four historical helper tests and real Docker/Compose coordination smoke with an offline Steam/process fixture. Hosted publication and anonymous image provenance are recorded in the [release notes](https://github.com/TooonyChen/cs2-multi-modded-server/releases/tag/v0.1.2). These checks do not run CS2. Native/plugin compatibility, bot spawn/round/map transitions, Workshop download, human joining, menu rendering/clicks and movement need acceptance on a real empty server. The original movement-lock defect remains unresolved; the rejected experimental patch is excluded. No production change, migration or restore acceptance is included.

## v0.1.1

Root repository layout and English deployment guide; runtime source and bundled resources unchanged from v0.1.0.

## v0.1.0

Initial public multi-instance runtime and GHCR release.
