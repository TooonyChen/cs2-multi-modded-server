# Captured runtime limitations and follow-up

Independent review examined maintenance source at `c16191e4ce7fbfdae3a30fa7b3e770eb6bb8db71`. It passed the four existing helper tests and source checks and found no credential/publication blocker for a private historical operations repository. It did not verify production, remote artifacts, recovery, or end-to-end update safety. The maintenance executable files remain unchanged from that reviewed capture. Documentation corrections do not fix these runtime limitations.

## Health checks

`scheduled_update.py` searches whole response strings for `GameModeManager` and `LOADED`; it does not require that the manager's own entry is loaded. It submits `bot_add` and checks only that a subsequent status command responds. A rejected bot command or zero spawned bots can pass and clear the pending marker. Its `VERIFIED` log message is stronger than the evidence. This differs from the separately performed incident mode/bot tests recorded in maintenance/README.md.

Follow-up: parse the manager's own entry, verify a newly joined/spawned bot, preserve pending on failure, clean up test bot changes, and test failed/rejected cases. Empty-player checks reduce disruption but a player can join after the final check.

## Configuration ownership

Standard CSS config directories, Metamod metaplugins.ini and external cfg paths are excluded, but complete plugin subdirectories for InventorySimulator, MatchZy and FixRandomSpawn are accepted. Plugin-local settings/data supplied inside a future archive can overwrite operator files. Do not interpret the updater's captured docstring as a universal preservation guarantee. Preserve private config/data backups; follow-up needs explicit operator-owned paths informed by real package layouts.

## Interrupted updates and recovery

Downloads and validation complete before overlay writes. Normal Python write exceptions attempt restoration, but files are replaced individually and recovery metadata is written after mutation. Timeout, kill or host failure during writes can leave mixed versions and incomplete incremental recovery metadata. The startup failure message saying installed versions were retained is not reliable for this interruption case. Post-restart health failure does not roll back. Interruption between manifest completion and pending-marker creation can also lose the restart reminder.

Before manual recovery, stop the timer and any active service, stop/quiesce container and other writers, and bypass the startup updater. Incremental backups are not a substitute for a consistent full overlay/state/game backup. Overlay restoration may not remove files already copied into the installed game tree or undo SteamCMD/image changes. Recovery has not been exercised in isolation by this repository task.

Follow-up: durable recovery metadata before writes, interrupted-update detection/recovery, restart intent recorded with the transaction, and failure-injection tests before any deployment.

## Local paths and downloads

Archive member checks reject absolute and parent-traversal names; they do not defend destination writes against pre-existing symlink parents or predictable temporary-file symlinks. Overlay/state directories must be trusted and must not be concurrently edited. No unsafe production symlink was observed or checked by the review. Add destination-confinement/symlink-resistant writes before using untrusted writable directories.

SHA-256 verification occurs only when upstream release metadata supplies a digest. Gamedata is commit-addressed, without an independent recorded payload digest. Downloads lack expanded-size limits and redirect-host restrictions. Version provenance and conditional digest checking do not guarantee continued availability or reproducible rebuilds.

## Source evidence

`docs/deployed-baseline.json` records original source hashes at `db6f60a` (also unchanged at `c16191e`), not a promise that subsequently corrected Markdown has those hashes. Use `git show c16191e:<path>` to inspect the original capture. Binaries, live settings, backups and final human-client verification remain outside this source-review evidence.
