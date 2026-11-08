"""Exercise real HTTP requests against the deployable handler before publishing."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from preview import PreviewHandler

ROOT = Path(__file__).resolve().parents[1]
server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f'http://127.0.0.1:{server.server_port}'
checks = []


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(base+path, data=body, headers={'Content-Type':'application/json'})
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, response.read()
    except HTTPError as response:
        return response.code, response.read()


def check(name, condition):
    assert condition, name
    checks.append(name)


try:
    for path in ['/', '/app.js', '/style.css', '/health', '/v1/model', '/api/index?endpoint=model']:
        status, body = request(path)
        check('GET '+path, status==200 and len(body)>10)
    configs = [
        {'method':'broadcast','mode':'empirical','nodes':3},
        {'method':'semantic_sequential','mode':'empirical','nodes':3},
        {'method':'random_sequential','mode':'empirical','nodes':3},
        {'method':'single_db','mode':'empirical','nodes':1},
        {'method':'semantic_sequential','mode':'trace','nodes':3,'threshold':.8},
        {'method':'broadcast','mode':'assumption','nodes':8},
        {'method':'semantic_sequential','mode':'assumption','nodes':8,
         'semantic_owner_first_probability':.57},
    ]
    for config in configs:
        status, body = request('/v1/simulate', dict(config,draws=1000))
        data = json.loads(body)
        check('simulate '+config['method']+' '+config['mode'],
              status==200 and data['summary']['retrieval_ms']['mean']>0
              and data['summary']['network_frame_bytes']['mean']>0
              and data['persistence']=='download_only' and 'samples' not in data)
        if config['mode']=='assumption':
            check('assumption quality suppressed', data['reference_hit_rate'] is None)
    status, body = request('/api/index?endpoint=simulate', {'draws':1000})
    check('rewritten POST', status==200)
    baseline = json.loads(body)
    check('native expected values', 330<baseline['summary']['retrieval_ms']['mean']<350
          and 18000<baseline['summary']['network_frame_bytes']['mean']<19500)
    status, body = request('/v1/predict', {'question':'What did Holmes discover?','method':'broadcast'})
    check('point prediction', status==200 and 'predictions' in json.loads(body))
    for payload in [{'draws':20001}, {'nodes':8}, {'draws':0}, [], {'threshold':'bad'}]:
        check('invalid input '+str(payload),request('/v1/simulate',payload)[0]==422)
    check('unknown path',request('/not-found')[0]==404)
    output = ROOT/'tests/local_checks.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'time_utc':datetime.now(timezone.utc).isoformat(),
        'status':'passed','checks':checks,'real_vercel_deployment_tested':False},indent=2))
    print(f'{len(checks)} HTTP checks passed. Native example: '
          f"{baseline['summary']['retrieval_ms']['mean']:.1f} ms, "
          f"{baseline['summary']['network_frame_bytes']['mean']/1000:.2f} kB.")
finally:
    server.shutdown()
    server.server_close()
