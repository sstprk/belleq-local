"""Upload a deterministic manifest; fail on changed corpus or any failed upload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import httpx
p=argparse.ArgumentParser()
p.add_argument('corpus',type=Path); p.add_argument('manifest',type=Path)
p.add_argument('--config-dir',type=Path,default=Path('config'))
a=p.parse_args(); manifest=json.loads(a.manifest.read_text())
with httpx.Client(timeout=600,trust_env=False,headers={'x-api-key':os.getenv('BELLEQ_API_KEY','')}) as c:
    for f in manifest['files']:
        path=(a.corpus/f['path']).resolve()
        if not path.is_relative_to(a.corpus.resolve()): raise ValueError('Path escapes corpus')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=f['sha256']: raise ValueError(f'Corpus changed: {path}')
        conf=json.loads((a.config_dir/(f['node_id']+'.json')).read_text())
        base=f"http://{conf['bind']}:{conf['port']}"
        r=c.post(base+'/v1/documents/upload',files={'file':(path.name,raw)})
        r.raise_for_status()
        print(json.dumps({'path':f['path'],'node_id':f['node_id'],**r.json()}),flush=True)
