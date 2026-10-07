import pytest
from belleq_lab.evaluation import quality, distribution
from scripts.evaluate import summarize
from scripts.network_report import summarize_packets


def test_quality_ranking_missing_slots_and_duplicate_evidence():
    hits=[{'content_hash': h} for h in ['wrong','a','a']]
    q=quality(hits,['a','b'],3)
    assert q['hit_at_k']==1 and q['miss_at_k']==0
    assert q['precision_at_k']==1/3 and q['judged_recall_at_k']==.5
    assert q['reciprocal_rank_at_k']==.5
    assert quality([],['a'],3)['miss_at_k']==1
    assert quality([{'content_hash':'a'}],['a'],3)['precision_at_k']==1/3
    with pytest.raises(ValueError): quality([],[],3)


def test_failures_separate_skipped_not_miss():
    base={'phase':'measured','client_ms':10}
    ok={**base,'complete':True,**quality([{'content_hash':'a'}],['a'],3)}
    fail={**base,'complete':False}
    nodes=[{'phase':'measured','node_id':'mini-2','status':'skipped'},
           {'phase':'measured','node_id':'mini-2','status':'error'}]
    s=summarize([ok,fail],nodes)
    assert s['all_attempt_hit_rate']==.5
    assert s['quality_complete_only']['hit_at_k']==1
    assert s['nodes']['mini-2']['hit_rate_when_queried_and_observable'] is None


def test_capture_direction_window_and_no_double_count():
    packet={'frame.time_epoch':'11','frame.len':'100','frame.cap_len':'100',
            'ip.src':'192.168.50.11','ip.dst':'192.168.50.12',
            'tcp.analysis.ack_rtt':'.002','http.time':'.3'}
    s=summarize_packets([packet,{**packet,'frame.time_epoch':'99'}],10,12)
    assert s['unique_captured_bytes']==100
    assert s['nodes']['mini-1']['tx_bytes']==100
    assert s['nodes']['mini-2']['rx_bytes']==100
    assert s['nodes']['mini-2']['rx_mbps']==.0004
    assert s['nodes']['mini-3']['ack_rtt_ms']['mean'] is None
    assert s['nodes']['mini-2']['ack_rtt_ms']['mean']==2
    assert distribution([1,2,3])['p50']==2


@pytest.mark.asyncio
async def test_runner_writes_failures_warmup_and_node_observations(tmp_path, monkeypatch):
    import argparse
    import json
    import httpx
    import scripts.evaluate as runner
    cases=tmp_path/'cases.jsonl'
    cases.write_text(json.dumps({'case_id':'q1','query':'question','reviewed':True,'relevant_hashes':['a']})+'\n')
    calls=[]
    async def handler(request):
        body=json.loads(request.content); calls.append(body)
        return httpx.Response(200,json={'partial':False,'chunks':[{'content_hash':'a'}],
            'routing':{'visited_nodes':['mini-2'],'skipped_nodes':['mini-3'], 'target_reached':False},
            'nodes':[{'node_id':'mini-2','status':'ok','round_trip_ms':2,'request_body_bytes':12,
                      'response_body_bytes':30,'timings':{'search_ms':1},
                      'candidates':[{'content_hash':'a','score':.8}]}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(runner.httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(handler),**kw))
    a=argparse.Namespace(queries=cases,output=tmp_path/'run',allow_draft=False,seed=42,timeout=2,
                        warmup=1,repeat=2,top_k=3,per_node_k=5,mode='broadcast',min_score=.7,
                        nodes=['mini-2','mini-3'],url='http://test/v1/retrieve/aggregate',scenario='categorical')
    await runner.run(a)
    summary=json.loads((a.output/'summary.json').read_text())
    assert len(calls)==3 and summary['queries_attempted']==2
    assert summary['nodes']['mini-3']['statuses']['skipped']==2
    assert summary['nodes']['mini-2']['hit_rate_when_queried_and_observable']==1
    assert (a.output/'nodes.csv').exists()
