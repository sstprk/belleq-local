"""UI-independent simulation API with explicit evidence levels."""
from dataclasses import dataclass, asdict
import math
import json
import numpy as np
from .common import ROOT, METHODS, SEED, distribution
from .replay import replay
from .ridge import features, predict

@dataclass
class Scenario:
    method: str = 'broadcast'
    mode: str = 'empirical'
    nodes: int = 3  # Search workers only; coordinator is separate.
    draws: int = 10000
    seed: int = SEED
    threshold: float = .7
    top_k: int = 3
    per_node_k: int = 5
    include_generation: bool = False
    extra_rtt_ms: float = 0
    service_time_multiplier: float = 1
    bandwidth_mbps: float | None = None
    reference_bandwidth_mbps: float = 1000
    semantic_owner_first_probability: float | None = None

    def validate(self):
        if self.method not in METHODS or self.mode not in ['empirical','trace','assumption']:
            raise ValueError('Unknown method or mode')
        for k,lo,hi in [('nodes',1,64),('draws',1,100000),('top_k',1,5),('seed',0,2**32-1)]:
            x=getattr(self,k)
            if type(x) is not int or not lo<=x<=hi:raise ValueError(f'{k} must be an integer in [{lo},{hi}]')
        for k in ['threshold','extra_rtt_ms','service_time_multiplier','reference_bandwidth_mbps']:
            x=getattr(self,k)
            if type(x) not in [int,float] or not math.isfinite(x):raise ValueError(f'{k} must be finite')
        if not 0<=self.threshold<=1 or self.extra_rtt_ms<0 or self.service_time_multiplier<=0:
            raise ValueError('Invalid threshold, RTT, or compute multiplier')
        if self.reference_bandwidth_mbps<=0:raise ValueError('Reference bandwidth must be positive')
        if type(self.include_generation) is not bool:raise ValueError('include_generation must be boolean')
        if self.per_node_k!=5:raise ValueError('v0.1 retains the recorded five-candidate worker payload; per_node_k must be 5')
        if self.bandwidth_mbps is not None and (type(self.bandwidth_mbps) not in [int,float] or
                not math.isfinite(self.bandwidth_mbps) or self.bandwidth_mbps<=0):
            raise ValueError('Bandwidth must be finite and positive')
        p=self.semantic_owner_first_probability
        if p is not None and (type(p) not in [int,float] or not math.isfinite(p) or not 0<=p<=1):
            raise ValueError('Owner-first probability must be in [0,1]')
        if self.method=='single_db' and self.nodes!=1:raise ValueError('single_db uses one search worker')
        native=1 if self.method=='single_db' else 3
        if self.mode=='empirical' and (self.nodes!=native or self.threshold!=.7 or self.top_k!=3 or
                self.extra_rtt_ms!=0 or self.service_time_multiplier!=1 or self.bandwidth_mbps is not None or p is not None):
            raise ValueError('Empirical mode supports only the measured native configuration; choose trace or assumption mode')
        if self.mode=='trace' and (self.nodes!=3 or self.method=='single_db' or self.extra_rtt_ms!=0 or
                self.service_time_multiplier!=1 or self.bandwidth_mbps is not None or p is not None):
            raise ValueError('Trace mode replays three recorded categorical workers; changed costs require assumption mode')
        if self.mode=='assumption' and self.method=='single_db':
            raise ValueError('single_db is available in empirical mode only in v0.1')
        if self.mode=='assumption' and self.method=='semantic_sequential' and p is None:
            raise ValueError('Semantic assumption mode requires an explicit semantic_owner_first_probability')
        if p is not None and self.method!='semantic_sequential':
            raise ValueError('Owner-first probability applies only to semantic_sequential')

def load_artifacts():
    return {name:json.loads((ROOT/'artifacts'/f'{name}.json').read_text())
            for name in ['calibration','trace_library','regressors','model_card']}

def point_prediction(question, method, artifacts=None):
    if not isinstance(question,str) or not 1<=len(question)<=10000 or method not in METHODS:
        raise ValueError('Provide a question of 1..10000 characters and a supported method')
    a=artifacts or load_artifacts();x=[features(dict(question=question,experiment_method=method))]
    result={}
    for target,model in a['regressors'].items():
        result[target]=float(predict(model['ridge'],x)[0]) if model['selected']=='ridge' else model['method_mean'][method]
    return dict(question=question,method=method,predictions=result,
        scope='Native configuration only; point estimates, no queue/load or new-node-count prediction',
        model_selection={k:v['selected'] for k,v in a['regressors'].items()})

def simulate(config, artifacts=None):
    s=Scenario(**config);s.validate();a=artifacts or load_artifacts()
    rng=np.random.default_rng(s.seed)
    records=[r for r in a['calibration'] if r['method']==s.method]
    by_case={r['case_id']:r for r in records}
    positive_generation=[r['generation_ms'] for r in records if r['generation_ms']>0]
    frame_ratios=[r['network_frame_bytes']/r['body_bytes'] for r in records if r['complete'] and r['body_bytes']>0]
    traces=a['trace_library'];samples=[]
    for i in range(s.draws):
        if s.mode=='empirical':
            r=records[int(rng.integers(len(records)))];gen=r['generation_ms'] if s.include_generation else 0
            samples.append(dict(draw=i,case_id=r['case_id'],complete=r['complete'],
                retrieval_ms=r['aggregate_ms'],generation_ms=gen,
                end_to_end_ms=(r['client_ms'] if s.include_generation else r['aggregate_ms']),
                network_frame_bytes=r['network_frame_bytes'],application_body_bytes=r['body_bytes'],
                visited_nodes=r['visited_nodes'],reference_hit=r['hit'],
                generation_invoked=r['generation_invoked'] if s.include_generation else False))
            continue
        t=traces[int(rng.integers(len(traces)))];native=t['nodes'];owner=t['owner']
        r=by_case[t['case_id']]
        if s.mode=='trace':
            nodes=native;order=list(native)
            if s.method=='semantic_sequential':order=t['semantic_order'][:]
            elif s.method=='random_sequential':rng.shuffle(order)
        else:
            # Explicit virtual-worker scenario: one source-owner archetype, N-1 distractors.
            # It does NOT redistribute the 16421 original vectors or learn a search-size curve.
            nodes={};distractors=[n for n in native if n!=owner]
            for j in range(s.nodes):
                template=owner if j==0 else distractors[int(rng.integers(len(distractors)))]
                node=dict(native[template]);node_id=f'virtual-{j}'
                node.update(node_id=node_id,candidates=[dict(c,content_hash=f'{j}:{c["content_hash"]}',
                                                             id=f'{j}:{c["id"]}') for c in node['candidates']])
                nodes[node_id]=node
            order=list(nodes);rng.shuffle(order)
            if s.method=='semantic_sequential':
                order.remove('virtual-0')
                if rng.random()<s.semantic_owner_first_probability:order.insert(0,'virtual-0')
                else:order.insert(int(rng.integers(1,s.nodes)) if s.nodes>1 else 0,'virtual-0')
        visited,hits=replay(nodes,order,'broadcast' if s.method=='broadcast' else s.method,
                            s.threshold,s.top_k,s.per_node_k)
        selected=[nodes[n] for n in visited]
        body=sum(n['request_body_bytes']+n['response_body_bytes'] for n in selected)
        ratio=r['network_frame_bytes']/r['body_bytes'] if r['complete'] and r['body_bytes']>0 else float(np.median(frame_ratios))
        frames=body*ratio  # Whole-query calibrated frame/body ratio; not per-packet emulation.
        costs=[n['round_trip_ms']*s.service_time_multiplier+s.extra_rtt_ms for n in selected]
        worker=max(costs) if s.method=='broadcast' else sum(costs)
        router=t['router_ms']*s.service_time_multiplier if s.method=='semantic_sequential' else 0
        serialization=0
        if s.bandwidth_mbps is not None:
            # Shared coordinator link once; positive extra serialization only.
            serialization=frames*8/1000*max(0,1/s.bandwidth_mbps-1/s.reference_bandwidth_mbps)
        retrieval=router+worker+serialization
        gen=0
        if s.include_generation and hits:
            gen=r['generation_ms'] if r['generation_ms']>0 else float(rng.choice(positive_generation))
        samples.append(dict(draw=i,case_id=t['case_id'],complete=True,retrieval_ms=retrieval,
            generation_ms=gen,end_to_end_ms=retrieval+gen,network_frame_bytes=frames,
            application_body_bytes=body,visited_nodes=len(visited),
            reference_hit=int(any(h['content_hash'] in t['gold'] for h in hits)) if s.mode=='trace' else None,
            generation_invoked=bool(s.include_generation and hits)))
    summary={k:distribution([x[k] for x in samples if x['complete'] and x[k] is not None])
        for k in ['retrieval_ms','generation_ms','end_to_end_ms','network_frame_bytes','application_body_bytes','visited_nodes']}
    hit=[x['reference_hit'] for x in samples if x['reference_hit'] is not None]
    warnings=[
        'Search workers exclude the separate coordinator.',
        'p05/p95 describe simulated query variability, not confidence in unseen deployments.',
        'Concurrency=1; no queueing, capacity, QPS, WAN congestion, or corpus-size scaling learned.',
        'Frame bytes are captured coordinator traffic; physical-layer overhead and unrelated traffic excluded.',
        'No live retrieval or LLM calls are made; generated text is not predicted.'
    ]
    if s.mode!='empirical':warnings += [
        'Counterfactual costs use old broadcast worker timings; modern-session worker speed drift is not corrected.',
        'Counterfactual modes assume successful workers and do not model the two observed dependency failures.',
        'Frame bytes use a sampled query frame/body ratio; they are estimates, not reconstructed packet traces.',
        'Generation duration is sampled; changed-context answer content/quality is unknown.']
    if s.mode=='assumption':warnings += [
        'UNVALIDATED EXTRAPOLATION: virtual workers reuse one owner and distractor archetypes.',
        'Each virtual worker keeps sampled compute and payload distributions. New corpus sizes are not modeled.',
        'Semantic owner-first probability is a user assumption, not measured accuracy at this node count.',
        'Reference-hit and answer accuracy are unavailable for assumption mode.',
        'Bandwidth adjustment assumes a user-specified reference link; no packet scheduling or saturation model.']
    return dict(config=asdict(s),evidence_level={'empirical':'heldout_checked_native_distribution',
        'trace':'counterfactual_candidate_replay','assumption':'unvalidated_user_assumptions'}[s.mode],
        summary=summary,failed_draws=sum(not x['complete'] for x in samples),
        reference_hit_rate=float(np.mean(hit)) if hit else None,
        reference_hit_note='Nonexhaustive synthetic passage labels, not answer accuracy; empirical rate conditional on complete labeled rows.',
        warnings=warnings,samples=samples)
