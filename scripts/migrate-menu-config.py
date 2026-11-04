#!/usr/bin/env python3
"""Explicit, offline migration of saved GMM config; run only with servers stopped."""
import argparse
import copy
import json
from pathlib import Path


def migrate(config):
    result = copy.deepcopy(config)
    version = result.get('Version', 12)
    if version not in (12, 13):
        raise ValueError('Expected GameModeManager schema 12 or 13')
    result['Version'] = 13
    result.setdefault('WorkshopAddon', '3831211166')
    rtv = result.get('RTV', {})
    chooser = result.setdefault('MapChooser', {})
    chooser.setdefault('GeneratePools', True)
    chooser.setdefault('TriggerSecondsBeforeEnd', rtv.get('TriggerSecondsBeforeEnd', 60))
    chooser.setdefault('TriggerKillsBeforeEnd', rtv.get('TriggerKillsBeforeEnd', 13))
    chooser.setdefault('ModesInVotes', rtv.get('IncludeModes', True))
    votes = result.setdefault('Votes', {})
    if votes.get('Style') not in ('menu', 'native'):
        votes['Style'] = 'menu'
    return result


def update(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Refusing symlinked configuration path')
    original = path.read_bytes()
    result = migrate(json.loads(original))
    if result == json.loads(original):
        return False
    backup = path.with_name(path.name + '.before-panorama')
    # Never overwrite the original backup on a repeated migration.
    with backup.open('xb') as handle:
        handle.write(original)
    temporary = path.with_name(path.name + '.panorama-new')
    with temporary.open('x') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    print('Migrated; original saved as .before-panorama' if update(args.config) else 'Already migrated')
