import copy
import unittest
from hermesaki.bootstrap import configure_container_logging


class Logging(unittest.TestCase):
    def test_container_logging_is_idempotent_and_preserves_custom_tracers(self):
        class Provider:
            def __init__(self):
                self.tracers = [
                    {'id': 'default', '@type': 'Log', 'path': '/var/log/stalwart/', 'enable': True},
                    {'id': 'custom', '@type': 'Log', 'path': '/persistent/logs/', 'enable': True},
                ]
                self.calls = []
            def list(self, kind):
                return copy.deepcopy(self.tracers)
            def call(self, method, data):
                self.calls.append(data)
                for value in data.get('create', {}).values():
                    self.tracers.append(dict(value, id='console'))
                for key, value in data.get('update', {}).items():
                    next(t for t in self.tracers if t['id'] == key).update(value)
        provider = Provider()
        configure_container_logging(provider)
        configure_container_logging(provider)
        self.assertEqual(len(provider.calls), 2)
        self.assertFalse(provider.tracers[0]['enable'])
        self.assertTrue(provider.tracers[1]['enable'])
        self.assertEqual(provider.tracers[2]['level'], 'info')
        self.assertEqual(provider.tracers[2]['@type'], 'Stdout')
