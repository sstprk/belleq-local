"""Generate 1/2/3-worker configurations with NEW collections, never deletes data."""
import argparse
import json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--workers',type=int,choices=[1,2,3],required=True)
p.add_argument('--run',required=True,help='unique alphanumeric run label')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if not a.run.replace('_','').isalnum(): p.error('run label must be alphanumeric/underscore')
a.output.mkdir(parents=True,exist_ok=False)
root=Path(__file__).resolve().parents[1]
for i in range(1,5):
    s=json.loads((root/f'config/mini-{i}.json').read_text())
    s['collection']=f'lab_{a.run}_n{a.workers}'
    if i==1:
        s['nodes']=s['nodes'][:a.workers]
        s['retrieval_mode']='broadcast'  # worker-count baseline; routing is a separate experiment
    (a.output/f'mini-{i}.json').write_text(json.dumps(s,indent=2)+'\n')
print(f'Copy each config onto matching mini as config/local.json; restart services. Collection: {s["collection"]}')
