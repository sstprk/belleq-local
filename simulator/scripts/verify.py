"""Run numerical/invariant tests, real localhost API checks, and source integrity checks."""
from pathlib import Path
import io
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from belleq_sim.common import ROOT,write_json,sha256,event

def main():
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (ROOT/'results/unit_tests.log').write_text(stream.getvalue())
    assert result.wasSuccessful(),stream.getvalue()
    manifest=json.loads((ROOT/'data/source_manifest.json').read_text())
    for entry in manifest:
        assert sha256(ROOT/entry['snapshot_path'])==entry['sha256'],entry['snapshot_path']
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
    checks=[]
    with (ROOT/'results/api_smoke.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-m','belleq_sim','serve','--port',str(port)],cwd=ROOT,
                               env=env,stdout=log,stderr=log)
        base=f'http://127.0.0.1:{port}'
        try:
            for _ in range(50):
                try:
                    with urlopen(base+'/health',timeout=1) as r:assert json.load(r)['status']=='ok'
                    break
                except URLError:time.sleep(.1)
            else:raise RuntimeError('API failed to start; inspect api_smoke.log')
            checks.append('GET /health -> 200')
            for path,mime,needle in [('/','text/html','scenario-form'),
                    ('/style.css','text/css','.workspace'),('/app.js','text/javascript','/v1/simulate')]:
                with urlopen(base+path,timeout=5) as r:
                    assert mime in r.headers['Content-Type'] and needle in r.read().decode()
            checks.append('GET interface HTML/CSS/JS -> 200; correct content types')
            try:urlopen(base+'/../artifacts/calibration.json',timeout=5)
            except HTTPError as e:assert e.code==404
            else:raise AssertionError('Private research files exposed as static assets')
            checks.append('Non-whitelisted files are not served')
            with urlopen(base+'/v1/model',timeout=5) as r:
                assert json.load(r)['unseen_node_count_validated'] is False
            checks.append('GET /v1/model -> truthful scope')
            def post(path,value):
                return urlopen(Request(base+path,json.dumps(value).encode(),{'Content-Type':'application/json'}),timeout=15)
            with post('/v1/simulate',dict(method='broadcast',nodes=3,draws=30)) as r:
                d=json.load(r);assert d['summary']['visited_nodes']['mean']==3 and 'samples' not in d
                assert (ROOT/'results/ui_runs'/d['run_id']/'samples.csv').exists()
                assert d['record_type']=='simulation_not_physical_measurement'
            checks.append('POST native simulation -> 200; bounded summary')
            with post('/v1/simulate',dict(mode='assumption',method='broadcast',nodes=8,draws=30)) as r:
                d=json.load(r);assert d['reference_hit_rate'] is None and d['evidence_level']=='unvalidated_user_assumptions'
            checks.append('POST extrapolation -> explicit assumptions; no invented quality')
            with post('/v1/predict',dict(method='broadcast',question='What did Holmes discover?')) as r:
                assert json.load(r)['predictions']['aggregate_ms']>0
            checks.append('POST trained prediction -> 200')
            try:post('/v1/simulate',dict(nodes=8,draws=10))
            except HTTPError as e:assert e.code==422
            else:raise AssertionError('Unsupported empirical setting accepted')
            checks.append('Unsupported empirical configuration -> 422')
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    verification=dict(unit_tests=result.testsRun,unit_failures=len(result.failures),unit_errors=len(result.errors),
                      api_checks=checks,raw_files_sha256_verified=len(manifest),status='passed')
    write_json(ROOT/'results/verification.json',verification)
    event('07_verification_complete',**verification)
    print(json.dumps(verification,indent=2))

if __name__=='__main__':main()
