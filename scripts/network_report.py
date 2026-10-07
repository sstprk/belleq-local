"""Summarize ONE coordinator Ethernet capture; never sum captures across hosts."""
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from belleq_lab.evaluation import distribution

FIELDS = ['frame.time_epoch','frame.len','frame.cap_len','ip.src','ip.dst',
          'tcp.analysis.ack_rtt','tcp.analysis.retransmission',
          'tcp.analysis.fast_retransmission','tcp.analysis.spurious_retransmission',
          'http.time']
NODES = {f'192.168.50.{i+10}': f'mini-{i}' for i in range(1,5)}


def summarize_packets(packets, start, end):
    if end <= start: raise ValueError('Positive observation window required')
    duration = end-start
    result = {node: dict(node_id=node, tx_bytes=0, rx_bytes=0, tx_packets=0, rx_packets=0,
                        retransmission_frames=0, truncated_frames=0, ack_rtt_ms=[], http_response_ms=[])
              for node in NODES.values()}
    selected = [r for r in packets if start <= float(r['frame.time_epoch']) <= end]
    for r in selected:
        length = int(r['frame.len'])
        for address, direction in ((r['ip.src'], 'tx'), (r['ip.dst'], 'rx')):
            if address not in NODES: continue
            n = result[NODES[address]]
            n[direction+'_bytes'] += length
            n[direction+'_packets'] += 1
            n['truncated_frames'] += int(int(r['frame.cap_len']) < length)
            n['retransmission_frames'] += int(any(r.get(k) for k in FIELDS[6:9]))
            if r.get('tcp.analysis.ack_rtt'):
                n['ack_rtt_ms'].append(float(r['tcp.analysis.ack_rtt'])*1000)
            if r.get('http.time'):
                n['http_response_ms'].append(float(r['http.time'])*1000)
    for n in result.values():
        n['tx_mbps'] = n['tx_bytes']*8/duration/1e6
        n['rx_mbps'] = n['rx_bytes']*8/duration/1e6
        n['ack_rtt_ms'] = distribution(n['ack_rtt_ms'])
        n['http_response_ms'] = distribution(n['http_response_ms'])
    return {'start_epoch':start, 'end_epoch':end, 'duration_s':duration,
            'unique_captured_bytes':sum(int(r['frame.len']) for r in selected),
            'unique_captured_frames':len(selected), 'nodes':result}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pcap',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True,help='evaluate.py output directory, same clock as capture')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tshark',default='/Applications/Wireshark.app/Contents/MacOS/tshark')
    a=p.parse_args()
    records=[json.loads(l) for l in (a.run/'raw.jsonl').read_text().splitlines()]
    measured=[r for r in records if r['phase']=='measured']
    if not measured: p.error('No measured queries')
    cmd=[a.tshark,'-n','-r',str(a.pcap),'-d','tcp.port==8000,http',
         '-Y','tcp.port == 8000 && ip.addr == 192.168.50.11',
         '-T','fields','-E','header=y','-E','separator=/t','-E','occurrence=f']
    for field in FIELDS: cmd.extend(['-e',field])
    proc=subprocess.run(cmd,capture_output=True,text=True,check=True)
    packets=list(csv.DictReader(io.StringIO(proc.stdout),delimiter='\t'))
    start=min(r['start_epoch'] for r in measured)
    end=max(r['end_epoch'] for r in measured)
    report=summarize_packets(packets,start,end)
    report.update(pcap=str(a.pcap), warnings=[
        'Capture at mini-1 Ethernet; run evaluator on mini-1 for same-clock windows.',
        'Only captured port-8000 IPv4 traffic. No loopback, Ollama or Qdrant internal traffic.',
        'frame.len is captured-frame accounting, excludes physical overhead and may be affected by offload.',
        'TX+RX summed across all nodes double-counts mini-to-mini traffic; use unique_captured_bytes.',
        'ACK RTT includes host ACK behavior; HTTP response time includes server work, neither is one-way latency.',
        'Empty samples mean unobserved, not zero latency. Inspect tcpdump drop count before accepting a run.',
        'Per-query windows omit handshake/close or delayed ACK packets outside the request interval; run totals preferred.'
    ], tshark_stderr=proc.stderr)
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'network.json').write_text(json.dumps(report,indent=2))
    with (a.output/'packets.tsv').open('w') as f: f.write(proc.stdout)
    rows=[]
    for r in measured:
        s=summarize_packets(packets,r['start_epoch'],r['end_epoch'])
        for node,n in s['nodes'].items():
            row=dict(query_id=r['query_id'],case_id=r['case_id'],node_id=node,
                     duration_s=s['duration_s'])
            for key,value in n.items():
                if isinstance(value,dict):
                    row.update({key+'_'+k:v for k,v in value.items()})
                else: row[key]=value
            rows.append(row)
    with (a.output/'network_queries.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(a.output/'network.json')

if __name__=='__main__': main()
