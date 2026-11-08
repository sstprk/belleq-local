import json
import unittest
import numpy as np
from belleq_sim.common import ROOT, csv_read
from belleq_sim.replay import replay, merge
from belleq_sim.ridge import fit, predict
from belleq_sim.engine import Scenario, simulate, load_artifacts, point_prediction

def node(name, candidates):
    return dict(node_id=name,candidates=[dict(content_hash=h,id=h,score=s) for h,s in candidates])

class ReplayTests(unittest.TestCase):
    def test_dedup_requires_distinct_chunks_before_stop(self):
        nodes={'a':node('a',[('x',.9),('x',.8)]),'b':node('b',[('y',.85)]),'c':node('c',[('z',.75)])}
        visited,hits=replay(nodes,['a','b','c'],'random_sequential',top_k=3)
        self.assertEqual(visited,['a','b','c'])
        self.assertEqual([h['id'] for h in hits],['x','y','z'])

    def test_threshold_is_inclusive_and_does_not_imply_gold_hit(self):
        nodes={'a':node('a',[('wrong',.7)]),'b':node('b',[('gold',.99)])}
        visited,hits=replay(nodes,['a','b'],'semantic_sequential',threshold=.7,top_k=1)
        self.assertEqual(visited,['a'])
        self.assertEqual(hits[0]['id'],'wrong')

    def test_broadcast_always_visits_all_and_retains_best_duplicate(self):
        nodes={'a':node('a',[('x',.75)]),'b':node('b',[('x',.9),('y',.8)])}
        visited,hits=replay(nodes,['a','b'],'broadcast',top_k=1)
        self.assertEqual(visited,['a','b'])
        self.assertEqual(hits[0]['score'],.9)

class RidgeTests(unittest.TestCase):
    def test_constant_target_and_feature_remain_finite(self):
        m=fit([[1,2],[1,3],[1,4]],[7,7,7],alpha=1)
        np.testing.assert_allclose(predict(m,[[1,100]]),[7])

    def test_objective_stationarity_and_unpenalized_intercept(self):
        x=np.array([[0,3],[2,2],[4,9],[5,8]],dtype=float);y=np.array([1,3,8,7],dtype=float)
        m=fit(x,y,alpha=2);z=(x-m['center'])/m['scale'];w=np.array(m['coefficients'])
        residual=z@w+m['intercept']-y
        np.testing.assert_allclose(z.T@residual+2*w,[0,0],atol=1e-10)
        self.assertAlmostEqual(float(residual.sum()),0)

class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.a=load_artifacts()

    def test_split_is_disjoint_and_augmentation_inherits_parent(self):
        split=json.loads((ROOT/'artifacts/split.json').read_text())['assignments']
        self.assertEqual(list(split.values()).count('test'),100)
        self.assertTrue(all(split[r['case_id']]!='test' for r in self.a['calibration']))
        self.assertTrue(all(split[r['case_id']]!='test' for r in self.a['trace_library']))
        for r in csv_read(ROOT/'data/augmented/order_permutations.csv'):
            self.assertEqual(r['split'],split[r['case_id']])

    def test_every_recorded_successful_replay_matches(self):
        r=csv_read(ROOT/'results/replay_validation.csv')
        self.assertEqual(len(r),1998)
        self.assertTrue(all(x['hashes_match']=='True' and x['visits_match']=='True' for x in r))

    def test_empirical_is_seeded_and_joint(self):
        cfg=dict(method='broadcast',mode='empirical',nodes=3,draws=20,seed=7)
        a=simulate(cfg,self.a);b=simulate(cfg,self.a)
        self.assertEqual(a,b)
        self.assertTrue(all(x['generation_ms']==0 for x in a['samples']))
        self.assertTrue(all(x['visited_nodes']==3 for x in a['samples']))
        self.assertGreater(a['summary']['network_frame_bytes']['mean'],0)

    def test_generation_toggle_preserves_retrieval_and_traffic(self):
        cfg=dict(method='broadcast',draws=50)
        a=simulate(cfg,self.a);b=simulate({**cfg,'include_generation':True},self.a)
        for x,y in zip(a['samples'],b['samples']):
            self.assertEqual(x['retrieval_ms'],y['retrieval_ms'])
            self.assertEqual(x['network_frame_bytes'],y['network_frame_bytes'])
            self.assertGreaterEqual(y['end_to_end_ms'],x['end_to_end_ms'])

    def test_unmeasured_setting_cannot_look_empirically_validated(self):
        with self.assertRaises(ValueError):Scenario(nodes=8).validate()
        with self.assertRaises(ValueError):Scenario(mode='assumption',method='semantic_sequential',nodes=8).validate()
        r=simulate(dict(mode='assumption',nodes=8,draws=10),self.a)
        self.assertEqual(r['evidence_level'],'unvalidated_user_assumptions')
        self.assertIsNone(r['reference_hit_rate'])

    def test_invalid_and_nonfinite_inputs(self):
        for c in [dict(draws=0),dict(nodes=2.5),dict(threshold=float('nan')),
                  dict(mode='assumption',extra_rtt_ms=-1),dict(per_node_k=10),
                  dict(mode='assumption',bandwidth_mbps=float('inf'))]:
            with self.assertRaises(ValueError):Scenario(**c).validate()

    def test_virtual_broadcast_traffic_increases_with_nodes(self):
        a=simulate(dict(mode='assumption',nodes=2,draws=300,seed=9),self.a)
        b=simulate(dict(mode='assumption',nodes=8,draws=300,seed=9),self.a)
        self.assertGreater(b['summary']['network_frame_bytes']['mean'],a['summary']['network_frame_bytes']['mean']*3)
        self.assertEqual(b['summary']['visited_nodes']['mean'],8)

    def test_prediction_is_finite_and_pre_request_only(self):
        r=point_prediction('What did Holmes discover?','broadcast',self.a)
        self.assertTrue(all(np.isfinite(x) and x>=0 for x in r['predictions'].values()))

if __name__=='__main__':unittest.main(verbosity=2)
