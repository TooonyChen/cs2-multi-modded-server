"""Saved-config ownership is an explicit offline operator choice."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_bundle import ROOT, migration


class OwnershipMigrationTests(unittest.TestCase):
    def saved(self, version=12, enabled=False):
        config = json.loads((ROOT / 'runtime/fixtures/gmm-v12.json').read_text())
        config['Version'] = version
        config['Rotation']['Enabled'] = enabled
        return config

    def test_disabled_rotation_requires_explicit_choice_for_both_schemas(self):
        for version in (12, 13):
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, 'map-change-owner'):
                    migration.migrate(self.saved(version))

    def test_gmm_choice_changes_only_ownership_beyond_menu_migration(self):
        old = self.saved()
        preserved = migration.migrate(old, map_change_owner='preserve')
        changed = migration.migrate(old, map_change_owner='gmm')
        preserved['Rotation']['Enabled'] = True
        self.assertEqual(preserved, changed)
        self.assertFalse(old['Rotation']['Enabled'])
        self.assertEqual(old['GameModes'], changed['GameModes'])

    def test_preserve_allows_deliberately_disabled_or_other_owner_configuration(self):
        for enabled in (False, True):
            old = self.saved(enabled=enabled)
            old['Rotation']['ModeRotation'] = True
            old['Rotation']['WhenServerEmpty'] = True
            old['Rotation']['ModeSchedules'] = True
            migrated = migration.migrate(old, map_change_owner='preserve')
            self.assertEqual(old['Rotation'], migrated['Rotation'])
            self.assertEqual(migrated, migration.migrate(migrated, map_change_owner='preserve'))

    def test_enabled_config_needs_no_ownership_override(self):
        old = self.saved(enabled=True)
        self.assertEqual(old['Rotation'], migration.migrate(old)['Rotation'])

    def test_cli_refuses_before_any_write_then_backs_up_explicit_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'gmm.json'
            raw = json.dumps(self.saved()).encode()
            path.write_bytes(raw)
            cmd = [sys.executable, str(ROOT / 'scripts/migrate-menu-config.py'), str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('map-change-owner', result.stderr)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(list(Path(tmp).iterdir()), [path])
            result = subprocess.run(cmd + ['--map-change-owner', 'gmm'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.with_name('gmm.json.before-panorama').read_bytes(), raw)
            self.assertTrue(json.loads(path.read_text())['Rotation']['Enabled'])
            self.assertFalse(migration.update(path, map_change_owner='gmm'))

    def test_schema13_ownership_repair_preserves_previous_menu_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'gmm.json'
            saved = migration.migrate(self.saved(), map_change_owner='preserve')
            raw = json.dumps(saved).encode()
            path.write_bytes(raw)
            prior = path.with_name('gmm.json.before-panorama')
            prior.write_bytes(b'original schema12 backup')
            self.assertTrue(migration.update(path, map_change_owner='gmm'))
            self.assertEqual(prior.read_bytes(), b'original schema12 backup')
            self.assertEqual(path.with_name('gmm.json.before-map-owner').read_bytes(), raw)

    def test_cli_preserve_emits_ownership_warning_without_changing_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'gmm.json'
            path.write_text(json.dumps(self.saved()))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/migrate-menu-config.py'), str(path),
                                     '--map-change-owner', 'preserve'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('owner', result.stderr)
            self.assertFalse(json.loads(path.read_text())['Rotation']['Enabled'])
