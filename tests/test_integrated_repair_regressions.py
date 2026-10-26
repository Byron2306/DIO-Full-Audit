"""Regression coverage for reproduced integrated-checkpoint defects; no provider calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('name', ['document_studio_ollama_bridge.py', 'run_evidex_jobs.py', 'run_evidex_transaction_loop.py', 'run_homs_hymark_batch.py'])
def test_clean_filename_entrypoints_bind_repository_imports(tmp_path, name):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (scripts / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
    (tmp_path / 'sovereign_runtime.py').write_text('from pathlib import Path\ndef evidex_root(): return Path("/nonexistent")\ndef evidex_environment(base=None): return dict(base or {})\ndef ollama_model(v=None): return v or "local-test"\ndef ollama_url(v=None): return v or "http://127.0.0.1:11434"\ndef require_ollama_provider(*a, **k): return "ollama"\n')
    code = 'import runpy,sys; scope=runpy.run_path(sys.argv[1],run_name="import_probe"); '
    if name == 'run_homs_hymark_batch.py':
        code += 'scope["configure_provider"](__import__("pathlib").Path("/nonexistent"), "ollama", "local-test"); '
    code += 'print("IMPORT_OK")'
    result = subprocess.run([sys.executable, '-I', '-c', code, str(scripts / name)], cwd=tmp_path, capture_output=True, text=True, timeout=15, env={'PATH':os.environ.get('PATH','/usr/bin:/bin')})
    assert result.returncode == 0, result.stderr
    assert 'IMPORT_OK' in result.stdout

@pytest.mark.parametrize('passed', [False, None, 'true'])
def test_failed_or_missing_cached_music_rights_are_not_reused(tmp_path, monkeypatch, passed):
    import scripts.lingua_music_projection as music
    episode = tmp_path / 'episodes' / 'warm_education'
    choices = episode / 'imports/music_choices'
    choices.mkdir(parents=True)
    (episode / 'imports/music_bed.ogg').write_bytes(b'audio')
    (episode / 'imports/MUSIC_ATTRIBUTION.md').write_text('CC BY 4.0')
    (choices / 'COMMERCIAL_MUSIC_RECEIPT.json').write_text(json.dumps({'selected': {'licence_name':'CC BY 4.0','rights':{'passed':passed}}}))
    monkeypatch.setattr(music, 'FOUNDRY', tmp_path)
    assert music._catalog() == []


def test_passed_cached_music_rights_can_be_reused(tmp_path, monkeypatch):
    import scripts.lingua_music_projection as music
    episode=tmp_path/'episodes/a'; choices=episode/'imports/music_choices'; choices.mkdir(parents=True)
    (episode/'imports/music_bed.ogg').write_bytes(b'audio')
    (episode/'imports/MUSIC_ATTRIBUTION.md').write_text('CC BY 4.0')
    (choices/'COMMERCIAL_MUSIC_RECEIPT.json').write_text(json.dumps({'selected':{'licence_name':'CC BY 4.0','rights':{'passed':True}}}))
    monkeypatch.setattr(music,'FOUNDRY',tmp_path)
    assert len(music._catalog()) == 1


def test_identity_count_and_extension_label_do_not_certify_product_grade(tmp_path, monkeypatch):
    import scripts.serve_canonical_portfolio as catalog
    products=[{'product_id':f'p{i}', 'name':f'P{i}'} for i in range(68)]
    monkeypatch.setattr(catalog,'build_commercial_pricing_registry',lambda root:{'products':products})
    snapshot=tmp_path/'snapshot.json'; snapshot.write_text(json.dumps({'incarnations':[{}]*68,'extension_summary_state':'VERIFIED'}))
    monkeypatch.setattr(catalog,'SNAPSHOT',snapshot)
    state=catalog.portfolio_state()
    assert state['identity_registry_complete'] is True
    assert state['product_grade_verified'] is False
    assert state['external_release_authorized'] is False


def test_health_false_or_wrong_service_is_unavailable(monkeypatch):
    import dio_launcher as launcher
    monkeypatch.setattr(launcher,'probe_url',lambda url, **kw:{'ready':True,'status':200,'payload':{'ok':False,'service':'unrelated'}})
    state=launcher.launcher_state()
    assert state['surfaces_ready'] is False
    assert all(row['ready'] is False for row in state['surfaces'])


def test_portfolio_count_strings_and_bad_types_do_not_crash_or_certify():
    from dio_launcher import portfolio_truth
    for count in ['garbage', {}, True, 53.5]:
        result=portfolio_truth({'base_canonical_incarnation_count':count})
        assert result['verified'] is False


def test_valid_dashboard_access_is_separate_from_portfolio_proof(monkeypatch):
    import dio_launcher as launcher
    payloads={'/api/control-deck/portfolio':{'schema':'dio.control_deck.portfolio_snapshot.v1'},'/api/business/health':{'ok':True,'service':'dio-business'},'/api/market/health':{'ok':True,'service':'dio-market-command'},'/api/business/portfolio':{}}
    from urllib.parse import urlsplit
    monkeypatch.setattr(launcher,'probe_url',lambda url, **kw:{'ready':True,'payload':payloads.get(urlsplit(url).path,{})})
    monkeypatch.setattr(launcher,'canonical_catalog_state',lambda:{'available':False})
    state=launcher.launcher_state()
    assert state['surfaces_ready'] is True
    assert state['inspection_available'] is True
    assert state['portfolio']['verified'] is False
    assert state['ready'] is False


def test_full_identity_counts_are_not_execution_proofs():
    from dio_launcher import portfolio_truth
    result=portfolio_truth({'base_canonical_incarnation_count':53, 'canon_extension_count':15,'canonical_incarnation_count':68,'extension_summary_state':'VERIFIED','incarnations':[{}]*68})
    assert result['verified'] is False
    assert result['identity_counts_complete'] is True


def test_bridge_filename_executes_against_bounded_local_provider(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    captured=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_POST(self):
            captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body=json.dumps({'model':'fixture-model','response':json.dumps({'document_summary':'fixture result','edits':[],'translations':[],'glossary':[],'qa_flags':[]})}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/document_studio_ollama_bridge.py')],input=json.dumps({'base_url':f'http://127.0.0.1:{server.server_port}','model':'fixture-model','prompt':'fixture'}),text=True,capture_output=True,cwd=tmp_path,timeout=15,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'DIO_SOVEREIGN_ENV_FILE':'/dev/null'})
        assert result.returncode == 0,result.stderr
        response=json.loads(result.stdout)
        assert response['status']=='ok' and response['model']=='fixture-model'
        assert response['release_authority'] is False
        assert captured[0]['model']=='fixture-model'
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

@pytest.mark.parametrize('snapshot',[[],{'incarnations':'not-a-list'},{'incarnations':[7]}])
def test_invalid_runtime_projection_is_reported_without_crashing(tmp_path,monkeypatch,snapshot):
    import scripts.serve_canonical_portfolio as catalog
    monkeypatch.setattr(catalog,'build_commercial_pricing_registry',lambda root:{'products':[{'product_id':f'p{i}','name':f'P{i}'} for i in range(68)]})
    path=tmp_path/'snapshot';path.write_text(json.dumps(snapshot));monkeypatch.setattr(catalog,'SNAPSHOT',path)
    assert catalog.portfolio_state()['runtime']['extension_summary_state']=='INVALID'


def test_sophia_binding_preserves_existing_backend_and_services_package(tmp_path):
    other=tmp_path/'other';services=other/'backend/services';services.mkdir(parents=True)
    (other/'backend/__init__.py').write_text('sentinel = "other-backend"\n')
    (services/'__init__.py').write_text('sentinel = "other-services"\n')
    sophia=tmp_path/'sophia';target=sophia/'arda_os/backend/services';target.mkdir(parents=True)
    for name in ('academic_retrieval','sophia_academic_claim_tools','sophia_source_support'):
        (target/(name+'.py')).write_text('value="sophia"\n')
    code='import sys;sys.path[:0]=sys.argv[1:3];from pathlib import Path;import backend,backend.services;import adapters.sophia.canonical_sources as sources;sources.ORGAN_ROOT=Path(sys.argv[3]).resolve();from adapters.sophia.review_pipeline import bind_sophia_backend;bind_sophia_backend(Path(sys.argv[3]));from backend.services import academic_retrieval;assert backend.sentinel=="other-backend";assert backend.services.sentinel=="other-services";assert academic_retrieval.value=="sophia"'
    result=subprocess.run([sys.executable,'-I','-c',code,str(ROOT),str(other),str(sophia)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_startup_guard_holds_split_mount_and_state(tmp_path):
    from scripts.verify_integrated_runtime import verify, EXPECTED_UUID
    repo=tmp_path/'repo';repo.mkdir();state=tmp_path/'state';state.mkdir();(state/'telemetry').mkdir()
    (repo/'state').symlink_to(state);(repo/'telemetry').symlink_to(state/'telemetry')
    verify(repo,state,EXPECTED_UUID,EXPECTED_UUID,EXPECTED_UUID)
    with pytest.raises(RuntimeError,match='data volume'):
        verify(repo,state,'wrong-volume',EXPECTED_UUID,EXPECTED_UUID)
    with pytest.raises(RuntimeError,match='state directory'):
        verify(repo,state,EXPECTED_UUID,'wrong-volume',EXPECTED_UUID)
    with pytest.raises(RuntimeError,match='telemetry directory'):
        verify(repo,state,EXPECTED_UUID,EXPECTED_UUID,'wrong-volume')
    (repo/'state').unlink();(repo/'state').mkdir()
    with pytest.raises(RuntimeError,match='state binding'):
        verify(repo,state,EXPECTED_UUID,EXPECTED_UUID,EXPECTED_UUID)
