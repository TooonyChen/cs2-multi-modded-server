#!/usr/bin/env python3
"""Import an OFFLINE, private csgo snapshot; never connects to a production server."""
import argparse
from pathlib import Path
import shutil
from runtime import mutable

SHARED_SUFFIXES = {'.dll', '.so', '.vpk', '.pdb', '.vdf', '.vtex_c', '.vmdl_c', '.vmat_c', '.vsnd_c'}
ROOTS = {'addons', 'cfg', 'maps', 'materials', 'models', 'resource', 'sound', 'panorama', 'gamemodes_server.txt'}


def import_snapshot(source, shared, instance):
    count = [0, 0]
    for src in sorted(source.rglob('*')):
        rel = src.relative_to(source)
        if rel.parts[0] not in ROOTS: continue
        if src.is_symlink(): raise ValueError('Snapshot symlinks are not supported: ' + str(rel))
        if not src.is_file(): continue
        # Arbitrary plugin data stays private. Only known immutable resources are shared.
        immutable = not mutable(rel) and (src.suffix in SHARED_SUFFIXES or
                    '/gamedata/' in '/' + rel.as_posix() or '/lang/' in '/' + rel.as_posix() or
                    src.name.endswith(('.deps.json', '.runtimeconfig.json')))
        dest = shared/rel if immutable else instance/'installation/game/csgo'/rel
        if dest.exists() or dest.is_symlink():
            raise FileExistsError('Import destination already exists: ' + str(dest))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        count[0 if immutable else 1] += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='offline snapshot game/csgo directory')
    parser.add_argument('--shared', type=Path, required=True, help='private central overlay directory')
    parser.add_argument('--instance', type=Path, required=True, help='private instance volume staging directory')
    args = parser.parse_args()
    a,b = import_snapshot(args.source, args.shared, args.instance)
    print(f'Imported {a} shared resources and {b} private files; no server was contacted')
