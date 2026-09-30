"""Stable corpus manifest and disjoint file assignment; no uploads or deletions."""
import argparse
import hashlib
import json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('corpus',type=Path)
p.add_argument('--nodes',nargs='+',required=True,help='mini-2 [mini-3 mini-4]')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if len(set(a.nodes))!=len(a.nodes): p.error('duplicate nodes')
files=[]
for f in sorted(a.corpus.rglob('*')):
    if f.is_file() and f.suffix.lower() in {'.pdf','.txt','.md','.docx','.html'}:
        sha=hashlib.sha256(f.read_bytes()).hexdigest()
        files.append({'path':str(f.relative_to(a.corpus)), 'sha256':sha, 'bytes':f.stat().st_size})
# Deduplicate identical files; round robin over stable hash order balances file count.
unique={}
for f in files: unique.setdefault(f['sha256'],f)
ordered=sorted(unique.values(),key=lambda f:(f['sha256'],f['path']))
for i,f in enumerate(ordered): f['node_id']=a.nodes[i%len(a.nodes)]
corpus_id=hashlib.sha256('\n'.join(f['sha256'] for f in ordered).encode()).hexdigest()
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'corpus_id':corpus_id,'nodes':a.nodes,'files':ordered},indent=2))
print(f'{len(ordered)} unique files; corpus_id={corpus_id}')
print('Balances file count, not chunk count. Record observed chunk counts after ingestion.')
