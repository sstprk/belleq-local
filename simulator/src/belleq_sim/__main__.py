import argparse
import json
import sys
from .common import ROOT, write_json, csv_write, event

def main():
    p=argparse.ArgumentParser(description='Belleq research simulator backend')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('train')
    s=sub.add_parser('simulate');s.add_argument('--config',required=True);s.add_argument('--output',required=True)
    q=sub.add_parser('predict');q.add_argument('--question',required=True);q.add_argument('--method',default='broadcast')
    h=sub.add_parser('serve');h.add_argument('--port',type=int,default=8010)
    a=p.parse_args()
    if a.command=='train':
        from .train import main as train
        train()
    elif a.command=='simulate':
        from .engine import simulate
        result=simulate(json.load(open(a.config)));samples=result.pop('samples')
        from pathlib import Path
        dest=Path(a.output)
        if dest.exists():raise ValueError('Output directory already exists; use a new run path')
        dest.mkdir(parents=True)
        write_json(dest/'summary.json',result);csv_write(dest/'samples.csv',samples)
        event('simulation_run',output=str(dest),config=result['config'],evidence=result['evidence_level'])
        print(json.dumps(result,ensure_ascii=False,indent=2))
    elif a.command=='predict':
        from .engine import point_prediction
        print(json.dumps(point_prediction(a.question,a.method),indent=2))
    else:
        from .server import serve
        serve(a.port)

if __name__=='__main__':main()
