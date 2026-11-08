"""Upload the archived categorical corpus, checking the original book hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,default=ROOT/'config/categorical/corpus.json')
    p.add_argument('--books',type=Path,default=ROOT/'simulator/data/raw/oct12/books')
    p.add_argument('--config-dir',type=Path,default=ROOT/'config/categorical')
    a=p.parse_args()
    with httpx.Client(timeout=600,trust_env=False,
                      headers={'X-API-Key':os.getenv('BELLEQ_API_KEY','')}) as c:
        for book in json.loads(a.corpus.read_text()):
            path=a.books/(book['book_id']+'.txt');raw=path.read_bytes()
            # Downloaded originals and cleaned upload files have separate hashes.
            if hashlib.sha256(raw).hexdigest()!=book['upload_sha256']:
                raise ValueError(f'Book bytes differ from the corpus manifest: {path.name}')
            cfg=json.loads((a.config_dir/(book['node_id']+'.json')).read_text())
            base=f"http://{cfg['bind']}:{cfg['port']}"
            r=c.post(base+'/v1/documents/upload',files={'file':(path.name,raw)})
            r.raise_for_status()
            result=r.json()
            if result['doc_id']!=book['doc_id'] or result['chunks']!=book['chunks']:
                raise ValueError(f'Ingestion identity/chunk count differs: {path.name}')
            print(json.dumps({'book_id':book['book_id'],'node_id':book['node_id'],**result}),flush=True)


if __name__=='__main__':main()
