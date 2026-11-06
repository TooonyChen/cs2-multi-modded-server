#!/usr/bin/env python3
"""Cooperative CS2 fleet. Linux flock is the authority; markers only request stops."""
import contextlib
import ctypes
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


# Paths below are relative to an instance installation root.
MODS_ROOT = Path('game/csgo')
EXECUTABLE = Path('game/bin/linuxsteamrt64/cs2')
# CS2 stores dynamically downloaded Workshop maps/addons next to its executable.
WORKSHOP = Path('game/bin/linuxsteamrt64/steamapps/workshop')
RESERVED = ('.shared-files.json', '.overlay-files.json')


def instance_cache(rel):
    """Steam download caches are written by the running game, so they stay per instance."""
    return 'steamapps' in rel.parts[1:] or rel.parts[:2] == ('steamapps', 'workshop')


def relative_entry(name, what):
    rel = Path(name)
    if not str(name) or rel.is_absolute() or '..' in rel.parts or rel == Path('.'):
        raise RuntimeError('Invalid ' + what + ' path: ' + str(name))
    return rel


def ensure_dir(path):
    """Create missing directories readable by the runtime user, whatever the umask."""
    missing = []
    while not path.exists() and not path.is_symlink():
        missing.append(path); path = path.parent
    for item in reversed(missing):
        item.mkdir()
        os.chmod(item, 0o755)
    if missing: path = missing[0]
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError('Expected a real directory: ' + str(path))


def instance_config(state):
    """Optional instance.json: {"exclude": ["addons/...", ...]} relative to game/csgo."""
    path = state/'instance.json'
    if path.is_symlink():
        raise RuntimeError('instance.json must not be a symlink')
    if not path.exists():
        return {'exclude': []}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or set(data) - {'exclude'}:
        raise RuntimeError('instance.json must be an object whose only key is "exclude"')
    exclude = data.get('exclude', [])
    if not isinstance(exclude, list) or not all(isinstance(x, str) for x in exclude):
        raise RuntimeError('instance.json "exclude" must be a list of paths')
    for name in exclude: relative_entry(name, 'instance.json exclude')
    return {'exclude': exclude}


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(base, target, exclude=(), overlay=None):
    """Directory metadata is private; immutable files point at the RO base mount.

    `exclude` drops shared paths (relative to game/csgo) from this instance only.
    `overlay` is a private tree mirroring game/csgo, applied over the shared files.
    """
    target = target.absolute()
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise RuntimeError('Instance root or ancestor is a symlink: ' + str(target))
    ensure_dir(target)
    def destination(name):
        rel = relative_entry(name, 'shared manifest')
        dest = target / rel
        if any(p.is_symlink() for p in dest.parents if p != target and target in p.parents):
            raise RuntimeError('Instance parent directory is a symlink: ' + str(rel))
        return dest
    def record(name):
        path = target/name
        if path.is_symlink():
            raise RuntimeError('Instance manifest is a symlink: ' + name)
        return json.loads(path.read_text()) if path.exists() else None
    old = record('.shared-files.json') or []
    applied = record('.overlay-files.json') or {}
    # Validate cleanup paths before performing any writes, including stale links.
    for name in old: destination(name)
    for name in applied: destination(name)
    excluded = [MODS_ROOT/relative_entry(x, 'exclude') for x in exclude]
    matched = set()
    def is_excluded(rel):
        hits = [e for e in excluded if e == rel or e in rel.parents]
        matched.update(hits)
        return bool(hits)

    # Build the complete plan first; overlay entries replace shared ones.
    plan = {}
    for source in sorted(base.rglob('*')):
        rel = source.relative_to(base)
        if rel.as_posix() in RESERVED:
            raise RuntimeError('Shared base contains reserved instance manifest')
        if source.is_symlink():
            # Refuse links escaping the installation (including imported overlays).
            source.resolve().relative_to(base.resolve())
        if instance_cache(rel) or is_excluded(rel):
            continue
        if source.is_dir():
            plan[rel] = ('dir', source)
        elif source.is_file():
            if rel == EXECUTABLE: plan[rel] = ('exe', source)
            elif mutable(rel): plan[rel] = ('seed', source)
            else: plan[rel] = ('link', source)
    for name in sorted(set(map(str, excluded)) - set(map(str, matched))):
        print('instance.json exclude matches no shared path: ' + str(Path(name).relative_to(MODS_ROOT)), flush=True)
    if overlay is not None and (overlay.exists() or overlay.is_symlink()):
        if overlay.is_symlink() or not overlay.is_dir():
            raise RuntimeError('Instance overlay must be a real directory: ' + str(overlay))
        for source in sorted(overlay.rglob('*')):
            if source.is_symlink():
                raise RuntimeError('Instance overlay must not contain symlinks: ' + str(source))
            if not source.is_dir() and not source.is_file():
                continue
            rel = MODS_ROOT/source.relative_to(overlay)
            kind = 'dir' if source.is_dir() else ('copy' if mutable(rel) else 'overlay-link')
            if rel in plan and (plan[rel][0] == 'dir') != (kind == 'dir'):
                raise RuntimeError('Instance overlay changes a file into a directory or back: ' + str(rel))
            plan[rel] = (kind, source)
    # Every planned entry needs real parent directories; the Workshop cache always exists.
    for folder in {*(p for rel in plan for p in rel.parents), WORKSHOP} - {Path('.')}:
        if plan.setdefault(folder, ('dir', None))[0] != 'dir':
            raise RuntimeError('Planned file is also a parent directory: ' + str(folder))

    current, copies = [], {}
    for rel in sorted(plan):
        kind, source = plan[rel]
        dest = destination(rel)
        if kind == 'dir':
            if dest.is_symlink():
                raise RuntimeError('Instance directory is a symlink: ' + str(rel))
            ensure_dir(dest)
            continue
        if dest.is_dir() and not dest.is_symlink():
            raise RuntimeError('File destination is a directory: ' + str(rel))
        if kind == 'exe':
            if dest.is_symlink(): dest.unlink()
            shutil.copy2(source, dest)
        elif kind == 'seed':
            if dest.is_symlink():
                dest.unlink()
            if not dest.exists():
                shutil.copy2(source, dest)
        elif kind == 'copy':
            # Re-copy only when the overlay itself changed, so live edits survive restarts.
            digest = digest_file(source)
            if dest.is_symlink() or not dest.exists() or applied.get(rel.as_posix()) != digest:
                if dest.is_symlink(): dest.unlink()
                shutil.copy2(source, dest)
            copies[rel.as_posix()] = digest
        else:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            if kind == 'link':
                dest.symlink_to(source.absolute())
            else:  # Relative, so overlay links also resolve from the host.
                dest.symlink_to(os.path.relpath(source.absolute(), dest.parent))
            current.append(rel.as_posix())
    for name in set(old) - set(current):
        dest = destination(name)
        if dest.is_symlink():
            dest.unlink()
    # Leave no empty plugin directories behind; never delete files.
    for entry in excluded:
        top = destination(entry)
        if top.is_symlink() or not top.is_dir(): continue
        for root, _, _ in os.walk(top, topdown=False):
            path = Path(root)
            if path.relative_to(target) not in plan and not any(path.iterdir()):
                path.rmdir()
    (target/'.shared-files.json').write_text(json.dumps(current))
    (target/'.overlay-files.json').write_text(json.dumps(copies))


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
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try:
            child.wait(timeout=float(os.getenv('STOP_TIMEOUT', '45')))
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
            config = instance_config(STATE)
            materialize(BASE, game, exclude=config['exclude'], overlay=STATE/'overlay')
            for name in ('cfg', 'addons', 'logs'):
                actual = game/'game/csgo'/name
                ensure_dir(actual)
                shortcut = STATE/name
                if not shortcut.exists() and not shortcut.is_symlink():
                    shortcut.symlink_to(Path('installation/game/csgo')/name, target_is_directory=True)
            home = STATE/'home'; ensure_dir(home)
            sdk = home/'.steam/sdk64'; ensure_dir(sdk)
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
    # Adopt orphaned wrapper descendants so cleanup can reap them, not just
    # signal them. This runtime requires Linux (as does flock and Compose).
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot become SteamCMD child subreaper')
    # Close the spawn/cleanup-handler race on updater shutdown.
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    try:
        child = subprocess.Popen([os.getenv('STEAMCMD', '/steamcmd/steamcmd.sh'), *args, '+quit'],
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 start_new_session=True,
                                 preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
    except BaseException:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        raise
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        output, _ = child.communicate(timeout=float(os.getenv('STEAMCMD_TIMEOUT', '7200')))
        if child.returncode: raise RuntimeError('SteamCMD failed; fleet remains stopped')
        return output
    finally:
        # Includes metadata commands: SteamCMD can update its own files there.
        # Do not let a repeated shutdown interrupt cleanup and release our locks.
        handlers = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            stop_child(child)
            while True:
                try: os.waitpid(-child.pid, 0)
                except ChildProcessError: break
        finally:
            if child.stdout: child.stdout.close()
            for sig, handler in handlers.items(): signal.signal(sig, handler)


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
    def shutdown(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
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
