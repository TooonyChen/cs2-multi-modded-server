import unittest, io, zipfile, tempfile
from pathlib import Path
import updater

class UpdaterTests(unittest.TestCase):
    def test_ci_fix_pin_prevents_downgrade_until_stable_catches_up(self):
        self.assertTrue(updater.keep_pin('v1.0.379', {'release_floor': [1, 0, 380]}))
        self.assertFalse(updater.keep_pin('v1.0.380', {'release_floor': [1, 0, 380]}))

    def test_mode_plugin_stays_disabled_until_selected(self):
        self.assertEqual(updater.target_path('matchzy', 'addons/counterstrikesharp/plugins/MatchZy/MatchZy.dll'), 'addons/counterstrikesharp/plugins/disabled/MatchZy/MatchZy.dll')
        self.assertFalse(updater.allowed('matchzy', 'cfg/MatchZy/config.cfg'))
        self.assertTrue(updater.allowed('matchzy', 'addons/counterstrikesharp/gamedata/matchzy.json'))

    def test_selects_cs2_metamod_branch_and_preserves_custom_config(self):
        releases=[{'tag_name':'1.12.0.1229','assets':[]},{'tag_name':'2.0.0.1483','assets':[{'name':'mmsource-2.0.0-git1483-linux.tar.gz','browser_download_url':'https://example.invalid/meta.tar.gz'}]}]
        self.assertEqual(updater.metamod_asset(releases)['name'],'mmsource-2.0.0-git1483-linux.tar.gz')
        self.assertTrue(updater.allowed('css','addons/counterstrikesharp/api/CounterStrikeSharp.API.dll'))
        self.assertFalse(updater.allowed('css','addons/counterstrikesharp/configs/core.json'))
        self.assertFalse(updater.allowed('metamod','addons/metamod/metaplugins.ini'))
        with self.assertRaises(ValueError):
            updater.safe_path('../escape')

if __name__=='__main__': unittest.main()
