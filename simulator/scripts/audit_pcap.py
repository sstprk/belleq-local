"""Independently recompute the CSV's captured-frame byte totals from archived PCAPs.

Requires TShark (Wireshark); model runtime itself does not need TShark.
"""
from bisect import bisect_left,bisect_right
from pathlib import Path
import argparse
import io
import csv
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from belleq_sim.common import ROOT,csv_read,csv_write,write_json,event,sha256

def main():
    p=argparse.ArgumentParser();p.add_argument('--tshark',default='/Applications/Wireshark.app/Contents/MacOS/tshark');a=p.parse_args()
    datasets={
        'old':ROOT/'data/raw/oct12/categorical.complete-records.pcap',
        'restart':ROOT/'data/raw/oct14/capture_restart.pcap'}
    packet_data={}
    for name,path in datasets.items():
        cmd=[a.tshark,'-n','-r',str(path),'-Y',
             '(tcp.port == 8000 || tcp.port == 8001) && ip.addr == 192.168.50.11',
             '-T','fields','-E','separator=/t','-e','frame.time_epoch','-e','frame.len']
        r=subprocess.run(cmd,capture_output=True,text=True,check=True)
        pairs=sorted((float(t),int(length)) for t,length in
                     (line.split('\t') for line in r.stdout.splitlines() if line))
        times=[t for t,b in pairs];prefix=[0]
        for t,b in pairs:prefix.append(prefix[-1]+b)
        packet_data[name]=times,prefix
    details=[]
    for r in csv_read(ROOT/'data/raw/combined_070.csv'):
        source='old' if r['experiment_method'] in ['semantic_sequential','broadcast'] else 'restart'
        times,prefix=packet_data[source]
        lo=bisect_left(times,float(r['start_epoch']));hi=bisect_right(times,float(r['end_epoch']))
        recomputed=prefix[hi]-prefix[lo]
        original=int(float(r['mini1_network_tx_bytes'])+float(r['mini1_network_rx_bytes']))
        details.append(dict(sample_id=r['sample_id'],case_id=r['case_id'],method=r['experiment_method'],
            capture=source,csv_bytes=original,recomputed_bytes=recomputed,match=original==recomputed))
    report=dict(queries_checked=len(details),all_match=all(r['match'] for r in details),
        mismatches=sum(not r['match'] for r in details),
        captures={k:dict(path=str(v.relative_to(ROOT)),sha256=sha256(v)) for k,v in datasets.items()},
        tshark_version=subprocess.run([a.tshark,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0],
        note='Captured coordinator frame bytes inside request windows; not complete wire utilization.')
    csv_write(ROOT/'results/pcap_byte_audit.csv',details)
    write_json(ROOT/'results/pcap_audit.json',report)
    assert report['all_match'],report
    event('pcap_bytes_independently_audited',**report)
    print(report)

if __name__=='__main__':main()
