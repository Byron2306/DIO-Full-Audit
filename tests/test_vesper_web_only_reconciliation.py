import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_dio_web_only_sync_test',ROOT/'scripts/sync_vesper_presence_edge.py')
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)


class WebOnlyReconciliationTests(unittest.TestCase):
    def config(self,folder):
        p=Path(folder)/'transport-token';p.write_text('synthetic-test-token')
        return {'edge_token_path':str(p),'base_url':'https://example.invalid','core_url':'http://127.0.0.1:8787'}

    def test_web_only_does_not_pull_or_process_telegram_or_signed_lanes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sync,'edge_request',return_value={'events':[]}) as edge:
            result=sync.sync_once(self.config(tmp),web_only=True)
        self.assertEqual(result['web_received'],0)
        self.assertEqual(result['telegram_received'],0)
        self.assertEqual(result['signed_received'],0)
        self.assertEqual([c.args[0] for c in edge.call_args_list],['https://example.invalid/api/presence/web-events?limit=100'])

    def test_default_preserves_three_transport_lanes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sync,'edge_request',return_value={'events':[]}) as edge:
            sync.sync_once(self.config(tmp))
        urls=[c.args[0] for c in edge.call_args_list]
        self.assertEqual(len(urls),3)
        self.assertTrue(any('/telegram-events?' in u for u in urls))
        self.assertTrue(any('/web-events?' in u for u in urls))


if __name__=='__main__':unittest.main()
