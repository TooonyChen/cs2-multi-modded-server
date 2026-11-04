"""Validate actual redistributable package contents and saved config boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
runtime_spec = importlib.util.spec_from_file_location('fleet_runtime', ROOT/'runtime/runtime.py')
assert runtime_spec is not None and runtime_spec.loader is not None
fleet = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(fleet)
materialize = fleet.materialize
CSS = ROOT/'game/csgo/addons/counterstrikesharp'
spec = importlib.util.spec_from_file_location('migration', ROOT/'scripts/migrate-menu-config.py')
assert spec is not None and spec.loader is not None
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class BundleTests(unittest.TestCase):
    def test_actual_payloads_match_provenance(self):
        manifest = json.loads((ROOT/'docs/bundled-baseline.json').read_text())
        for name, digest in manifest['files'].items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)
        for source in manifest['sources']:
            self.assertEqual(hashlib.sha256((ROOT/source['source_archive']).read_bytes()).hexdigest(), source['source_sha256'])

    def test_fixrandomspawn_official_layout_and_signatures(self):
        manifest = json.loads((ROOT/'docs/bundled-baseline.json').read_text())
        package = next(p for p in manifest['packages'] if p['name'] == 'FixRandomSpawn 1.2.0')
        self.assertEqual(package['sha256'], '554e5ebe5fb1046e263ff4745477a7f39c91131332918d342ed6e9f595aaed1b')
        expected = {'FixRandomSpawn.dll', 'FixRandomSpawn.pdb', 'FixRandomSpawn.deps.json',
                    'lang/en.json', 'lang/ru.json'}
        plugin = CSS/'plugins/FixRandomSpawn'
        self.assertEqual({str(p.relative_to(plugin)) for p in plugin.rglob('*') if p.is_file()}, expected)
        self.assertIn('1.2.0'.encode('utf-16-le'), (plugin/'FixRandomSpawn.dll').read_bytes())
        data = json.loads((CSS/'gamedata/FixRandomSpawn.json').read_text())
        self.assertEqual(set(data), {'CCSPlayerPawn_EntSelectSpawnPoint', 'CCSPlayerPawn_EntSelectSpawnPoint_Patch'})
        self.assertEqual(data['CCSPlayerPawn_EntSelectSpawnPoint']['signatures']['linux'],
                         '84 D2 0F 84 ? ? ? ? 48 8D 15 ? ? ? ? 48 8B 52')
        self.assertEqual(data['CCSPlayerPawn_EntSelectSpawnPoint_Patch']['signatures']['linux'],
                         '0F 1F 84 00 00 00 00 00')
        self.assertFalse((plugin/'gamedata').exists())
        self.assertFalse((CSS/'plugins/disabled/FixRandomSpawn').exists())
        for p in [CSS/'gamedata/FixRandomSpawn.json', *[plugin/n for n in expected]]:
            self.assertIn(str(p.relative_to(ROOT)), manifest['files'])

    def test_fixrandomspawn_materializes_without_overwriting_private_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)/'base'; target = Path(tmp)/'instance'
            rel = Path('game/csgo/addons/counterstrikesharp')
            shutil.copytree(CSS/'plugins/FixRandomSpawn', base/rel/'plugins/FixRandomSpawn')
            (base/rel/'gamedata').mkdir()
            shutil.copy2(CSS/'gamedata/FixRandomSpawn.json', base/rel/'gamedata/FixRandomSpawn.json')
            config = target/rel/'configs/plugins/FixRandomSpawn/FixRandomSpawn.json'
            config.parent.mkdir(parents=True)
            private = b'{"warmup_mode":{"enable":true},"ConfigVersion":1}\n'
            config.write_bytes(private)
            materialize(base, target)
            for name in ['plugins/FixRandomSpawn/FixRandomSpawn.dll', 'gamedata/FixRandomSpawn.json']:
                self.assertEqual((target/rel/name).read_bytes(), (CSS/name).read_bytes())
            self.assertEqual(config.read_bytes(), private)
            self.assertFalse(config.is_symlink())

    def test_public_admin_default_is_empty_and_private_admins_survive(self):
        config = CSS/'configs/admins.json'
        self.assertEqual(json.loads(config.read_text()), {})
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)/'base'; target = Path(tmp)/'instance'
            rel = Path('game/csgo/addons/counterstrikesharp/configs/admins.json')
            (base/rel).parent.mkdir(parents=True)
            shutil.copy2(config, base/rel)
            materialize(base, target)
            self.assertEqual(json.loads((target/rel).read_text()), {})
            private = b'{"fixture-admin":{"identity":"fixture-only","flags":["@css/root"]}}\n'
            (target/rel).write_bytes(private)
            materialize(base, target)
            self.assertEqual((target/rel).read_bytes(), private)
            self.assertFalse((target/rel).is_symlink())

    def test_casual_mode_and_settings_resolve_with_exact_case(self):
        modes = json.loads((CSS/'configs/plugins/GameModeManager/GameModeManager.json').read_text())['GameModes']['List']
        self.assertEqual(len(modes), 34)
        mode = next(m for m in modes if m['Name'] == 'Casual (1.6)')
        cfg = ROOT/'game/csgo/cfg'
        self.assertEqual(mode['Config'], 'Casual-1.6.cfg')
        self.assertIn(mode['Config'], {p.name for p in cfg.iterdir()})
        text = (cfg/mode['Config']).read_text()
        self.assertIn('exec Casual-1.6_settings.cfg', text)
        self.assertIn('exec_after_map_start "exec Casual-1.6_settings.cfg"', text)
        self.assertNotIn('exec casual-1.6_settings.cfg', text)
        self.assertIn('Casual-1.6_settings.cfg', {p.name for p in cfg.iterdir()})

    def test_api_and_dependency_locations(self):
        api = json.loads((CSS/'api/CounterStrikeSharp.API.deps.json').read_text())
        self.assertIn('CounterStrikeSharp.API/1.0.380-1', api['libraries'])
        self.assertEqual((CSS/'plugins/GameModeManager/GameModeManager.Shared.dll').read_bytes(),
                         (CSS/'shared/GameModeManager.Shared/GameModeManager.Shared.dll').read_bytes())
        for name in ('MenuManagerApi', 'ggmcAPI'):
            self.assertTrue((CSS/f'shared/{name}/{name}.dll').is_file())
        self.assertFalse((CSS/'plugins/GameModeManager/MenuManagerApi.dll').exists())
        self.assertFalse((CSS/'plugins/WASDMenuAPI').exists())
        self.assertTrue((CSS/'plugins/disabled/WASDMenuAPI/WASDMenuAPI.dll').is_file())
        for name in ('MenuManagerCore','GG1MapChooser','PMM_GG1MapChooser'):
            self.assertTrue((CSS/f'plugins/{name}/{name}.dll').is_file())
        local = json.loads((CSS/'plugins/disabled/RetakesAllocator/gamedata/RetakesAllocator_gamedata.json').read_text())
        legacy = json.loads((CSS/'gamedata/RetakesAllocator.json').read_text())
        self.assertEqual(local['GiveNamedItem2'], legacy['GiveNamedItem2'])
        config = json.loads((CSS/'plugins/disabled/RetakesAllocator/config/config.json').read_text())
        for key in ('EnableCanAcquireHook','CapabilityWeaponPaints','AutoUpdateSignatures'):
            self.assertIs(config[key], False)
        self.assertIn('addons/multiaddonmanager/bin/multiaddonmanager', (ROOT/'game/csgo/addons/metamod/multiaddonmanager.vdf').read_text())
        self.assertIn('3461824328,3831211166', (ROOT/'game/csgo/cfg/multiaddonmanager/multiaddonmanager.cfg').read_text())

    def test_migration_preserves_all_modes_and_non_menu_settings(self):
        original = json.loads((ROOT/'runtime/fixtures/gmm-v12.json').read_text())
        expected = json.loads((CSS/'configs/plugins/GameModeManager/GameModeManager.json').read_text())
        self.assertEqual(len(original['GameModes']['List']), 34)
        # The public bundle deliberately repairs the inherited Linux filename case.
        casual = next(m for m in original['GameModes']['List'] if m['Name'] == 'Casual (1.6)')
        self.assertEqual(casual['Config'], 'casual-1.6.cfg')
        casual['Config'] = 'Casual-1.6.cfg'
        self.assertEqual(migration.migrate(original, map_change_owner='preserve'), expected)
        for key in original.keys() - {'Version','Votes'}:
            self.assertEqual(original[key], expected[key], key)
        for key in original['Votes'].keys() - {'Style'}:
            self.assertEqual(original['Votes'][key], expected['Votes'][key])
        self.assertEqual(migration.migrate(expected, map_change_owner='preserve'), expected)
        # Private/custom entries are carried through without substituting public defaults.
        original['GameModes']['List'].append({'Name':'Custom','Config':'private.cfg','DefaultMap':'123'})
        original['GameModes']['Default'] = original['GameModes']['List'][-1]
        original['Rotation']['Enabled'] = True
        migrated = migration.migrate(original)
        self.assertEqual(original['GameModes'], migrated['GameModes'])
        self.assertEqual(original['Rotation'], migrated['Rotation'])
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'config.json'
            raw = json.dumps(original).encode(); f.write_bytes(raw)
            self.assertTrue(migration.update(f))
            self.assertEqual(f.with_name('config.json.before-panorama').read_bytes(), raw)
            self.assertFalse(migration.update(f))
            link = Path(tmp)/'link.json'; link.symlink_to(f)
            with self.assertRaises(ValueError): migration.update(link)
        with self.assertRaises(ValueError): migration.migrate({'Version':99})

    def test_materialize_refreshes_real_binary_but_preserves_private_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)/'base'; target = Path(tmp)/'instance'
            rel = Path('game/csgo/addons/counterstrikesharp')
            binary = rel/'plugins/GameModeManager/GameModeManager.dll'
            config = rel/'configs/plugins/GameModeManager/GameModeManager.json'
            for dest, source in [(binary,CSS/'plugins/GameModeManager/GameModeManager.dll'),
                                 (config,ROOT/'runtime/fixtures/gmm-v12.json')]:
                (base/dest).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,base/dest)
            old = rel/'plugins/WASDMenuAPI/WASDMenuAPI.dll'
            (base/old).parent.mkdir(parents=True);shutil.copy2(CSS/'plugins/disabled/WASDMenuAPI/WASDMenuAPI.dll',base/old)
            materialize(base,target)
            private = json.loads((target/config).read_text()); private['GameModes']['Default']['Config']='private.cfg'
            (target/config).write_text(json.dumps(private))
            shutil.copy2(CSS/'configs/plugins/GameModeManager/GameModeManager.json',base/config)
            (base/old).unlink()
            materialize(base,target)
            self.assertEqual(json.loads((target/config).read_text()), private)
            self.assertFalse((target/config).is_symlink())
            self.assertTrue((target/binary).is_symlink())
            self.assertEqual((target/binary).read_bytes(), (CSS/'plugins/GameModeManager/GameModeManager.dll').read_bytes())
            self.assertFalse((target/old).exists())

    def test_pins_stop_latest_lookup_before_any_network_or_mutation(self):
        source = (ROOT/'scripts/update/update.sh').read_text()
        function = source[source.index('process_mod() {'):source.index('# ----------------------------------------------------------------------------- main')]
        # Exercise the real updater function, with network lookup deliberately fatal.
        shell = 'set -eu\nsource scripts/update/lib.sh\nlog() { printf "%s\\n" "$*"; }\nfetch_latest_release() { exit 91; }\nRES_UPTODATE=()\n' + function
        shell += '\nprocess_mod CounterStrikeSharp https://github.com/roflmuffin/CounterStrikeSharp 1.0.380-1\n'
        shell += '\nprocess_mod CS2-FixRandomSpawn https://github.com/qstage/CS2-FixRandomSpawn 1.2.0\n'
        result = subprocess.run(['bash','-c',shell],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('PIN CounterStrikeSharp 1.0.380-1',result.stdout)
        self.assertIn('PIN CS2-FixRandomSpawn 1.2.0',result.stdout)


if __name__ == '__main__': unittest.main()
