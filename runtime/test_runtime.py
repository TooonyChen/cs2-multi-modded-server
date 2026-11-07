import importlib.util
import os
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
            (m.BASE/'game/csgo/addons/gmm').mkdir(parents=True)
            (m.BASE/'game/csgo/addons/gmm/gmm.dll').write_text('shared')
            fake = p/'fake.py'
            fake.write_text("import os,signal,time,pathlib\np=pathlib.Path(os.environ['INSTANCE_STATE'])/'running'\np.write_text(str(os.getpid()))\ndef stop(*a):\n p.unlink(missing_ok=True)\n raise SystemExit\nsignal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(.05)\n")
            children = []
            markers = []
            try:
                for name in ['a','b','c']:
                    state=p/name; state.mkdir(); markers.append(state/'running')
                    if name == 'b':  # A different mode: its own plugin set, applied by the supervisor.
                        (state/'instance.json').write_text(json.dumps({'exclude': ['addons/gmm']}))
                        (state/'overlay/addons/own').mkdir(parents=True)
                        (state/'overlay/addons/own/own.dll').write_text('own')
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
                # The plugin set survives the update restart; other instances are unaffected.
                self.assertFalse(os.path.lexists(p/'b/addons/gmm'))
                self.assertEqual((p/'b/addons/own/own.dll').read_text(), 'own')
                for name in ['a','c']:
                    self.assertEqual((p/name/'addons/gmm/gmm.dll').read_text(), 'shared')
                    self.assertFalse(os.path.lexists(p/name/'addons/own'))
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

    def test_steam_timeout_reaps_writer_before_recovery(self):
        self.check_steam_writer('timeout')

    def test_updater_shutdown_reaps_metadata_and_install_writers(self):
        for mode in ('interrupt', 'interrupt-install', 'sigint-install'):
            with self.subTest(mode=mode): self.check_steam_writer(mode)

    def check_steam_writer(self, mode):
        import os
        import subprocess
        import sys
        import textwrap
        import time
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            (p/'base').mkdir(); (p/'control').mkdir()
            writer = p/'writer.py'
            writer.write_text(textwrap.dedent('''\
                import os, pathlib, signal, time
                p = pathlib.Path(os.environ['GAME_BASE'])
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                (p/'writer.pid').write_text(str(os.getpid()))
                while True:
                    with (p/'writes').open('a') as f: f.write('x')
                    time.sleep(.02)
            '''))
            wrapper = p/'steamcmd'
            wrapper.write_text('#!/bin/sh\n' + sys.executable + ' ' + str(writer) + ' &\nwait\n')
            wrapper.chmod(0o755)
            driver = p/'driver.py'
            driver.write_text(textwrap.dedent('''\
                import os, pathlib, subprocess, sys
                sys.path.insert(0, sys.argv[1])
                import runtime as m
                # This test checks process/lock lifetime, not host-wide flush
                # latency (os.sync may stall on unrelated CI runner I/O).
                m.os.sync = lambda: None
                if sys.argv[2] != 'timeout':
                    if sys.argv[2].endswith('-install'):
                        original = m.steam
                        m.steam = lambda *a: ('"public" { "buildid" "1" }' if '+app_info_print' in a else original(*a))
                        m.install = lambda *_: m.steam('+app_update', '730')
                    m.updater()
                else:
                    try: m.transaction(lambda: m.steam('+app_update', '730'))
                    except subprocess.TimeoutExpired: pass
                    assert (m.CONTROL/'updating').exists()
                    def recover():
                        pid = int((m.BASE/'writer.pid').read_text())
                        assert not pathlib.Path(f'/proc/{pid}').exists(), 'writer survived into recovery'
                        (m.BASE/'recovered').touch()
                    m.transaction(recover)
            '''))
            env = dict(os.environ, GAME_BASE=str(p/'base'), CONTROL=str(p/'control'),
                       STEAMCMD=str(wrapper), STEAMCMD_TIMEOUT='.4', STOP_TIMEOUT='.1')
            child = subprocess.Popen([sys.executable, str(driver), str(pathlib.Path(__file__).parent), mode], env=env)
            pid = None
            try:
                end = time.monotonic()+5
                while time.monotonic() < end and not (p/'base/writer.pid').exists(): time.sleep(.02)
                self.assertTrue((p/'base/writer.pid').exists())
                pid = int((p/'base/writer.pid').read_text())
                if mode != 'timeout':
                    import signal
                    child.send_signal(signal.SIGINT if mode.startswith('sigint') else signal.SIGTERM)
                self.assertEqual(child.wait(timeout=5), 0)
                before = (p/'base/writes').read_bytes()
                time.sleep(.2)
                self.assertEqual((p/'base/writes').read_bytes(), before, 'Steam descendant wrote after lock release')
                self.assertFalse(pathlib.Path(f'/proc/{pid}').exists(), 'Steam descendant was not reaped')
                if mode == 'timeout': self.assertTrue((p/'base/recovered').exists())
                if mode.endswith('-install'): self.assertTrue((p/'control/updating').exists())
            finally:
                if child.poll() is None: child.kill(); child.wait()
                if pid is not None:
                    try: os.kill(pid, 9)
                    except ProcessLookupError: pass

    def test_materialize_rejects_installation_root_symlink(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = p/'base'; base.mkdir()
            outside = p/'outside'; outside.mkdir()
            (outside/'sentinel').write_text('unchanged')
            (base/'resource.vpk').write_text('shared')
            target = p/'installation'; target.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError): m.materialize(base, target)
            self.assertEqual(sorted(x.name for x in outside.iterdir()), ['sentinel'])
            self.assertEqual((outside/'sentinel').read_text(), 'unchanged')

    def test_materialize_confines_manifest_and_nested_destinations(self):
        import json
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = p/'base'; base.mkdir()
            outside = p/'outside'; outside.mkdir()
            sentinel = outside/'sentinel'; sentinel.write_text('unchanged')
            target = p/'installation'; target.mkdir()
            for kind in ('directory', 'manifest-link', 'manifest-traversal'):
                with self.subTest(kind=kind):
                    if kind == 'directory':
                        (base/'nested').mkdir(); (base/'nested/new.cfg').write_text('default')
                        (target/'nested').symlink_to(outside, target_is_directory=True)
                    elif kind == 'manifest-link':
                        (target/'.shared-files.json').symlink_to(sentinel)
                    else:
                        (outside/'link').symlink_to(sentinel)
                        (target/'.shared-files.json').write_text(json.dumps(['../outside/link']))
                    with self.assertRaises(RuntimeError): m.materialize(base, target)
                    self.assertEqual(sentinel.read_text(), 'unchanged')
                    self.assertFalse((outside/'new.cfg').exists())
                    if kind == 'directory':
                        (target/'nested').unlink()
                        (base/'nested/new.cfg').unlink(); (base/'nested').rmdir()
                    else: (target/'.shared-files.json').unlink()
            self.assertTrue((outside/'link').is_symlink())

    def test_materialize_rejects_reserved_manifest_in_base(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = p/'base'; base.mkdir()
            manifest = base/'.shared-files.json'; manifest.write_text('base sentinel')
            with self.assertRaises(RuntimeError): m.materialize(base, p/'instance')
            self.assertEqual(manifest.read_text(), 'base sentinel')

    def shared_fixture(self, root):
        base = root/'base'
        csgo = base/'game/csgo'
        for rel, text in {
            'addons/counterstrikesharp/plugins/GameModeManager/GameModeManager.dll': 'gmm',
            'addons/counterstrikesharp/plugins/GameModeManager/GameModeManager.deps.json': '{}',
            'addons/counterstrikesharp/shared/GameModeManager.Shared/GameModeManager.Shared.dll': 'gmm api',
            'addons/counterstrikesharp/plugins/SimpleAdmin/SimpleAdmin.dll': 'admin',
            'addons/counterstrikesharp/configs/plugins/GameModeManager/GameModeManager.json': '{"shared": 1}',
            'addons/metamod/multiaddonmanager.vdf': 'mam',
            'cfg/server.cfg': 'shared cfg',
        }.items():
            (csgo/rel).parent.mkdir(parents=True, exist_ok=True)
            (csgo/rel).write_text(text)
        return base

    GMM = ['addons/counterstrikesharp/plugins/GameModeManager',
           'addons/counterstrikesharp/shared/GameModeManager.Shared']

    def test_excluded_plugins_stay_out_across_restarts(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p)
            plugins = 'game/csgo/addons/counterstrikesharp/plugins'
            # Upgrade path: the instance already ran with the full shared set.
            m.materialize(base, p/'prophunt')
            self.assertTrue((p/'prophunt'/plugins/'GameModeManager/GameModeManager.dll').is_symlink())
            for restart in range(3):
                with self.subTest(restart=restart):
                    m.materialize(base, p/'prophunt', exclude=self.GMM)
                    m.materialize(base, p/'server1')
                    self.assertFalse(os.path.lexists(p/'prophunt'/plugins/'GameModeManager'))
                    self.assertFalse(os.path.lexists(
                        p/'prophunt/game/csgo/addons/counterstrikesharp/shared/GameModeManager.Shared'))
                    self.assertEqual((p/'prophunt'/plugins/'SimpleAdmin/SimpleAdmin.dll').read_text(), 'admin')
                    self.assertTrue((p/'prophunt/game/csgo/addons/metamod/multiaddonmanager.vdf').is_symlink())
                    # Other instances keep the complete shared set.
                    self.assertEqual((p/'server1'/plugins/'GameModeManager/GameModeManager.dll').read_text(), 'gmm')
            self.assertEqual((base/'game/csgo'/self.GMM[0]/'GameModeManager.dll').read_text(), 'gmm')
            # Seeded private settings are data, so exclusion never deletes them.
            cfg = p/'prophunt/game/csgo/addons/counterstrikesharp/configs/plugins/GameModeManager/GameModeManager.json'
            self.assertEqual(cfg.read_text(), '{"shared": 1}')
            # Dropping the exclusion restores the shared links.
            m.materialize(base, p/'prophunt')
            self.assertEqual((p/'prophunt'/plugins/'GameModeManager/GameModeManager.dll').read_text(), 'gmm')

    def test_exclusion_keeps_non_empty_private_directories(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p); a = p/'a'
            m.materialize(base, a)
            data = a/'game/csgo'/self.GMM[0]/'players.db'
            data.write_text('private')
            m.materialize(base, a, exclude=self.GMM)
            self.assertEqual(data.read_text(), 'private')
            self.assertFalse(os.path.lexists(a/'game/csgo'/self.GMM[0]/'GameModeManager.dll'))

    def test_instance_overlay_wins_and_tracks_its_own_changes(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p); a = p/'a'
            overlay = p/'overlay'
            menu = 'addons/counterstrikesharp/configs/plugins/GG1MapChooser/GG1MapChooser.json'
            for rel, text in {
                'addons/counterstrikesharp/plugins/PropHunt/PropHunt.dll': 'prop',
                'addons/counterstrikesharp/plugins/SimpleAdmin/SimpleAdmin.dll': 'private admin build',
                'cfg/server.cfg': 'overlay cfg',
                menu: '{"maps": 1}',
                # The overlay may re-add a file under an excluded shared path.
                'addons/counterstrikesharp/shared/GameModeManager.Shared/GameModeManager.Shared.dll': 'own api',
            }.items():
                (overlay/rel).parent.mkdir(parents=True, exist_ok=True)
                (overlay/rel).write_text(text)
            live = a/'game/csgo'
            m.materialize(base, a)
            (live/'cfg/server.cfg').write_text('edited before overlay')
            m.materialize(base, a, exclude=self.GMM, overlay=overlay)
            self.assertEqual((live/'addons/counterstrikesharp/plugins/PropHunt/PropHunt.dll').read_text(), 'prop')
            self.assertEqual((live/'addons/counterstrikesharp/plugins/SimpleAdmin/SimpleAdmin.dll').read_text(),
                             'private admin build')
            self.assertEqual((live/'addons/counterstrikesharp/shared/GameModeManager.Shared/'
                              'GameModeManager.Shared.dll').read_text(), 'own api')
            self.assertFalse(os.path.lexists(live/self.GMM[0]))
            link = live/'addons/counterstrikesharp/plugins/PropHunt/PropHunt.dll'
            self.assertFalse(link.readlink().is_absolute(), 'overlay links must resolve from the host')
            # Mutable overlay files are private copies that win over the shared seed.
            self.assertFalse((live/'cfg/server.cfg').is_symlink())
            self.assertEqual((live/'cfg/server.cfg').read_text(), 'overlay cfg')
            self.assertEqual((live/menu).read_text(), '{"maps": 1}')
            # A live edit survives restarts until the overlay file itself changes.
            (live/menu).write_text('{"maps": 2}')
            m.materialize(base, a, exclude=self.GMM, overlay=overlay)
            self.assertEqual((live/menu).read_text(), '{"maps": 2}')
            (overlay/menu).write_text('{"maps": 3}')
            m.materialize(base, a, exclude=self.GMM, overlay=overlay)
            self.assertEqual((live/menu).read_text(), '{"maps": 3}')
            # Removing an overlay binary restores the shared file or removes the link.
            (overlay/'addons/counterstrikesharp/plugins/SimpleAdmin/SimpleAdmin.dll').unlink()
            (overlay/'addons/counterstrikesharp/plugins/PropHunt/PropHunt.dll').unlink()
            m.materialize(base, a, exclude=self.GMM, overlay=overlay)
            self.assertEqual((live/'addons/counterstrikesharp/plugins/SimpleAdmin/SimpleAdmin.dll').read_text(), 'admin')
            self.assertFalse(os.path.lexists(live/'addons/counterstrikesharp/plugins/PropHunt/PropHunt.dll'))
            self.assertEqual((base/'game/csgo/cfg/server.cfg').read_text(), 'shared cfg')

    def test_instance_inputs_are_confined(self):
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p)
            outside = p/'outside'; outside.mkdir(); (outside/'secret.dll').write_text('outside')
            for name in ('/etc', '../outside', 'addons/../../outside', '', '.'):
                with self.subTest(exclude=name), self.assertRaises(RuntimeError):
                    m.materialize(base, p/'a', exclude=[name])
            overlay = p/'overlay'; (overlay/'addons').mkdir(parents=True)
            (overlay/'addons/escape.dll').symlink_to(outside/'secret.dll')
            with self.assertRaises(RuntimeError): m.materialize(base, p/'b', overlay=overlay)
            self.assertFalse(os.path.lexists(p/'b/game/csgo/addons/escape.dll'))
            linked = p/'linked-overlay'; linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError): m.materialize(base, p/'c', overlay=linked)
            clash = p/'clash'; (clash/'cfg/server.cfg').mkdir(parents=True)
            with self.assertRaises(RuntimeError): m.materialize(base, p/'d', overlay=clash)
            self.assertEqual((outside/'secret.dll').read_text(), 'outside')

    def test_instance_config_is_strict(self):
        import json
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            state = pathlib.Path(t)
            self.assertEqual(m.instance_config(state), {'exclude': []})
            config = state/'instance.json'
            config.write_text(json.dumps({'exclude': self.GMM}))
            self.assertEqual(m.instance_config(state), {'exclude': self.GMM})
            for bad in ({'exclud': []}, {'exclude': 'addons'}, {'exclude': [1]}, ['addons'],
                        {'exclude': ['../escape']}):
                with self.subTest(config=bad), self.assertRaises(RuntimeError):
                    config.write_text(json.dumps(bad)); m.instance_config(state)
            config.unlink(); (state/'real.json').write_text('{}')
            config.symlink_to(state/'real.json')
            with self.assertRaises(RuntimeError): m.instance_config(state)

    def test_workshop_cache_is_private_and_writable(self):
        import json
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p); a = p/'a'
            cache = 'game/bin/linuxsteamrt64/steamapps/workshop'
            (base/cache/'content/730/3831211166').mkdir(parents=True)
            (base/cache/'appworkshop_730.acf').write_text('base acf')
            (base/cache/'content/730/3831211166/addon.vpk').write_text('base addon')
            (base/'steamapps').mkdir(); (base/'steamapps/appmanifest_730.acf').write_text('manifest')
            # Simulate a tree prepared by v0.1.3, which linked the cache into read-only /base.
            m.materialize(base, a)
            stale = a/cache/'appworkshop_730.acf'
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.symlink_to(base/cache/'appworkshop_730.acf')
            manifest = a/'.shared-files.json'
            manifest.write_text(json.dumps(json.loads(manifest.read_text()) + [cache + '/appworkshop_730.acf']))
            m.materialize(base, a)
            self.assertFalse(os.path.lexists(stale))
            self.assertFalse(os.path.lexists(a/cache/'content/730/3831211166/addon.vpk'))
            self.assertTrue((a/cache).is_dir() and not (a/cache).is_symlink())
            (a/cache/'appworkshop_730.acf').write_text('instance acf')
            self.assertEqual((base/cache/'appworkshop_730.acf').read_text(), 'base acf')
            # SteamCMD's own install manifest is still shared.
            self.assertTrue((a/'steamapps/appmanifest_730.acf').is_symlink())
            # A fresh instance gets the cache directory even when the base has none.
            fresh_base = self.shared_fixture(p/'fresh')
            m.materialize(fresh_base, p/'b')
            self.assertTrue((p/'b'/cache).is_dir())

    def test_created_directories_ignore_private_umask(self):
        import runtime as m
        import stat
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.shared_fixture(p)
            overlay = p/'overlay'; (overlay/'addons/own').mkdir(parents=True)
            (overlay/'addons/own/own.dll').write_text('own')
            previous = os.umask(0o077)
            try:
                m.materialize(base, p/'state/installation', overlay=overlay)
            finally:
                os.umask(previous)
            for rel in ('state', 'state/installation', 'state/installation/game/csgo/addons/own',
                        'state/installation/game/csgo/addons/counterstrikesharp/plugins/SimpleAdmin',
                        'state/installation/game/bin/linuxsteamrt64/steamapps/workshop'):
                with self.subTest(path=rel):
                    self.assertEqual(stat.S_IMODE((p/rel).stat().st_mode), 0o755)

    CSS = 'game/csgo/addons/counterstrikesharp'
    API = CSS + '/api'

    def css_fixture(self, root):
        base = self.shared_fixture(root)
        for name, text in {'CounterStrikeSharp.API.dll': 'api v1',
                           'CounterStrikeSharp.API.deps.json': '{"deps": 1}',
                           'CounterStrikeSharp.API.runtimeconfig.json': '{"runtime": 1}',
                           'Serilog.dll': 'serilog'}.items():
            (base/self.API/name).parent.mkdir(parents=True, exist_ok=True)
            (base/self.API/name).write_text(text)
        (base/self.CSS/'dotnet/host/fxr/10.0.3').mkdir(parents=True)
        (base/self.CSS/'dotnet/host/fxr/10.0.3/libhostfxr.so').write_text('fxr')
        return base

    def test_css_api_is_a_private_copy(self):
        # The .NET host resolves api/CounterStrikeSharp.API.dll through symlinks and managed CSS
        # takes its plugins/configs root from that location, so a linked api/ points CSS at /base.
        import runtime as m
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.css_fixture(p); a = p/'a'
            m.materialize(base, a)
            api = a/self.API
            for name in ('CounterStrikeSharp.API.dll', 'CounterStrikeSharp.API.deps.json',
                         'CounterStrikeSharp.API.runtimeconfig.json', 'Serilog.dll'):
                with self.subTest(name=name):
                    self.assertFalse((api/name).is_symlink())
                    self.assertEqual((api/name).read_text(), (base/self.API/name).read_text())
                    self.assertEqual(os.path.realpath(api/name), str(api/name))
            # The rest of CSS stays shared: the runtime and the plugin binaries are links.
            self.assertTrue((a/self.CSS/'dotnet/host/fxr/10.0.3/libhostfxr.so').is_symlink())
            self.assertTrue((a/self.CSS/'plugins/SimpleAdmin/SimpleAdmin.dll').is_symlink())
            # A shared CSS update refreshes the copy; a dropped file disappears.
            (base/self.API/'CounterStrikeSharp.API.dll').write_text('api v2')
            (base/self.API/'Serilog.dll').unlink()
            m.materialize(base, a)
            self.assertEqual((api/'CounterStrikeSharp.API.dll').read_text(), 'api v2')
            self.assertFalse(os.path.lexists(api/'Serilog.dll'))
            # An instance overlay may replace an api file; it is copied as well.
            overlay = p/'overlay'; (overlay/'addons/counterstrikesharp/api').mkdir(parents=True)
            (overlay/'addons/counterstrikesharp/api/CounterStrikeSharp.API.dll').write_text('own api')
            m.materialize(base, a, overlay=overlay)
            self.assertFalse((api/'CounterStrikeSharp.API.dll').is_symlink())
            self.assertEqual((api/'CounterStrikeSharp.API.dll').read_text(), 'own api')
            # A fresh instance never needs the upgrade migration.
            self.assertFalse((a/'.css-root-migration.json').exists())

    def test_upgrade_adopts_the_shared_css_configs_that_were_in_effect(self):
        import runtime as m
        import json
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t); base = self.css_fixture(p); a = p/'a'
            admins = self.CSS + '/configs/admins.json'
            core = self.CSS + '/configs/core.json'
            local = self.CSS + '/plugins/SimpleAdmin/SimpleAdmin.json'
            for rel, text in {admins: '{"Tony": 1}', core: '{"autoload": true}', local: '{"db": "shared"}'}.items():
                (base/rel).write_text(text)
            # Lay the instance out as v0.1.3 did: api/ linked into /base, seeds never read by CSS.
            m.materialize(base, a)
            for rel, text in {admins: '{}', local: '{"db": "stale"}'}.items():
                (a/rel).write_text(text)
            for name in json.loads((a/'.private-files.json').read_text()):
                (a/name).unlink(); (a/name).symlink_to(base/name)
            (a/'.shared-files.json').write_text(json.dumps(
                json.loads((a/'.shared-files.json').read_text()) + json.loads((a/'.private-files.json').read_text())))
            (a/'.private-files.json').unlink()
            m.materialize(base, a, exclude=['addons/counterstrikesharp/plugins/GameModeManager'])
            self.assertEqual((a/admins).read_text(), '{"Tony": 1}')
            self.assertEqual((a/local).read_text(), '{"db": "shared"}')
            self.assertEqual((a/core).read_text(), '{"autoload": true}')
            self.assertEqual((a/'.css-root-migration'/admins).read_text(), '{}')
            self.assertEqual((a/'.css-root-migration'/local).read_text(), '{"db": "stale"}')
            self.assertEqual(sorted(json.loads((a/'.css-root-migration.json').read_text())['adopted']),
                             sorted([admins, local]))
            self.assertFalse((a/self.API/'CounterStrikeSharp.API.dll').is_symlink())
            # Runs once: later instance edits are the authoritative settings and survive restarts.
            (a/admins).write_text('{"Tony": 1, "Alyssa": 1}')
            m.materialize(base, a)
            self.assertEqual((a/admins).read_text(), '{"Tony": 1, "Alyssa": 1}')
            self.assertEqual((base/admins).read_text(), '{"Tony": 1}')

    def test_public_build_ignores_depot_public_manifests(self):
        import runtime as m
        text='"manifests" { "public" { "gid" "123" } } "branches" { "public" { "buildid" "26393695" } }'
        self.assertEqual(m.public_build(text),'26393695')
        with self.assertRaises(RuntimeError): m.public_build('Steam network error')

if __name__ == '__main__': unittest.main()
