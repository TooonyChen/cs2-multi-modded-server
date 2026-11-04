# Changelog

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
