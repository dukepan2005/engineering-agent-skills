import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('boards_inventory', Path(__file__).parents[1] / 'scripts/azure_devops_boards.py')
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class InventoryTests(unittest.TestCase):
    def test_inventory_reads_predecessor_outside_sprint_and_preserves_states(self):
        class Client:
            def sprint_item_ids(self, iteration): return [1]
            def read(self, item_id):
                if item_id == 1:
                    return {'id': 1, 'fields': {'System.IterationPath': 'P\\S', 'System.State': 'Active'}, 'relations': [{'rel': module.RELATIONS['predecessor'], 'url': 'https://example/_apis/wit/workItems/2'}]}
                return {'id': 2, 'fields': {'System.State': 'Closed'}}
        output = io.StringIO()
        with patch.object(module, 'sprint', return_value='P\\S'), patch.object(module, 'connect', return_value=(Client(), None)), contextlib.redirect_stdout(output):
            module.sprint_inventory(SimpleNamespace())
        result = json.loads(output.getvalue())
        self.assertEqual(result['items'][0]['state'], 'Active')
        self.assertEqual(result['predecessors'][0]['state'], 'Closed')

    def test_changed_iteration_fails(self):
        class Client:
            def sprint_item_ids(self, iteration): return [1]
            def read(self, item_id): return {'id': 1, 'fields': {'System.IterationPath': 'P\\other'}}
        with patch.object(module, 'sprint', return_value='P\\S'), patch.object(module, 'connect', return_value=(Client(), None)):
            with self.assertRaisesRegex(RuntimeError, 'changed or was omitted'):
                module.sprint_inventory(SimpleNamespace())

    def test_query_rejects_injection_and_limit(self):
        class Response:
            def json(self): return {'workItems': [{'id': i} for i in range(20000)]}
        class Api:
            def _send(self, **kwargs): return Response()
        client = module.AzureClient(Api(), 'P')
        with self.assertRaisesRegex(RuntimeError, 'Invalid iteration'):
            client.sprint_item_ids("P\\S' OR 1=1")
        with self.assertRaisesRegex(RuntimeError, 'limit'):
            client.sprint_item_ids('P\\S')

if __name__ == '__main__': unittest.main()
