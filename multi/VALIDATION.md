# Validation evidence

Executed locally on 2026-11-04; no production service was accessed or restarted.

- Docker Engine 26.1.5, Linux amd64. Docker Compose v5.7.0 standalone binary was downloaded into the session scratch directory because the host had no Compose plugin.
- `docker build -f multi/Dockerfile -t cs2-multi-local:latest .` succeeded against Steam Runtime 4 (base digest sha256:954d06cebd63ba94a3fe1a7cca322fa3d59eac2fa59eb66cd17512733e641dd3).
- `docker compose -f multi/compose.yaml config --quiet` succeeded with private example env files created locally. No populated env file is tracked.
- `python3 -m unittest discover -s multi -v`: 7 tests passed. These cover three real supervisor subprocesses with real Linux flock and SIGTERM, stop-before-write, restart after success, failure marker retention, private configuration persistence, shared resource identity, old binary removal, source symlink escape refusal, conservative empty-player status, and private snapshot import preserving a 32-entry **fixture** mode list. This does not claim to have read the live mode configuration.
- Historical maintenance helper tests: 4 passed separately. Their captured runtime limitations remain documented; they are not enabled in the fleet.
- `COMPOSE=<standalone-compose> python3 multi/docker_smoke.py` ran an isolated real Compose project with updater + 3 server containers, using the explicitly labeled offline Steam/process fixture. It verified host bind cfg/addons shortcuts resolve correctly, admin/config files are regular independent copies with private settings preserved across updates, all server /base mounts reject writes, automatic build 1 bootstrap, automatic build 2 application, injected build 999 installation failure retaining the stop marker and stopping all 3 games, and automatic build 3 repair/restart. Disposable containers/networks/volumes were removed afterwards.
- A separate real SteamCMD container successfully self-updated, logged in anonymously, printed app 730 public branch build ID **26393695**, and exited 0. Only metadata was requested; no CS2 game installation was downloaded. The branch layout matches runtime.public_build parsing.

Not exercised: full ~game-sized Steam installation, CS2 engine behavior through the symlink tree, plugin ABI compatibility, Workshop client downloads, actual live snapshot import, production cutover/restore, human joining, bot spawn/map transitions in CS2, or Panorama rendering/clicks. The engine's executable is copied into each private tree specifically to preserve executable-relative paths, but real CS2 acceptance is still required. Host power-loss recovery was not fault-injected; the stop marker/journal are fsynced and the installation is synced before readers resume, but this is not a snapshot rollback implementation.

GitHub Actions is disabled on this fork. The authenticated OAuth token has repo scope but not workflow scope, and GitHub rejected adding the new active workflow. The checked-in multi/ci-template.yml is a template only; no remote CI success is claimed.

No claim is made that legacy framework/helper tests or a responding RCON status prove gameplay health. Independent review of the final commit should precede deployment; these local checks are implementation evidence, not production acceptance.
