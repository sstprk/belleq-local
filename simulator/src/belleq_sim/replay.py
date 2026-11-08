"""Deterministic replay of the recorded candidate lists, not a new vector search."""
from itertools import permutations

def merge(nodes, threshold=.7, top_k=3, per_node_k=5):
    unique = {}
    for node in nodes:
        for c in node['candidates'][:per_node_k]:
            if c['score'] < threshold: continue
            key = c['content_hash']
            if key not in unique or c['score'] > unique[key]['score']:
                unique[key] = c
    return sorted(unique.values(),key=lambda h:(-h['score'],str(h['id'])))[:top_k]

def replay(nodes, order, mode, threshold=.7, top_k=3, per_node_k=5):
    visited=[]
    for node_id in order:
        visited.append(nodes[node_id])
        if mode!='broadcast' and len(merge(visited,threshold,top_k,per_node_k))>=top_k:
            break
    chunks = merge(visited,threshold,top_k,per_node_k)
    return [n['node_id'] for n in visited],chunks

def all_orders(nodes):
    return permutations(sorted(nodes))
