"""Fetch/import the research archive, verifying its hash before safe extraction."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def import_archive(archive, root=ROOT):
    release = json.loads((root/'data-release.json').read_text())
    if archive.stat().st_size != release['bytes'] or digest(archive) != release['sha256']:
        raise ValueError('Research archive size or SHA-256 differs from data-release.json')
    with tarfile.open(archive, 'r:gz') as tar:
        manifest_name = 'simulator/data/source_manifest.json'
        manifest = json.load(tar.extractfile(manifest_name))
        expected = {'simulator/'+r['snapshot_path']:r['sha256'] for r in manifest}
        expected[manifest_name] = None
        members = tar.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError('Unexpected archive members')
        for member in members:
            name = PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or '..' in name.parts:
                raise ValueError('Archive must contain regular relative files only')
            target = root.joinpath(*name.parts)
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('Archive path escapes repository')
            target.parent.mkdir(parents=True, exist_ok=True)
            wanted = expected[member.name]
            if target.exists():
                if wanted is not None and digest(target) != wanted:
                    raise ValueError(f'Existing data differs; refusing replacement: {member.name}')
                if wanted is not None:
                    continue
            with tar.extractfile(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            if wanted is not None and digest(target) != wanted:
                raise ValueError(f'Extracted checksum mismatch: {member.name}')
    return len(manifest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, help='Use a downloaded archive without internet')
    a = p.parse_args()
    release = json.loads((ROOT/'data-release.json').read_text())
    if a.archive:
        count = import_archive(a.archive)
    else:
        with tempfile.TemporaryDirectory(prefix='belleq-data-') as tmp:
            archive = Path(tmp)/release['filename']
            with urlopen(release['url'], timeout=120) as src, archive.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            count = import_archive(archive)
    print(f'Verified {count} research inputs under simulator/data/raw')


if __name__ == '__main__':
    main()
