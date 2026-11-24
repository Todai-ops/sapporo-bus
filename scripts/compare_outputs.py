#!/usr/bin/env python3
"""Cross-platform comparison of objective invariants, not arbitrarily tied schedules."""
from pathlib import Path
import csv,math,collections
ROOT=Path(__file__).resolve().parents[1]

def rows(path):
    assert path.is_file(),f'Missing output {path}'
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def nearly(a,b):
    return abs(float(a)-float(b))<1e-7

original=rows(ROOT/'sapporo_reconstruction/final_analysis/coverage.csv')
replay=rows(ROOT/'reproduced/main/coverage.csv')
archived=rows(ROOT/'revision_analysis/reproduced/rerun_archive_model/coverage.csv')
# No reference identity can affect the unconditional global objective. Compare
# all reported K, phase and depth settings where L is unrestricted.
def unconditional(data):
    d={}
    for r in data:
        if str(r['L'])!='inf':continue
        k=(r['offset'],r['depth'],r['K'])
        v=float(r['cov'])
        if k in d:assert nearly(d[k],v),(k,d[k],v)
        d[k]=v
    return d
old=unconditional(original)
for label,data in [('normal replay',replay),('instrumented replay',archived)]:
    now=unconditional(data)
    assert set(old)==set(now),(label,'missing unconditional scenarios',set(old)^set(now))
    for k in old:assert nearly(old[k],now[k]),(label,k,old[k],now[k])
    print('PASS:',label,len(old),'unconditional optimal-coverage comparisons')

# The sensitivity script now uses exact archived reference IDs.
base={r['scenario']:r for r in rows(ROOT/'revision_analysis/new_sensitivity_results.csv')}
new={r['scenario']:r for r in rows(ROOT/'revision_analysis/reproduced/new_sensitivity_results.csv')}
assert set(base)==set(new)
for key in base:
    a,b=base[key],new[key]
    for field in ['queries','full','fixed','unrestricted','protected','coord_gain','protection_cost','Lstar','Lstar_cov']:
        if field=='Lstar' and not a[field] and not b[field]:continue
        assert nearly(a[field],b[field]),(key,field,a[field],b[field])
print('PASS: 7 sensitivity scenarios: objective and loss-bound results with archived reference IDs')

# A fresh run can have fewer or more calls than the archived run, because
# HiGHS may select different tied optima during no-good enumeration.
for title,path in [('archived',ROOT/'revision_analysis/solver_run_ledger.csv'),('fresh',ROOT/'revision_analysis/reproduced/solver_run_ledger.csv')]:
    ledger=rows(path)
    assert ledger and all(str(r['status'])=='0' for r in ledger),(title,'non-optimal solver status')
    print(title,'solver-call count:',len(ledger),'(830 archived; a platform-dependent number on replay)')
print('All platform-stable checks passed. Use frozen_validation.py for query identities and specific schedules.')
