import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class WebLauncherTests(unittest.TestCase):
    def module(self):
        path=ROOT/'scripts/run_canonical_vesper_web.py'
        self.assertTrue(path.is_file(),'canonical web reconciler launcher is missing')
        spec=importlib.util.spec_from_file_location('_canonical_web_launcher_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_existing_secret_loaded_only_from_canonical_core_process(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'42';p.mkdir()
            (p/'cmdline').write_bytes(('python3\0'+str(ROOT/'scripts/serve_presence_bridge.py')+'\0').encode())
            (p/'environ').write_bytes(b'DIO_PRESENCE_PUBLIC_SHARED_SECRET=synthetic-secret\0UNRELATED_SECRET=do-not-copy\0')
            result=module.core_public_secret(42,proc_root=Path(tmp))
        self.assertEqual(result,'synthetic-secret')

    def test_foreign_core_process_refused(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'42';p.mkdir()
            (p/'cmdline').write_bytes(b'python3\0/home/elsewhere/serve_presence_bridge.py\0')
            (p/'environ').write_bytes(b'DIO_PRESENCE_PUBLIC_SHARED_SECRET=must-not-use\0')
            with self.assertRaisesRegex(ValueError,'core_source_owner_mismatch'):
                module.core_public_secret(42,proc_root=Path(tmp))

    def test_missing_core_secret_refuses(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'42';p.mkdir()
            (p/'cmdline').write_bytes(('python3\0'+str(ROOT/'scripts/serve_presence_bridge.py')+'\0').encode())
            (p/'environ').write_bytes(b'UNRELATED_SECRET=do-not-copy\0')
            with self.assertRaisesRegex(ValueError,'public_signing_secret_missing'):
                module.core_public_secret(42,proc_root=Path(tmp))


if __name__=='__main__':unittest.main()
