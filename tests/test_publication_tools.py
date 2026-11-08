import argparse
import json
import httpx
import pytest
from scripts.consolidate import consolidate
from scripts import evaluate
from scripts.fetch_research_data import import_archive


def test_dataset_import_rejects_checksum_before_parsing_archive(tmp_path):
    archive=tmp_path/'bad.tar.gz';archive.write_bytes(b'not an archive')
    (tmp_path/'data-release.json').write_text(json.dumps({'bytes':archive.stat().st_size,'sha256':'0'*64}))
    with pytest.raises(ValueError,match='SHA-256'):
        import_archive(archive,tmp_path)


def test_dataset_import_rejects_path_traversal(tmp_path):
    import hashlib,io,tarfile
    archive=tmp_path/'bad.tar.gz';bad='data/raw/../../../escape'
    content=b'payload';manifest=[{'snapshot_path':bad,'sha256':hashlib.sha256(content).hexdigest()}]
    with tarfile.open(archive,'w:gz') as tar:
        for name,data in [('simulator/data/source_manifest.json',json.dumps(manifest).encode()),('simulator/'+bad,content)]:
            item=tarfile.TarInfo(name);item.size=len(data);tar.addfile(item,io.BytesIO(data))
    (tmp_path/'data-release.json').write_text(json.dumps({'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
    with pytest.raises(ValueError,match='relative'):
        import_archive(archive,tmp_path)
    assert not (tmp_path/'escape').exists()


def test_consolidation_refuses_nonempty_destination():
    with httpx.Client(transport=httpx.MockTransport(
            lambda r:httpx.Response(200,json={'result':{'count':1}}))) as c:
        with pytest.raises(ValueError,match='empty'):
            consolidate(c,['http://source'],'http://destination','test')


def test_consolidation_refuses_incompatible_schema_before_upsert():
    methods=[]
    def handler(r):
        methods.append(r.method)
        result={'count':0} if r.url.path.endswith('/count') else {
            'points':[{'payload':{'fingerprint':r.url.host}}]}
        return httpx.Response(200,json={'result':result})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(ValueError,match='schemas'):
            consolidate(c,['http://source'],'http://destination','test')
    assert 'PUT' not in methods


@pytest.mark.asyncio
async def test_answer_runner_preserves_outputs_and_varies_seed(tmp_path,monkeypatch):
    cases=tmp_path/'questions.jsonl'
    cases.write_text('\n'.join(json.dumps(dict(case_id=f'q{i}',query=f'question {i}',
        expected_answer='reference',relevant_hashes=['gold'],reviewed=False)) for i in range(2)))
    calls=[]
    async def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json={'partial':False,'answer':'recorded answer',
            'generation_ms':50,'end_to_end_ms':60,'chunks':[{'content_hash':'gold'}],
            'nodes':[],'routing':{'visited_nodes':[],'skipped_nodes':[]},'timings':{'aggregate_ms':10}})
    original=httpx.AsyncClient
    monkeypatch.setattr(evaluate.httpx,'AsyncClient',lambda **kw:
        original(transport=httpx.MockTransport(handler),**kw))
    a=argparse.Namespace(queries=cases,output=tmp_path/'run',allow_draft=True,seed=42,
        timeout=2,warmup=0,repeat=1,top_k=3,per_node_k=5,mode='random_sequential',
        min_score=.7,nodes=['mini-2'],url='http://test/v1/answer',scenario='random_node_order')
    await evaluate.run(a)
    import csv
    rows=list(csv.DictReader((a.output/'queries.csv').open()))
    assert len(rows)==2 and len({c['random_seed'] for c in calls})==2
    assert all(r['answer']=='recorded answer' and r['hit_at_k']=='1' and r['generation_ms']=='50' for r in rows)
