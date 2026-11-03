#!/usr/bin/env python3
"""Cooperative CS2 fleet. Linux flock is the authority; markers only request stops."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

BASE = Path(os.getenv('GAME_BASE', '/base'))
CONTROL = Path(os.getenv('CONTROL', '/control'))
STATE = Path(os.getenv('INSTANCE_STATE', '/instance'))
STOP = False


def mutable(path):
    s = path.as_posix()
    return ('/cfg/' in '/' + s or '/configs/' in '/' + s or
            path.name in ('gamemodes_server.txt', 'metaplugins.ini') or
            (path.suffix in ('.json', '.cfg', '.ini', '.toml', '.yaml', '.yml', '.txt', '.sqlite', '.db') and
             not any(x in s for x in ('/gamedata/', '/lang/')) and
             not path.name.endswith(('.deps.json', '.runtimeconfig.json'))))


def materialize(base, target):
    """Directory metadata is private; immutable files point at the RO base mount."""
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / '.shared-files.json'
    old = json.loads(manifest.read_text()) if manifest.exists() else []
    current = []
    for source in sorted(base.rglob('*')):
        rel = source.relative_to(base)
        if source.is_symlink():
            # Refuse links escaping the installation (including imported overlays).
            source.resolve().relative_to(base.resolve())
        dest = target / rel
        if source.is_dir():
            if dest.is_symlink():
                raise RuntimeError('Instance directory is a symlink: ' + str(rel))
            dest.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            if rel.as_posix() == 'game/bin/linuxsteamrt64/cs2':
                if dest.is_symlink(): dest.unlink()
                shutil.copy2(source, dest)
            elif mutable(rel):
                if dest.is_symlink():
                    dest.unlink()
                if not dest.exists():
                    shutil.copy2(source, dest)
            else:
                if dest.is_dir():
                    raise RuntimeError('Binary destination is a directory: ' + str(rel))
                if dest.exists() or dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(source.absolute())
                current.append(rel.as_posix())
    for name in set(old) - set(current):
        dest = target / name
        if dest.is_symlink():
            dest.unlink()
    manifest.write_text(json.dumps(current))


@contextlib.contextmanager
def lock(name, exclusive=True, nonblock=False):
    CONTROL.mkdir(parents=True, exist_ok=True)
    with (CONTROL/name).open('a+') as handle:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle, mode | (fcntl.LOCK_NB if nonblock else 0))
        yield handle


def sync_directory(path):
    fd = os.open(path, os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def atomic(path, data):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as handle:
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    sync_directory(path.parent)


def stop_child(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=int(os.getenv('STOP_TIMEOUT', '45')))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    # Child process groups must be gone before releasing the base lock.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def player_count(text):
    match = re.search(r'players\s*:\s*(\d+)\s+humans?\b', text, re.I)
    return int(match[1]) if match else None


def status(child):
    players = None
    try:
        from rcon_client import command
        players = player_count(command('status', os.environ['RCON_PASSWORD']))
    except Exception:
        pass  # Unknown is deliberately not zero.
    atomic(CONTROL/(os.environ['INSTANCE_ID'] + '.json'),
           {'time': time.time(), 'players': players, 'running': child.poll() is None})


def server():
    global STOP
    signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__('STOP', True))
    signal.signal(signal.SIGINT, lambda *_: globals().__setitem__('STOP', True))
    while not STOP:
        if (CONTROL/'updating').exists() or not (BASE/'.ready').exists():
            time.sleep(1)
            continue
        with lock('game.lock', exclusive=False) as lease:
            if (CONTROL/'updating').exists():
                continue
            game = STATE/'installation'
            materialize(BASE, game)
            for name in ('cfg', 'addons', 'logs'):
                actual = game/'game/csgo'/name
                actual.mkdir(parents=True, exist_ok=True)
                shortcut = STATE/name
                if not shortcut.exists() and not shortcut.is_symlink():
                    shortcut.symlink_to(Path('installation/game/csgo')/name, target_is_directory=True)
            home = STATE/'home'; home.mkdir(parents=True, exist_ok=True)
            sdk = home/'.steam/sdk64'; sdk.mkdir(parents=True, exist_ok=True)
            client = BASE/'steamclient.so'
            if client.exists():
                link = sdk/'steamclient.so'
                if link.is_symlink() or link.exists(): link.unlink()
                link.symlink_to(client)
            args = ['./game/bin/linuxsteamrt64/cs2', '-dedicated', '-console', '-usercon',
                    '-disable_workshop_command_filtering', '-port', '27015',
                    '+map', os.getenv('MAP', 'de_dust2'), '+exec', os.getenv('EXEC', 'on_boot.cfg')]
            for key, flag in [('STEAM_ACCOUNT', '+sv_setsteamaccount'), ('RCON_PASSWORD', '+rcon_password'),
                              ('SERVER_PASSWORD', '+sv_password'), ('MAXPLAYERS', '+sv_visiblemaxplayers'),
                              ('GAME_TYPE', '+game_type'), ('GAME_MODE', '+game_mode')]:
                if os.getenv(key): args += [flag, os.environ[key]]
            if os.getenv('TEST_COMMAND'):
                args = json.loads(os.environ['TEST_COMMAND'])
            env = dict(os.environ, HOME=str(home))
            env['LD_LIBRARY_PATH'] = ':'.join(str(game/p) for p in (
                'game/bin/linuxsteamrt64', 'game/csgo/bin/linuxsteamrt64'))
            child = subprocess.Popen(args, cwd=game, env=env, start_new_session=True, pass_fds=(lease.fileno(),))
            try:
                next_status = 0
                while child.poll() is None and not STOP and not (CONTROL/'updating').exists():
                    if time.monotonic() >= next_status:
                        status(child); next_status = time.monotonic() + 5
                    time.sleep(.2)
            finally:
                stop_child(child)
                atomic(CONTROL/(os.environ['INSTANCE_ID'] + '.json'),
                       {'time': time.time(), 'players': None, 'running': False})
        time.sleep(1)


def all_empty(ids, now=None):
    now = now or time.time()
    if not ids: return False
    for name in ids:
        try:
            data = json.loads((CONTROL/(name+'.json')).read_text())
            if not data['running'] or data['players'] != 0 or not 0 <= now-data['time'] < 20:
                return False
        except (OSError, KeyError, ValueError):
            return False
    return True


def transaction(apply):
    # A killed updater leaves the marker and keeps the fleet stopped until a retry succeeds.
    (CONTROL/'updating').touch()
    sync_directory(CONTROL)
    with lock('game.lock'):
        apply()
        (BASE/'.ready').touch()
        # Flush shared installation data before durably admitting new readers.
        os.sync()
        (CONTROL/'updating').unlink()
        sync_directory(CONTROL)


def steam(*args):
    result = subprocess.run([os.getenv('STEAMCMD', '/steamcmd/steamcmd.sh'), *args, '+quit'],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=7200)
    if result.returncode: raise RuntimeError('SteamCMD failed; fleet remains stopped')
    return result.stdout


def public_build(text):
    match = re.search(r'"public"\s*\{\s*"buildid"\s*"(\d+)"', text)
    if not match: raise RuntimeError('Cannot determine Steam public build ID')
    return match[1]


def mods_digest():
    digest = hashlib.sha256()
    for folder in ('/mods', '/custom'):
        root = Path(folder)
        for path in sorted(root.rglob('*')):
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def install(expected, digest):
    # Journal old AND planned paths before mutation, so interrupted copies are repaired on retry.
    previous = BASE/'.mod-files.json'
    old = json.loads(previous.read_text()) if previous.exists() else []
    sources = {}
    for folder in ('/mods', '/custom'):
        src = Path(folder)
        for path in sorted(src.rglob('*')):
            if path.is_symlink(): raise RuntimeError('Shared overlay must not contain symlinks')
            if path.is_file():
                sources[(Path('game/csgo')/path.relative_to(src)).as_posix()] = path
    journal = sorted(set(old) | set(sources))
    for name in journal:
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or not name.startswith('game/csgo/'):
            raise RuntimeError('Invalid overlay journal path')
    atomic(previous, journal)
    # Remove overlays before validation so Steam restores shadowed stock paths.
    for name in journal:
        dest = BASE/name
        if dest.is_symlink() or dest.is_file(): dest.unlink()
    output = steam('+force_install_dir', str(BASE), '+login', 'anonymous', '+app_update', '730', 'validate')
    if "Success! App '730' fully installed" not in output:
        raise RuntimeError('Steam did not confirm a complete installation')
    manifest = (BASE/'steamapps/appmanifest_730.acf').read_text()
    if not re.search(r'"buildid"\s*"' + re.escape(expected) + '"', manifest):
        raise RuntimeError('Installed build does not match checked build; retry required')
    # CS2 also resolves runtime libraries in csgo/bin on recent releases.
    libdir = BASE/'game/csgo/bin/linuxsteamrt64'
    libdir.mkdir(parents=True, exist_ok=True)
    for library in (BASE/'game/bin/linuxsteamrt64').glob('*.so'):
        shutil.copy2(library, libdir/library.name)
    for name, source in sources.items():
        dest = BASE/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    atomic(previous, sorted(sources))
    gi = BASE/'game/csgo/gameinfo.gi'
    text = gi.read_text()
    if not re.search(r'^\s*Game\s+csgo/addons/metamod\s*$', text, re.M):
        text, n = re.subn(r'(^\s*Game_LowViolence[^\n]*\n)',
                          r'\1\t\t\tGame csgo/addons/metamod\n', text, count=1, flags=re.M)
        if not n: raise RuntimeError('Metamod search path patch failed')
        gi.write_text(text)
    shutil.copy2(Path(os.getenv('STEAMCMD', '/steamcmd/steamcmd.sh')).parent/'linux64/steamclient.so', BASE/'steamclient.so')
    atomic(BASE/'.version.json', {'build': expected, 'mods': digest})


def updater():
    policy = os.getenv('UPDATE_POLICY', 'force')
    if policy not in ('force', 'empty'): raise ValueError('UPDATE_POLICY must be force or empty')
    ids = os.getenv('INSTANCE_IDS', 'server1 server2 server3').split()
    with lock('updater.lock', nonblock=True):
        while True:
            try:
                wanted = public_build(steam('+login', 'anonymous', '+app_info_update', '1', '+app_info_print', '730'))
                digest = mods_digest()
                current = json.loads((BASE/'.version.json').read_text()) if (BASE/'.version.json').exists() else {}
                needs = current != {'build': wanted, 'mods': digest} or (CONTROL/'updating').exists()
                if needs:
                    bootstrap = not (BASE/'.ready').exists()
                    if bootstrap or (CONTROL/'updating').exists() or policy == 'force' or all_empty(ids):
                        print('Quiescing all instances for shared update', flush=True)
                        transaction(lambda: install(wanted, digest))
                        print('Shared installation ready', flush=True)
                    else:
                        print('Update deferred: not every instance is confirmed empty', flush=True)
            except Exception as exc:
                print(type(exc).__name__ + ': ' + str(exc), flush=True)
            time.sleep(max(5, int(os.getenv('CHECK_INTERVAL', '300'))))


if __name__ == '__main__':
    {'server': server, 'updater': updater}[sys.argv[1]]()
