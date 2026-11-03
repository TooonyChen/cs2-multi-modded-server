#!/bin/bash
set -eu
# Patch only the update hook in a runtime copy of the image's original launcher.
# SteamCMD finishes first; framework updates then run before mods are copied.
python3 - <<'PY'
from pathlib import Path
source = Path('/home/cs2-modded-server/install_docker.sh').read_text()
anchor = 'echo "Installing mods"'
if source.count(anchor) != 1:
    raise SystemExit('Original launcher changed; refusing to insert an ambiguous update hook')
hook = '''if ! timeout 150 python3 /home/maintenance/updater.py --root /home/custom_files --state /home/maintenance-state; then
    echo '[CS2 maintenance] Release check failed; retaining installed versions.' >&2
fi
'''
Path('/home/maintenance-state/install-runtime.sh').write_text(source.replace(anchor, hook + anchor, 1))
PY
exec bash /home/maintenance-state/install-runtime.sh
