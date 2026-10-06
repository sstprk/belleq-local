"""Merge routing catalogue into existing coordinator config, preserving local settings."""
import argparse
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--config',type=Path,default=ROOT/'config/local.json')
p.add_argument('--threshold',type=float,default=.70)
a=p.parse_args()
if not -1 <= a.threshold <= 1: p.error('threshold must be between -1 and 1')
c=json.loads(a.config.read_text())
if not c.get('coordinator'): p.error('Run on coordinator only')
template=json.loads((ROOT/'config/mini-1.json').read_text())
catalogue={n['id']:n['description'] for n in template['nodes']}
for n in c['nodes']:
    if n['id'] not in catalogue: p.error(f'Unknown node {n["id"]}; set its description manually')
    n['description']=catalogue[n['id']]
c['retrieval_mode']='semantic_sequential'; c['relevance_threshold']=a.threshold
backup=a.config.with_suffix(a.config.suffix+'.before-routing')
if backup.exists(): p.error(f'Backup already exists: {backup}; edit config manually or archive backup')
backup.write_bytes(a.config.read_bytes()); backup.chmod(0o600)
a.config.write_text(json.dumps(c,indent=2)+'\n')
print(f'Routing enabled; restart coordinator. Backup: {backup}')
print('Threshold is an uncalibrated score cutoff, not proof of answer relevance.')
