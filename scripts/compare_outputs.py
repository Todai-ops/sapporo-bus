"""Compare reproduced solver tables and sensitivity values to frozen records."""
from pathlib import Path
import csv, math
ROOT=Path(__file__).resolve().parents[1]

def rows(file):
    with file.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.reader(f))

def check(a,b):
    assert a.is_file(),f'Missing expected saved table: {a}'
    assert b.is_file(),f'Missing reproduced table: {b}'
    x,y=rows(a),rows(b)
    assert len(x)==len(y),(a,len(x),b,len(y))
    for i,(one,two) in enumerate(zip(x,y)):
        assert one==two,f'Mismatch row {i} in {a.name}: {one[:5]} vs {two[:5]}'
    print(f'OK {a.relative_to(ROOT)} matches {b.relative_to(ROOT)} ({len(x)-1} data rows)')

old=ROOT/'sapporo_reconstruction/final_analysis'
for name in ('coverage.csv','metrics.csv','references.csv','menu.csv'):
    check(old/name,ROOT/'reproduced/main'/name)
    check(old/name,ROOT/'revision_analysis/reproduced/rerun_archive_model'/name)
check(ROOT/'revision_analysis/new_sensitivity_results.csv',ROOT/'revision_analysis/reproduced/new_sensitivity_results.csv')
check(ROOT/'revision_analysis/solver_run_counts.csv',ROOT/'revision_analysis/reproduced/solver_run_counts.csv')
# MIP diagnostics may contain machine-level differences: compare deterministic metadata and results.
a,b=(rows(ROOT/'revision_analysis'/f) for f in ('solver_run_ledger.csv','reproduced/solver_run_ledger.csv'))
assert len(a)==831 and len(b)==831,(len(a),len(b))
for k in ('offset','depth','K','L','reference_type','ref_count','nogoods','status','optimum_reachable'):
    col=a[0].index(k)
    for i in range(1,len(a)):
        assert a[i][col]==b[i][col],f'Ledger mismatch at solve {i}, col {k}'
print('OK 830 solver-call records (scenario, reference, status, and objective).')
