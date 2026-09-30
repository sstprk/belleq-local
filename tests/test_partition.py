import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_same_corpus_disjoint_assignment_across_worker_counts(tmp_path):
    corpus=tmp_path/'corpus'; corpus.mkdir()
    for i in range(7): (corpus/f'{i}.txt').write_text(f'document {i}')
    (corpus/'duplicate.txt').write_text('document 0')
    hashes=[]
    for count in (1,2,3):
        output=tmp_path/f'n{count}.json'
        nodes=[f'mini-{i+2}' for i in range(count)]
        subprocess.run([sys.executable,str(ROOT/'scripts/partition.py'),str(corpus),
                        '--nodes',*nodes,'--output',str(output)],check=True)
        data=json.loads(output.read_text())
        hashes.append(data['corpus_id'])
        assert len(data['files'])==7
        assert len({f['sha256'] for f in data['files']})==7
        assert {f['node_id'] for f in data['files']}==set(nodes)
    assert len(set(hashes))==1
