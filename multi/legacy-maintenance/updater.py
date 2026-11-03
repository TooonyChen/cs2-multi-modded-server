#!/usr/bin/env python3
"""Update official Linux CS2 framework releases in the persistent overlay.
Never overwrite server/plugin configuration. All downloads validate before writes.
"""
import argparse
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time
import urllib.request
import zipfile


def safe_path(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe archive path: ' + name)
    return p.as_posix()


def allowed(component, name):
    name = safe_path(name)
    if component == 'css':
        return name.startswith(('addons/counterstrikesharp/api/', 'addons/counterstrikesharp/bin/', 'addons/counterstrikesharp/gamedata/')) or name == 'addons/metamod/counterstrikesharp.vdf'
    if component == 'metamod':
        return name.startswith('addons/metamod/bin/') or name in ('addons/metamod.vdf', 'addons/metamod_x64.vdf')
    if component == 'fixspawn':
        return name.startswith('addons/counterstrikesharp/plugins/FixRandomSpawn/') or name == 'addons/counterstrikesharp/gamedata/FixRandomSpawn.json'
    if component == 'matchzy':
        return name.startswith('addons/counterstrikesharp/plugins/MatchZy/') or name == 'addons/counterstrikesharp/gamedata/matchzy.json'
    if component == 'inventory':
        return name.startswith('addons/counterstrikesharp/plugins/InventorySimulator/') or name == 'addons/counterstrikesharp/gamedata/inventory-simulator.json'
    return False


def target_path(component, name):
    name = safe_path(name)
    if component == 'matchzy':
        name = name.replace('plugins/MatchZy/', 'plugins/disabled/MatchZy/', 1)
    return name


CACHE = None


def fetch(url):
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    cache = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json') if CACHE and url.startswith('https://api.github.com/') else None
    if cache and cache.exists() and time.time() - cache.stat().st_mtime < 900:
        return cache.read_bytes()
    req = urllib.request.Request(url, headers={'User-Agent': 'Tony-CS2-maintenance/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read()
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return data


def metamod_asset(releases):
    for release in releases:
        if release.get('draft') or not release['tag_name'].startswith('2.0.'):
            continue
        for asset in release['assets']:
            if asset['name'].endswith('-linux.tar.gz'):
                return dict(asset, version=release['tag_name'])
    raise ValueError('No official CS2 Metamod 2.0 Linux release')


def latest_asset(repo, name):
    release = json.loads(fetch('https://api.github.com/repos/' + repo + '/releases/latest'))
    assets = [a for a in release['assets'] if name(a['name'])]
    if len(assets) != 1:
        raise ValueError('Ambiguous release asset for ' + repo)
    return dict(assets[0], version=release['tag_name'])


def allocator_gamedata():
    changes = json.loads(fetch('https://api.github.com/repos/yonilerner/cs2-retakes-allocator/commits?path=Resources/RetakesAllocator_gamedata.json&per_page=1'))
    commit = changes[0]['sha']
    return {'name': 'RetakesAllocator.json', 'version': commit, 'browser_download_url': 'https://raw.githubusercontent.com/yonilerner/cs2-retakes-allocator/' + commit + '/Resources/RetakesAllocator_gamedata.json'}


def unpack(component, asset, data):
    digest = asset.get('digest')
    if digest and digest.startswith('sha256:'):
        if hashlib.sha256(data).hexdigest() != digest.split(':', 1)[1]:
            raise ValueError('Release digest mismatch')
    files = {}
    if component == 'allocator':
        source = json.loads(data.decode('utf-8-sig'))
        if 'GiveNamedItem2' not in source:
            raise ValueError('Allocator signature missing')
        return {
            'addons/counterstrikesharp/gamedata/RetakesAllocator.json': json.dumps({'GiveNamedItem2': source['GiveNamedItem2']}, indent=2).encode(),
            'addons/counterstrikesharp/plugins/disabled/RetakesAllocator/gamedata/RetakesAllocator_gamedata.json': json.dumps(source, indent=2).encode(),
        }
    if asset['name'].endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                name = safe_path(entry.filename)
                if component == 'fixspawn':
                    name = 'addons/counterstrikesharp/' + name
                if not entry.is_dir() and allowed(component, name):
                    files[target_path(component, name)] = archive.read(entry)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for entry in archive.getmembers():
                safe_path(entry.name)
                if entry.isfile() and allowed(component, entry.name):
                    files[entry.name] = archive.extractfile(entry).read()
    required = {'css': 'addons/counterstrikesharp/bin/linuxsteamrt64/counterstrikesharp.so', 'metamod': 'addons/metamod/bin/linuxsteamrt64/metamod.2.cs2.so', 'inventory': 'addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll', 'matchzy': 'addons/counterstrikesharp/plugins/disabled/MatchZy/MatchZy.dll', 'fixspawn': 'addons/counterstrikesharp/plugins/FixRandomSpawn/FixRandomSpawn.dll'}
    if required[component] not in files:
        raise ValueError('Incomplete ' + component + ' archive')
    return files


def keep_pin(release, pin):
    return tuple(int(v) for v in release.lstrip('v').split('.')[:3]) < tuple(pin['release_floor'])


def update(root, state):
    global CACHE
    CACHE = state / 'metadata-cache'
    root.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'update.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_path = state / 'versions.json'
        old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        releases = json.loads(fetch('https://api.github.com/repos/alliedmodders/metamod-source/releases?per_page=30'))
        assets = {
            'metamod': metamod_asset(releases),
            'css': latest_asset('roflmuffin/CounterStrikeSharp', lambda n: n.startswith('counterstrikesharp-linux-') and n.endswith('.zip')),
            'allocator': allocator_gamedata(),
            'fixspawn': latest_asset('qstage/CS2-FixRandomSpawn', lambda n: n == 'CS2-FixRandomSpawn.zip'),
            'matchzy': latest_asset('shobhit-pathak/MatchZy', lambda n: n.startswith('MatchZy-') and n.endswith('.zip') and 'with-cssharp' not in n),
            'inventory': latest_asset('ianlucas/cs2-css-inventory-simulator', lambda n: n.startswith('InventorySimulator-') and n.endswith('.zip')),
        }
        wanted = {k: {'version': a['version'], 'asset': a['name'], 'digest': a.get('digest')} for k, a in assets.items()}
        pin_path = state / 'css-pin.json'
        pin = json.loads(pin_path.read_text()) if pin_path.exists() else None
        if pin and keep_pin(assets['css']['version'], pin):
            if 'css' not in old:
                raise ValueError('Pinned CSS manifest missing')
            wanted['css'] = old['css']
            del assets['css']
            print('PINNED_CSS ' + json.dumps(pin), flush=True)
        pending = [k for k in assets if old.get(k) != wanted[k]]
        if not pending:
            print('UP_TO_DATE ' + json.dumps(wanted), flush=True)
            return False
        files = {}
        # Complete every download and validation before modifying the overlay.
        for component in pending:
            a = assets[component]
            data = fetch(a['browser_download_url'])
            files.update(unpack(component, a, data))
        backup = state / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
        backup.mkdir(parents=True)
        new_paths = []
        try:
            for name, data in files.items():
                dest = root / name
                if dest.exists():
                    previous = backup / name
                    previous.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, previous)
                else:
                    new_paths.append(name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                temp = dest.with_name(dest.name + '.update-tmp')
                temp.write_bytes(data)
                temp.chmod(0o644)
                os.replace(temp, dest)
            (backup / 'previous-versions.json').write_text(json.dumps(old, indent=2))
            (backup / 'new-paths.json').write_text(json.dumps(new_paths))
            temp = state / 'versions.json.new'
            temp.write_text(json.dumps(wanted, indent=2))
            os.replace(temp, manifest_path)
        except Exception:
            for name in files:
                previous = backup / name
                if previous.exists():
                    shutil.copy2(previous, root / name)
                elif name in new_paths:
                    (root / name).unlink(missing_ok=True)
            raise
        print('UPDATED ' + json.dumps(wanted) + ' BACKUP=' + str(backup), flush=True)
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    update(args.root, args.state)
