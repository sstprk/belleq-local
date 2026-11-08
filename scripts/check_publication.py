"""Check publication structure, relative links, model parity and credential patterns.

This is a targeted pattern scan, not a guarantee that arbitrary data is public.
Only Git-tracked or unignored candidate files are inspected; private environments,
downloaded raw data and generated local runs are excluded.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]


def main():
    paths=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
        cwd=ROOT,capture_output=True,check=True).stdout.decode().split('\0')
    files=[ROOT/p for p in paths if p and (ROOT/p).is_file()]
    failures=[];md_count=0
    patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{30,}',
              rb'AKIA[0-9A-Z]{16}']
    for path in files:
        rel=path.relative_to(ROOT)
        if path.stat().st_size>10_000_000:failures.append(f'Oversized Git candidate: {rel}')
        content=path.read_bytes()
        if any(re.search(p,content) for p in patterns):failures.append(f'Credential pattern: {rel}')
        if path.suffix not in ['.png','.pdf','.docx'] and (b'/'+b'Users/') in content:
            failures.append(f'Personal home path: {rel}')
        if path.suffix=='.json':
            try:json.loads(content)
            except (ValueError,UnicodeError):failures.append(f'Invalid JSON: {rel}')
        if path.suffix=='.md':
            md_count+=1
            for value in re.findall(r'\]\(([^)]+)\)',content.decode()):
                value=value.split(' "')[0]
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value) or value.startswith('#'):continue
                local=unquote(value.split('#')[0])
                if local and not (path.parent/local).exists():
                    failures.append(f'Broken link in {rel}: {value}')
    for name in ['calibration','trace_library','regressors','model_card']:
        left=ROOT/f'simulator/artifacts/{name}.json';right=ROOT/f'web-demo/artifacts/{name}.json'
        if left.read_bytes()!=right.read_bytes():failures.append(f'Web model drift: {name}')
    release=json.loads((ROOT/'data-release.json').read_text())
    if len(release['sha256'])!=64 or release['raw_input_files']!=89:
        failures.append('Unexpected research release metadata')
    for name in ['LICENSE','CITATION.cff','README.md','docs/LAB_SETUP.md','docs/REPRODUCIBILITY.md']:
        if not (ROOT/name).is_file():failures.append('Required file missing: '+name)
    if failures:
        raise SystemExit('\n'.join(failures))
    print(json.dumps({'status':'passed','candidate_files':len(files),'markdown_files':md_count,
        'model_artifact_pairs':4,'credential_patterns_found':0,'broken_relative_links':0}))


if __name__=='__main__':main()
