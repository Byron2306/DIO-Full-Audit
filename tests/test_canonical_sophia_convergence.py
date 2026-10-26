import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EMBEDDED = Path('cross_folder_variants/Integritas-Mechanicus/A_CODE/arda_os/backend/services')


class CanonicalConvergenceTests(unittest.TestCase):
    def sources(self):
        self.assertIsNotNone(importlib.util.find_spec('adapters.sophia.canonical_sources'),
                             'canonical-only source resolver is missing')
        from adapters.sophia import canonical_sources
        return canonical_sources

    def test_custody_chain_executes_without_donor_repositories(self):
        source = self.sources()
        evidence = source.load_service('response_evidence')
        custody = source.load_service('sophia_custody')
        import hashlib
        digest = lambda b: hashlib.sha256(b).hexdigest()
        prompt = 'Review [P1].'; response = '[P1] needs evidence.'; model = 'granite3.3:2b'
        receipt = evidence.examine(prompt=prompt, response=response, model=model)
        values = {'manuscript':b'original', 'rubric':b'{}', 'zpd_guidance':b'advisory',
                  'prompt':prompt.encode(), 'response':response.encode()}
        result = custody.verify_custody(manuscript=values['manuscript'], rubric=values['rubric'],
            zpd_guidance=values['zpd_guidance'], prompt=prompt, response=response,
            requested_model=model, actual_model=model, receipt=receipt,
            expected_digests={k:digest(v) for k,v in values.items()})
        self.assertTrue(result['passed'])
        self.assertFalse(result['constitutional_release_authorized'])
        self.assertFalse(receipt['mandos_judgment']['passed'])
        self.assertFalse(receipt['article_conformity']['summary']['all_passed'])
        self.assertTrue(Path(custody.__file__).resolve().is_relative_to(ROOT))

    def test_changed_response_is_refused(self):
        source=self.sources();evidence=source.load_service('response_evidence')
        receipt=evidence.examine(prompt='[P1]',response='[P1] needs evidence.',model='granite3.3:2b')
        self.assertFalse(evidence.verify(receipt,prompt='[P1]',response='substituted',model='granite3.3:2b'))

    def test_clean_interpreter_ignores_home_and_poisoned_backend(self):
        self.sources()
        code='''import sys,types,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
sys.modules['backend']=types.ModuleType('backend')
from adapters.sophia.canonical_sources import load_service
m=load_service('sophia_custody')
print(json.dumps({'source':m.__file__,'owned':Path(m.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())}))
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.run([sys.executable,'-I','-c',code,str(ROOT)],cwd=tmp,
                env={**os.environ,'HOME':tmp,'PYTHONPATH':'/does-not-exist'},capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue(json.loads(p.stdout)['owned'])

    def sandbox(self, base):
        root=Path(base)/'repo'
        for rel in ['adapters/sophia/canonical_sources.py', *[str(EMBEDDED/(n+'.py')) for n in
                    ('response_evidence','sophia_custody','mandos_sophia_adapter','mandos_protocol_judge')]]:
            target=root/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
        return root

    def test_tampered_canonical_source_refuses(self):
        self.sources()
        with tempfile.TemporaryDirectory() as tmp:
            root=self.sandbox(tmp);p=root/EMBEDDED/'sophia_custody.py';p.write_text(p.read_text()+'\nTAMPER=True\n')
            code="import sys;sys.path.insert(0,sys.argv[1]);from adapters.sophia.canonical_sources import load_service;load_service('sophia_custody')"
            result=subprocess.run([sys.executable,'-I','-c',code,str(root)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('source_digest_mismatch',result.stderr)

    def test_missing_canonical_source_does_not_fallback_to_home(self):
        self.sources()
        with tempfile.TemporaryDirectory() as tmp:
            root=self.sandbox(tmp);(root/EMBEDDED/'sophia_custody.py').unlink()
            donor=Path(tmp)/'Metatron/backend/services';donor.mkdir(parents=True)
            (donor/'sophia_custody.py').write_text('raise RuntimeError("DONOR_EXECUTED")')
            code="import sys;sys.path.insert(0,sys.argv[1]);from adapters.sophia.canonical_sources import load_service;load_service('sophia_custody')"
            result=subprocess.run([sys.executable,'-I','-c',code,str(root)],env={**os.environ,'HOME':tmp},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('canonical_source_missing',result.stderr)
            self.assertNotIn('DONOR_EXECUTED',result.stderr)

    def test_mandos_source_judge_is_canonical_and_release_stays_held(self):
        m=self.sources().load_service('mandos_sophia_adapter')
        self.assertTrue(Path(m.SOURCE_JUDGE).is_relative_to(ROOT))
        result=m.assess(directive='Review [P1]',response='[P1] needs evidence.',model='granite3.3:2b',
            r2_receipt={},r3_receipt={},academic_grounding_passed=True)
        self.assertFalse(result['constitutional_release_authorized'])
        self.assertFalse(result['behavioral_passed'])

    def test_r3_bridge_uses_canonical_verifier_for_actual_artifacts(self):
        evidence=self.sources().load_service('response_evidence')
        from adapters.sophia.sophia_r3_boundary import capture,verify
        with tempfile.TemporaryDirectory() as tmp:
            document=Path(tmp)/'essay.txt';document.write_text('The [P1] claim needs evidence.')
            guidance=Path(tmp)/'zpd.json';guidance.write_text('{"advisory":true}')
            request={'homs_context':{'rubric':{'criteria':['evidence']}},'zpd_guidance_path':str(guidance)}
            prompt='Review [P1].';answer='[P1] needs evidence.';model='granite3.3:2b'
            pin=capture(request,document,prompt,model)
            result=verify(pin,request,{'response':answer,'model':model,
                'response_evidence':evidence.examine(prompt=prompt,response=answer,model=model)})
            self.assertTrue(result['passed'])
            self.assertEqual(result['source_owner'],'DIO-Full-Audit')
            self.assertTrue(Path(result['verifier_source_path']).is_relative_to(ROOT))
            document.write_text('substituted manuscript')
            changed=verify(pin,request,{'response':answer,'model':model,
                'response_evidence':evidence.examine(prompt=prompt,response=answer,model=model)})
            self.assertFalse(changed['passed'])

    def test_zpd_estimation_does_not_mutate_source_evidence(self):
        import copy
        path=ROOT/EMBEDDED/'zpd_shaper.py'
        spec=importlib.util.spec_from_file_location('_canonical_zpd_mutation_test',path)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        previous=list(sys.path)
        try:
            sys.path.insert(0,str(path.parent))
            spec.loader.exec_module(module)
        finally:sys.path[:]=previous
        for profile in ({'constructive_tension':0.2},{'payload':{'constructive_tension':0.2}}):
            calibration={'payload':{'cognitive_load':0.3}}
            before=copy.deepcopy((profile,calibration))
            module.ZPDShaper().estimate_zpd(resonance_profile=profile,calibration=calibration,
                current_topic='ownership evidence frustrated shared purpose')
            self.assertEqual((profile,calibration),before)

    def test_empty_homs_context_refuses_before_model_request(self):
        from unittest.mock import patch
        from adapters.sophia.review_pipeline import reviewer_commentary
        with tempfile.TemporaryDirectory() as tmp:
            document=Path(tmp)/'essay.md';document.write_text('A source claim needs clear evidence.')
            with patch('adapters.sophia.review_pipeline.fetch_json',return_value={'session_token':'synthetic'}), \
                 patch('adapters.sophia.review_pipeline.post_json',return_value={'response':'[P1] Evidence needed.'}) as post:
                result=reviewer_commentary('http://127.0.0.1:7070',
                    {'reasoned_review_approved':True,'reasoned_provider':'ollama','reasoned_model':'granite3.3:2b','homs_context':{}},
                    'Synthetic',document,document.read_text(),'plain_text',
                    {'status':'needs_revision','reference_entries':[],'in_text_citations':[]},[],[])
            self.assertEqual(post.call_count,0)
            self.assertIn('evidence incomplete',result['failure_reason'])


if __name__=='__main__':unittest.main()
