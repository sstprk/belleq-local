#!/usr/bin/env python3
"""User launchd job; install/start/stop/status/uninstall. Run as login user, not sudo."""
import argparse
import os
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'org.belleq.lab'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action', choices=['install','start','stop','status','uninstall'])
    args=p.parse_args()
    path=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    domain=f'gui/{os.getuid()}'
    target=f'{domain}/{LABEL}'
    def run(*a, check=True): return subprocess.run(['launchctl',*a],check=check)
    if args.action=='install':
        if not (ROOT/'.venv/bin/python').exists() or not (ROOT/'config/local.json').exists():
            p.error('Run uv sync and create config/local.json first')
        (ROOT/'logs').mkdir(exist_ok=True)
        path.parent.mkdir(parents=True,exist_ok=True)
        spec={'Label':LABEL,'ProgramArguments':[str(ROOT/'.venv/bin/python'),'-m','belleq_lab'],
              'WorkingDirectory':str(ROOT),'RunAtLoad':True,
              'KeepAlive':{'SuccessfulExit':False},'ThrottleInterval':30,
              'EnvironmentVariables':{'BELLEQ_CONFIG':str(ROOT/'config/local.json'),
                                      'PYTHONUNBUFFERED':'1'},
              'StandardOutPath':str(ROOT/'logs/service.log'),
              'StandardErrorPath':str(ROOT/'logs/service.err.log')}
        if os.getenv('BELLEQ_API_KEY'):
            spec['EnvironmentVariables']['BELLEQ_API_KEY']=os.environ['BELLEQ_API_KEY']
        run('bootout',target,check=False)
        path.write_bytes(plistlib.dumps(spec)); path.chmod(0o600)
        run('bootstrap',domain,str(path))
    elif args.action=='start':
        run('bootstrap',domain,str(path))
    elif args.action=='stop':
        run('bootout',target)
    elif args.action=='uninstall':
        run('bootout',target,check=False)
        path.unlink(missing_ok=True)
    else:
        run('print',target)
if __name__=='__main__': main()
