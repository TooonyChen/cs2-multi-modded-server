#!/usr/bin/env python3
"""Hourly framework updates, applied only while no human players are present."""
import argparse
from pathlib import Path
import re
import subprocess
import time
import rcon
import updater

ROOT = Path('/opt/cs2-modded-server/custom_files')
STATE = Path('/var/lib/cs2-maintenance')


def humans(status):
    found = re.search(r'^players\s*:\s*(\d+) humans\b', status, re.M)
    return int(found.group(1)) if found else None


def main(check_only=False):
    try:
        count = humans(rcon.command('status'))
    except (OSError, RuntimeError) as exc:
        print('DEFER: server not ready:', type(exc).__name__)
        return
    if count != 0:
        print('DEFER: server busy or player count unknown:', count)
        return
    if check_only:
        print('CHECK_OK: server empty; no update or restart requested')
        return
    pending = STATE / 'restart-pending'
    if updater.update(ROOT, STATE):
        pending.write_text('Framework overlay changed; restart when empty.\n')
    if not pending.exists():
        return
    # Players may have joined while the assets downloaded. Keep changes staged.
    if humans(rcon.command('status')) != 0:
        print('DEFER: player joined; update remains staged')
        return
    subprocess.run(['docker', 'restart', '-t', '30', 'cs2-modded-server'], check=True, timeout=60)
    for attempt in range(36):
        time.sleep(5)
        try:
            meta = rcon.command('meta list')
            plugins = rcon.command('css_plugins list')
            if 'CounterStrikeSharp' in meta and 'GameModeManager' in plugins and 'LOADED' in plugins:
                # Exercise the player-spawn path that originally crashed, not only plugin loading.
                rcon.command('bot_add')
                time.sleep(3)
                rcon.command('status')
                pending.unlink(missing_ok=True)
                print('VERIFIED: framework, mode manager and bot-join smoke check passed')
                return
        except (OSError, RuntimeError):
            pass
    raise RuntimeError('Updated server did not pass framework health check; inspect logs and backup before retry')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    main(parser.parse_args().check_only)
