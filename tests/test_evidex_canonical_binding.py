import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
SOURCE=HERE/'payload'
if not SOURCE.exists():SOURCE=HERE

def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
 sys.modules[name]=module;spec.loader.exec_module(module);return module

class CanonicalBindingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)/'DIO';self.root.mkdir()
  self.engine=self.root/'cross_folder_variants/Evidex/A_CODE';self.engine.mkdir(parents=True)
  for rel in ['sovereign_runtime.py','cross_folder_variants/Evidex/A_CODE/src/evidence_pack_engine/epistemic_authority.py']:
   dest=self.root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SOURCE/rel,dest)
  (self.root/'scripts').mkdir();(self.root/'products').mkdir()
  spine=HERE/'baseline/scripts/dio_epistemic_spine.py'
  if not spine.exists():spine=HERE/'scripts/dio_epistemic_spine.py'
  shutil.copy2(spine,self.root/'scripts/dio_epistemic_spine.py')
  self.env=patch.dict(os.environ,{'DIO_SOVEREIGN_ENV_FILE':str(self.root/'absent.env'),'DIO_EVIDEX_ROOT':'','DIO_ROOT':str(self.root)},clear=True);self.env.start();self.addCleanup(self.env.stop)
  self.runtime=load(self.root/'sovereign_runtime.py','tested_runtime')
  self.authority=load(self.engine/'src/evidence_pack_engine/epistemic_authority.py','tested_authority')
 def test_missing_virtualenv_never_changes_source_owner(self):
  self.assertEqual(self.runtime.evidex_root(),self.engine)
 def test_external_explicit_root_is_refused(self):
  with patch.dict(os.environ,{'DIO_EVIDEX_ROOT':str(self.root.parent/'Evidex')}):
   with self.assertRaises(RuntimeError):self.runtime.evidex_root()
 def test_external_symlink_is_refused(self):
  shutil.rmtree(self.engine);outside=self.root.parent/'external';outside.mkdir();self.engine.symlink_to(outside,target_is_directory=True)
  with self.assertRaises(RuntimeError):self.runtime.evidex_root()
 def test_engine_environment_drops_foreign_import_roots_and_sets_canonical_spine_owner(self):
  env=self.runtime.evidex_environment({'PYTHONPATH':'/foreign/DIO:/foreign/BEAST','DIO_ROOT':'/foreign/DIO','KEEP_SENTINEL':'yes'})
  self.assertEqual(env['DIO_ROOT'],str(self.root));self.assertEqual(env['KEEP_SENTINEL'],'yes')
  self.assertEqual(env['PYTHONPATH'].split(os.pathsep),[str(self.engine/'src'),str(self.root),str(self.root/'products')])
 def test_spine_cannot_come_from_cached_foreign_module(self):
  import types
  fake=types.ModuleType('scripts.dio_epistemic_spine');fake.claim_epistemic_state=lambda *a,**k:'FORGED';fake.epistemic_tokens=lambda:('FORGED',)
  with patch.dict(sys.modules,{'scripts.dio_epistemic_spine':fake}):
   spine=self.authority._load_spine();self.assertEqual(Path(spine.__file__).resolve(),self.root/'scripts/dio_epistemic_spine.py');self.assertNotIn('FORGED',spine.epistemic_tokens())
 def test_spine_root_outside_engine_owner_is_refused(self):
  with patch.dict(os.environ,{'DIO_ROOT':str(self.root.parent)}):
   with self.assertRaises(RuntimeError):self.authority._load_spine()
 def test_missing_or_symlinked_spine_is_refused(self):
  p=self.root/'scripts/dio_epistemic_spine.py';p.unlink()
  with self.assertRaises((RuntimeError,FileNotFoundError)):self.authority._load_spine()
  other=self.root.parent/'foreign.py';other.write_text('');p.symlink_to(other)
  with self.assertRaises((RuntimeError,FileNotFoundError)):self.authority._load_spine()

 def test_real_runner_subprocess_loads_owned_engine_and_spine(self):
  import json
  dest=self.root/'scripts/run_evidex_jobs.py';shutil.copy2(SOURCE/'scripts/run_evidex_jobs.py',dest)
  package=self.engine/'src/evidence_pack_engine';(package/'__init__.py').write_text('')
  (package/'cli.py').write_text("import json\nfrom pathlib import Path\nfrom .epistemic_authority import _load_spine\nprint(json.dumps({'engine':str(Path(__file__).resolve()),'spine':str(Path(_load_spine().__file__).resolve())}))\n")
  python=self.engine/'.venv/bin/python';python.parent.mkdir(parents=True);python.symlink_to(sys.executable)
  with patch.dict(sys.modules,{'sovereign_runtime':self.runtime}),patch.dict(os.environ,{'PYTHONPATH':'/foreign/DIO'}):
   runner=load(dest,'tested_runner')
   receipt=runner.run_evidex({'job_id':'SYNTHETIC','created_at':'2026-10-20','route':{'product':'evidex','reason':'test','confidence':1},'inputs':[],'evidence':[]},self.root/'out')
  self.assertEqual(receipt['returncode'],0,receipt['stderr'])
  observed=json.loads(receipt['stdout']);self.assertEqual(observed['engine'],str(package/'cli.py'));self.assertEqual(observed['spine'],str(self.root/'scripts/dio_epistemic_spine.py'))
 def test_prepared_compatibility_environment_uses_same_canonical_binding(self):
  import ast
  tree=ast.parse((SOURCE/'products/professional_evidence_red13_compat.py').read_text())
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_spine_environment')
  ns={'Path':Path,'os':os}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'prepared_compatibility','exec'),ns)
  with patch.dict(sys.modules,{'sovereign_runtime':self.runtime}):env,roots=ns['_spine_environment']({'PYTHONPATH':'/foreign/BEAST'})
  self.assertEqual(roots,[str(self.engine/'src'),str(self.root),str(self.root/'products')]);self.assertEqual(env['DIO_ROOT'],str(self.root))

if __name__=='__main__':unittest.main()
