#!/usr/bin/env python3
"""Explicit, offline migration of saved GMM config; run only with servers stopped."""
import argparse
import copy
import json
import sys
from pathlib import Path


def migrate(config, *, map_change_owner=None):
    result = copy.deepcopy(config)
    if map_change_owner not in (None, 'gmm', 'preserve'):
        raise ValueError('Unknown map-change-owner choice')
    version = result.get('Version', 12)
    if version not in (12, 13):
        raise ValueError('Expected GameModeManager schema 12 or 13')
    rotation = result.setdefault('Rotation', {})
    if map_change_owner == 'gmm':
        rotation['Enabled'] = True
    elif rotation.get('Enabled') is False and map_change_owner is None:
        raise ValueError('Rotation.Enabled=false leaves match-end ownership ambiguous. '
                         'Choose --map-change-owner gmm after disabling competing GG1/engine changes, '
                         'or --map-change-owner preserve for an intentional alternative or disabled setup.')
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


def update(path, *, map_change_owner=None):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Refusing symlinked configuration path')
    original = path.read_bytes()
    saved = json.loads(original)
    result = migrate(saved, map_change_owner=map_change_owner)
    if result == saved:
        return False
    owner_repair = (saved.get('Version') == 13 and map_change_owner == 'gmm'
                    and saved.get('Rotation', {}).get('Enabled') is False)
    suffix = '.before-map-owner' if owner_repair else '.before-panorama'
    backup = path.with_name(path.name + suffix)
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
    parser.add_argument('--map-change-owner', choices=('gmm', 'preserve'),
                        help='gmm enables map advancement; preserve retains an intentional owner/disabled setup')
    args = parser.parse_args()
    if args.map_change_owner == 'preserve':
        print('Warning: preserving map-change ownership; verify an external owner or intentional disabled advancement. '
              'Immediate RTV success does not verify match-end ownership.', file=sys.stderr)
    try:
        changed = update(args.config, map_change_owner=args.map_change_owner)
    except ValueError as error:
        parser.error(str(error))
    print('Migrated; exclusive backup saved alongside config' if changed else 'Already migrated')
