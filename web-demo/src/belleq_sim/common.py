import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
METHODS = ['semantic_sequential', 'broadcast', 'random_sequential', 'single_db']
SEED = 20261020

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def jsonl(path):
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]

def csv_read(path):
    csv.field_size_limit(100_000_000)
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def csv_write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def event(stage, **details):
    p = ROOT/'research/journal.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a') as f:
        f.write(json.dumps({'time_utc': datetime.now(timezone.utc).isoformat(),
                            'stage': stage, **details}, ensure_ascii=False)+'\n')

def distribution(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not len(a):
        return {'n': 0, 'mean': None, 'p50': None, 'p95': None}
    return dict(n=len(a), mean=float(a.mean()), p50=float(np.median(a)),
                p95=float(np.quantile(a,.95)), p05=float(np.quantile(a,.05)),
                std=float(a.std()), minimum=float(a.min()), maximum=float(a.max()))

def empirical_ci(values, seed=SEED, repeats=2000):
    """Question bootstrap CI for mean; does not estimate between-session uncertainty."""
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.mean(rng.choice(a, size=(repeats,len(a)), replace=True), axis=1)
    return [float(x) for x in np.quantile(means,[.025,.975])]
