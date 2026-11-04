# Match-end map-change ownership and regression

The published 0.1.2 public configuration has no automatic match-end owner: GMM `Rotation.Enabled=false`, GG1 `ChangeMapAfterVote=false`, `ChangeMapAfterWinDraw=false`, `ChangeMapAfterTimeLimit=false`, and `cfg/settings/map_voting.cfg` sets `mp_match_end_changelevel 0`. This is a statement about the public bundle, **not** the effective configuration of an existing private server. Existing instance configs survive materialization.

Production reportedly votes and changes maps during play. Its actual ownership flags and correlated ordinary match-end logs remain unknown. The pinned GG1 source proves a compatible immediate RTV path independent of automatic match-end ownership; successful voting does not identify production’s match-end owner. This public-default fix does not depend on production access and makes no claim about its effective settings.

## Pinned source evidence

All references below are the source revisions retained in `third_party/sources/` and recorded with SHA-256 in `docs/bundled-baseline.json`.

- [GMM RotationManager.cs, lines 29–32 and 67–70](https://github.com/nickj609/GameModeManager/blob/7b5d8fedba2eda147f2e3bdb0663fb59728c259f/GameModeManager/Core/RotationManager.cs#L29): parsing copies `Rotation.Enabled` into `RotationsEnabled`; the match win-panel handler invokes `TriggerRotation()`.
- [GMM ServerManager.cs, lines 207–254](https://github.com/nickj609/GameModeManager/blob/7b5d8fedba2eda147f2e3bdb0663fb59728c259f/GameModeManager/CrossCutting/ServerManager.cs#L207): `TriggerRotation()` immediately returns when rotations are disabled. `ModeRotation` separately gates changing to another mode. Otherwise the countdown calls `ChangeToNextMap()`, waits for any active GG1 vote, then uses GG1's chosen next map. An absent/unusable chooser falls back to a random map of the current mode. The in-progress guard prevents overlapping end triggers.
- [GMM TimeLimitManager.cs, lines 157–172](https://github.com/nickj609/GameModeManager/blob/7b5d8fedba2eda147f2e3bdb0663fb59728c259f/GameModeManager/Core/TimeLimitManager.cs#L157): the time-limit callback also invokes `TriggerRotation()`. This requires a scheduled/enabled timer; enabling rotation does not create a time limit in every mode.
- [GMM MapChooserBridge.cs, lines 572–575](https://github.com/nickj609/GameModeManager/blob/7b5d8fedba2eda147f2e3bdb0663fb59728c259f/GameModeManager/Core/MapChooserBridge.cs#L572): advancement issues `ggmc_change_nextmap`.
- [GG1 GG1MapChooser.cs, lines 3169–3185](https://github.com/ssypchenko/GG1MapChooser/blob/e70bf28bce522e7333dd506067b12e0ed7bcbcb0/GG1MapChooser.cs#L3169): that command uses the saved `_roundEndMap` winner, or random selection if none exists.
- [GG1 lines 3683–3686](https://github.com/ssypchenko/GG1MapChooser/blob/e70bf28bce522e7333dd506067b12e0ed7bcbcb0/GG1MapChooser.cs#L3683): vote completion stores the selected map and calls `DoMapChange` with the vote's requested change time.
- [GG1 lines 1219–1251](https://github.com/ssypchenko/GG1MapChooser/blob/e70bf28bce522e7333dd506067b12e0ed7bcbcb0/GG1MapChooser.cs#L1219): `ChangeMapTime_Now` starts a map change immediately, independent of `ChangeMapAfterVote`, win-panel ownership, and GMM rotation. `ChangeMapTime_MapEnd` stores the winner for later and may issue `nextlevel`; `nextlevel` alone does not establish an automatic change when engine changelevel is off.
- [GG1 lines 3940–3960](https://github.com/ssypchenko/GG1MapChooser/blob/e70bf28bce522e7333dd506067b12e0ed7bcbcb0/GG1MapChooser.cs#L3940): the successful RTV threshold starts a vote with `ChangeMapTime_Now`. Thus successful RTV can coexist with the public bundle's automatic match-end gap.
- [GG1 lines 685–724](https://github.com/ssypchenko/GG1MapChooser/blob/e70bf28bce522e7333dd506067b12e0ed7bcbcb0/GG1MapChooser.cs#L685): GG1's own win-panel handler is separately gated by `ChangeMapAfterWinDraw`.

## Ownership options and tradeoffs

The corrected public GMM-owned default enables `Rotation.Enabled` while leaving `ModeRotation`, `ModeSchedules`, `WhenServerEmpty` and `MapChooser.ModesInVotes` false. GG1 selects maps and handles immediate RTV; GMM decides when ordinary automatic advancement happens. This enables map rotation, not automatic mode cycling. It uses GMM's map countdown/hold path, so the existing unresolved movement-lock behavior still requires real engine/client acceptance.

A deliberate GG1-owned/private setup may instead keep GMM rotation disabled and enable the appropriate GG1 end triggers, or intentionally disable automatic advancement altogether. Do not overwrite such choices. The offline migration helper requires an explicit `--map-change-owner gmm` or `preserve` when saved rotation is false; the latter warns and preserves all ownership settings. It cannot determine effective GG1/engine state from a GMM JSON alone and does not mutate companion files.

The only gameplay configuration change from 0.1.2 is `Rotation.Enabled: false → true`. GG1 remains the map voter and immediate RTV handler; engine automatic changelevel stays disabled. Saved private configurations are preserved until an operator explicitly migrates them. No production change or engine acceptance is implied.

## Executable regression

Prepare the exact toolchain once with network access, then run the regression offline:

```sh
docker pull --platform linux/amd64 "$(python3 runtime/rotation_harness/run.py --image)"
python3 runtime/rotation_harness/run.py
```

The runner pins SDK **10.0.403** with roll-forward disabled and image `mcr.microsoft.com/dotnet/sdk@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b`. CI performs this separate pull, then executes Docker with `--pull=never --network=none`. It validates archive digests, compiles the unchanged complete GMM `ServerManager`, `RotationManager`, and `TimeLimitManager`, and extracts the actual GG1 command/change methods and GMM bridge command into a harness. Only external boundaries (engine commands, timers, localization, chooser lookup, map metadata) are stubbed. No network/NuGet package access is used during execution.

The test feeds actual bundled JSON into that code and asserts round-end/timed-end voted-winner advancement exactly once, waiting for an active vote, overlap suppression, retention of the current mode at the mode-rotation interval, disabled-rotation preservation, manual mode cfg/map execution, and immediate RTV-style changes with automatic rotation disabled. Before the fix, execution against 0.1.2 reproduced `round: voted winner did not advance exactly once`. The corrected packaged default passes all five scenarios. Explicit assertions also prevent automatic mode/empty/schedule cycling, modes in GG1 map votes, or competing bundled GG1/engine ownership from being enabled.

This is source-backed callback execution, not CS2 acceptance. It enters GG1 at vote completion, bypassing vote UI/tallying, and enters GMM's time-limit path through `EnableTimeLimit(1)`. It does not prove timer scheduling for every shipped mode, Panorama rendering, native hooks, movement recovery, real Workshop downloads, or synthetic mode-vote interception.

Before deployment acceptance, collect only allowlisted GMM rotation/MapChooser/Commands settings, GG1 ownership/vote flags, effective `mp_match_end_changelevel`, and a short correlated log around an ordinary non-RTV match-end vote, result and ensuing map command. Avoid admin identities, environment secrets and unrelated player data. Exercise both a round-limited and an enabled time-limited mode with a real client, then verify manual mode changes, immediate RTV and movement after transitions.
