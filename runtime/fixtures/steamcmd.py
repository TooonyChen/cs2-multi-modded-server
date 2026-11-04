#!/usr/bin/env python3
"""Offline Steam protocol fixture. This is NOT Steam or a CS2 game server."""
import os
from pathlib import Path
import sys

version = Path(os.environ['FIXTURE_BUILD']).read_text().strip()
if '+app_info_print' in sys.argv:
    print('"branches" { "public" { "buildid" "' + version + '" } }')
elif '+app_update' in sys.argv:
    if version == '999': raise SystemExit('Injected install failure')
    base = Path(sys.argv[sys.argv.index('+force_install_dir')+1])
    (base/'steamapps').mkdir(parents=True, exist_ok=True)
    (base/'steamapps/appmanifest_730.acf').write_text('"buildid" "' + version + '"')
    exe = base/'game/bin/linuxsteamrt64/cs2'
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text('''#!/usr/bin/env python3
import os, pathlib, signal, time
p = pathlib.Path('/instance/running')
p.write_text(str(os.getpid()))
try:
    pathlib.Path('/base/SHOULD-NOT-WRITE').write_text('unsafe')
    raise RuntimeError('base writable from server')
except PermissionError: pass
except OSError as e:
    if e.errno != 30: raise
pathlib.Path('/instance/ro-verified').touch()
def stop(*a):
    p.unlink(missing_ok=True)
    raise SystemExit
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(.1)
''')
    exe.chmod(0o755)
    csgo = base/'game/csgo'; csgo.mkdir(parents=True, exist_ok=True)
    (csgo/'gameinfo.gi').write_text('Game_LowViolence csgo_lv // fixture\n')
    (csgo/'fixture.vpk').write_text(version)
    print("Success! App '730' fully installed.")
else:
    raise SystemExit('Unexpected fixture call')
