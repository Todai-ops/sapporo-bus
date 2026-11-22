"""Verify the exact archived GTFS ZIP source hashes and provenance."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/'sapporo_reconstruction/data/provenance.json').read_text(encoding='utf-8'))
for f in p['feeds']:
    path=ROOT/'gtfs_sources'/f['filename']
    assert path.is_file(),path
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha==f['sha256'],f"GTFS mismatch: {f['filename']} {sha} != {f['sha256']}"
    assert f['source_url'].startswith('https://ckan.hoda.jp/'),f['source_url']
    print(f"OK {f['filename']}: SHA-256 {sha}")
assert p['number_of_queries']==832
assert p['bus_trip_count']==253
assert p['subway_trip_count']==678
print('All feed checksums match their recorded provenance.')
