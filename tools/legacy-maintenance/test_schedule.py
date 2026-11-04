import unittest
import scheduled_update

class SafetyTests(unittest.TestCase):
    def test_only_empty_server_allows_restart(self):
        self.assertEqual(scheduled_update.humans('players  : 0 humans, 10 bots (64 max)'), 0)
        self.assertEqual(scheduled_update.humans('players  : 1 humans, 0 bots (64 max)'), 1)
        self.assertIsNone(scheduled_update.humans('server not ready'))

if __name__ == '__main__': unittest.main()
