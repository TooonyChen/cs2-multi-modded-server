import importlib.util
import pathlib
import tempfile
import unittest

class RuntimeTests(unittest.TestCase):
    def test_instances_share_binary_but_keep_settings(self):
        spec = importlib.util.spec_from_file_location('runtime', pathlib.Path(__file__).with_name('runtime.py'))
        assert spec is not None and spec.origin is not None and spec.loader is not None
        self.assertTrue(pathlib.Path(spec.origin).exists(), 'multi-instance runtime is missing')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as t:
            b = pathlib.Path(t)/'base'; b.mkdir()
            (b/'game/csgo/cfg').mkdir(parents=True)
            (b/'game/csgo/cfg/server.cfg').write_text('default')
            (b/'game/core.vpk').write_text('one shared texture')
            for name in ['a', 'b', 'c']:
                m.materialize(b, pathlib.Path(t)/name)
            a = pathlib.Path(t)/'a'; c = pathlib.Path(t)/'c'
            (a/'game/csgo/cfg/server.cfg').write_text('private')
            m.materialize(b, a)
            self.assertEqual((a/'game/csgo/cfg/server.cfg').read_text(), 'private')
            self.assertEqual((c/'game/csgo/cfg/server.cfg').read_text(), 'default')
            self.assertTrue((a/'game/core.vpk').samefile(c/'game/core.vpk'))
            self.assertEqual((b/'game/csgo/cfg/server.cfg').read_text(), 'default')


    def test_empty_policy_fails_closed(self):
        import runtime as m
        import time
        import json
        with tempfile.TemporaryDirectory() as t:
            m.CONTROL = pathlib.Path(t)
            self.assertFalse(m.all_empty(['a', 'b']))
            for name in ['a', 'b']:
                (m.CONTROL/(name+'.json')).write_text(json.dumps({'running': True, 'players': 0, 'time': time.time()}))
            self.assertTrue(m.all_empty(['a', 'b']))
            p = m.CONTROL/'b.json'
            p.write_text(json.dumps({'running': True, 'players': None, 'time': time.time()}))
            self.assertFalse(m.all_empty(['a', 'b']))
            p.write_text(json.dumps({'running': True, 'players': 2, 'time': time.time()}))
            self.assertFalse(m.all_empty(['a', 'b']))
            p.write_text(json.dumps({'running': True, 'players': 0, 'time': time.time()-30}))
            self.assertFalse(m.all_empty(['a', 'b']))
            self.assertEqual(m.player_count('players : 2 humans, 4 bots (32 max)'), 2)
            self.assertIsNone(m.player_count('timeout'))

    def test_three_real_supervisors_quiesce_and_restart_after_transaction(self):
        import runtime as m
        import subprocess
        import os
        import json
        import time
        import sys
        def wait_for(predicate):
            end = time.monotonic()+12
            while time.monotonic() < end:
                if predicate(): return
                time.sleep(.05)
            self.fail('Timed out waiting for supervisor transition')
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            m.BASE = p/'base'; m.BASE.mkdir()
            m.CONTROL = p/'control'; m.CONTROL.mkdir()
            (m.BASE/'.ready').touch()
            (m.BASE/'texture.vpk').write_text('v1')
            fake = p/'fake.py'
            fake.write_text("import os,signal,time,pathlib\np=pathlib.Path(os.environ['INSTANCE_STATE'])/'running'\np.write_text(str(os.getpid()))\ndef stop(*a):\n p.unlink(missing_ok=True)\n raise SystemExit\nsignal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(.05)\n")
            children = []
            markers = []
            try:
                for name in ['a','b','c']:
                    state=p/name; state.mkdir(); markers.append(state/'running')
                    env=dict(os.environ, GAME_BASE=str(m.BASE), CONTROL=str(m.CONTROL),
                             INSTANCE_STATE=str(state), INSTANCE_ID=name,
                             TEST_COMMAND=json.dumps([sys.executable,str(fake)]))
                    children.append(subprocess.Popen([sys.executable, str(pathlib.Path(m.__file__)), 'server'],env=env))
                wait_for(lambda: all(x.exists() for x in markers))
                for name in ['a','b','c']:
                    self.assertTrue((p/name/'cfg').is_symlink())
                    self.assertFalse((p/name/'cfg').readlink().is_absolute())
                    (p/name/'cfg/server.cfg').write_text(name)
                self.assertEqual((p/'a/cfg/server.cfg').read_text(),'a')
                self.assertEqual((p/'b/cfg/server.cfg').read_text(),'b')
                first = [x.read_text() for x in markers]
                def apply():
                    self.assertTrue(all(not x.exists() for x in markers), 'Update began before games stopped')
                    (m.BASE/'texture.vpk').write_text('v2')
                m.transaction(apply)
                wait_for(lambda: all(x.exists() for x in markers))
                self.assertNotEqual(first, [x.read_text() for x in markers])
                for name in ['a','b','c']:
                    self.assertEqual((p/name/'installation/texture.vpk').read_text(), 'v2')
                def fail():
                    self.assertTrue(all(not x.exists() for x in markers))
                    raise RuntimeError('injected interrupted apply')
                with self.assertRaises(RuntimeError): m.transaction(fail)
                self.assertTrue((m.CONTROL/'updating').exists())
                time.sleep(1.2)
                self.assertTrue(all(not x.exists() for x in markers))
                m.transaction(lambda: None)
                wait_for(lambda: all(x.exists() for x in markers))
            finally:
                for child in children: child.terminate()
                for child in children: child.wait(timeout=10)

    def test_shared_overlay_cannot_escape_base(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t); b=p/'base'; b.mkdir()
            (p/'secret').write_text('outside')
            (b/'bad').symlink_to(p/'secret')
            with self.assertRaises(ValueError): m.materialize(b,p/'instance')

    def test_removed_binary_disappears_but_private_data_survives(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t); b=p/'base'; b.mkdir(); a=p/'a'
            (b/'plugin.dll').write_text('v1')
            m.materialize(b,a)
            (a/'local.db').write_text('player data')
            (b/'plugin.dll').unlink()
            m.materialize(b,a)
            self.assertFalse((a/'plugin.dll').is_symlink())
            self.assertEqual((a/'local.db').read_text(),'player data')


    def test_import_keeps_modes_and_admin_data_private(self):
        from import_existing import import_snapshot
        import json
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t); source=p/'source'
            plugin=source/'addons/counterstrikesharp/plugins/Example'
            plugin.mkdir(parents=True)
            (plugin/'Example.dll').write_bytes(b'fixture-not-a-real-binary')
            (plugin/'player.db').write_text('private-player-data')
            cfg=source/'addons/counterstrikesharp/configs/plugins/GameModeManager'
            cfg.mkdir(parents=True)
            modes={'GameModes':[{'Name':str(n)} for n in range(32)],'DefaultGameMode':'0'}
            (cfg/'GameModeManager.json').write_text(json.dumps(modes))
            (source/'cfg').mkdir(); (source/'cfg/server.cfg').write_text('private-rcon-fixture')
            shared=p/'shared'; instance=p/'instance'
            self.assertEqual(import_snapshot(source,shared,instance),[1,3])
            self.assertTrue((shared/'addons/counterstrikesharp/plugins/Example/Example.dll').exists())
            private=instance/'installation/game/csgo'
            self.assertEqual(json.loads((private/cfg.relative_to(source)/'GameModeManager.json').read_text()),modes)
            self.assertFalse((shared/'cfg/server.cfg').exists())
            self.assertFalse((shared/'addons/counterstrikesharp/plugins/Example/player.db').exists())
            with self.assertRaises(FileExistsError): import_snapshot(source,shared,instance)

    def test_public_build_ignores_depot_public_manifests(self):
        import runtime as m
        text='"manifests" { "public" { "gid" "123" } } "branches" { "public" { "buildid" "26393695" } }'
        self.assertEqual(m.public_build(text),'26393695')
        with self.assertRaises(RuntimeError): m.public_build('Steam network error')

if __name__ == '__main__': unittest.main()
