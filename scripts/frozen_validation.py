#!/usr/bin/env python3
"""Test a published *specific schedule* separately from global optimum values.

Reference identities and selected package/owner choices are frozen in JSON,
so a different tied SciPy/HiGHS solution will not alter this check.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'revised'),str(ROOT/'revision_analysis')]
import hold_harmless as h
from package_design import build_maxmin_package
DATA=ROOT/'sapporo_reconstruction/data'
cfg=dict(h.DEFAULT_CONFIG); cfg.update(json.loads((DATA/'config.json').read_text()))
trips,transfers,queries,weights=h.load(str(DATA))
idx=h.departure_index(trips)
support=[h.enumerate_support(q,trips,idx,transfers,cfg) for q in queries]
by_route=defaultdict(list);original={}
for tid,tr in trips.items():
    if tr['mode']=='bus':
        by_route[tr['route']].append(tid)
        original[tr['route']]=tr['op']
assert len(queries)==832

def build(method='bitrev',threshold=60,levels=8,cut=.2):
    c=dict(cfg);c['max_itinerary_minutes']=threshold
    sup=support if threshold==60 else [h.enumerate_support(q,trips,idx,transfers,c) for q in queries]
    if method=='bitrev':pk=h.build_packages(by_route,trips,levels,0,c['turnaround_minutes'])
    else:pk=build_maxmin_package(by_route,trips,levels,0,c['turnaround_minutes'])
    p=h.Planner(c,pk,original,sup,weights)
    fullh={o:sum(pk[r][-1]['hours'] for r in by_route if original[r]==o) for o in c['operators']}
    p.caps_h={o:fullh[o]*(1-cut) for o in fullh}
    return p

def check_plan(p,selected,ids,expected,label):
    chosen=[]
    for row in selected:
        route,operator,level=tuple(row)
        opts=[j for j in p.route_opts[route] if p.options[j]['op']==operator and p.options[j]['level']==level]
        assert len(opts)==1,(label,row,len(opts))
        chosen.append(opts[0])
    x=p.describe(chosen)
    actual=set(int(q)+1 for q in x['reach'])
    assert actual==set(ids),(label,'changed query identities',sorted(actual-set(ids))[:10],sorted(set(ids)-actual)[:10])
    assert x['cov']==expected,(label,x['cov'],expected)
    for op in p.ops:
        assert x['hours'][op]<=p.caps_h[op]+1e-7,(label,op,'hours')
        assert x['veh'][op]<=p.cfg['operators'][op]['vehicle_cap'],(label,op,'vehicles')
    return x

main=build()
archive=json.loads((ROOT/'revision_analysis/worked_example_20pct.json').read_text())['cases']
ref_ids=set(int(i) for i in archive['reference_K0']['reachability_ids'])
for name in ['reference_K0','K7_L0','K7_L3','K1_L5','K1_unrestricted','K7_unrestricted']:
    a=archive[name]
    selected=[(v['route'],v['selected_operator'],v['package_level']) for v in a['packages']]
    x=check_plan(main,selected,a['reachability_ids'],a['coverage'],name)
    assert len(set(x['reach']-set(i-1 for i in ref_ids)))==a['gains']
    assert len(set(i-1 for i in ref_ids)-x['reach'])==a['losses']
print('PASS: archived 411 reference plus six exact timetable/identity/resource checks.')

# Verify the published objectives *without* comparing the arbitrary timetable
# returned by SciPy/HiGHS to the published schedule.
assert main.solve(0,h.INF)['cov']==411
assert main.solve(1,h.INF)['cov']==415
assert main.solve(7,0,{q-1 for q in ref_ids})['cov']==411
assert main.solve(7,3,{q-1 for q in ref_ids})['cov']==413
print('PASS: 20% global optima match 411, 415, protected 411, L=3 413.')

# Freeze all three 60-min temporal-spacing reference *identities*, not a
# newly returned K=0 optimum which can differ across solver platforms.
temporal=build(method='temporal')
refs=json.loads((ROOT/'revision_analysis/temporal_reference_sets_frozen.json').read_text())
assert len(refs)==3
prot=[]
for i,r in enumerate(refs):
    check_plan(temporal,r['selected'],r['ids'],414,f'temporal reference {i+1}')
    qset={j-1 for j in r['ids']}
    ans=temporal.solve(7,0,qset)
    assert ans['cov']==r['protected'],(i,ans['cov'],r['protected'])
    prot.append(int(ans['cov']))
assert temporal.solve(0,h.INF)['cov']==414
assert temporal.solve(7,h.INF)['cov']==418
assert sorted(prot)==[414,415,416]
print('PASS: temporal-spacing references 414/414/414 -> zero-loss coverage 414, 415, 416; unrestricted 418.')

# Distinguish the two tied 415-query routes by where their 5 losses occur.
for name,origin in [('K1_unrestricted','中の沢'),('K1_L5','藤野４条十一丁目')]:
    v=archive[name]
    assert v['coverage']==415 and v['gains']==9 and v['losses']==5
    assert all(q['origin']==origin for q in v['lost_queries']),name
print('PASS: one 415 optimum loses 5 Nakanosawa queries; another loses 5 Fujino queries.')

# Additional complete, reference-locked objective checks across all three
# primary cuts and the decisive 45-minute counterexample.
primary=json.loads((ROOT/'revision_analysis/frozen_primary_references.json').read_text())
for cut in (10,20,30):
    plan=build(cut=cut/100)
    spec=primary[str(cut)]
    check_plan(plan,spec['selected'],spec['query_ids'],spec['coverage'],f'primary {cut}%')
    ref={int(q)-1 for q in spec['query_ids']}
    fixed=int(plan.solve(0,h.INF)['cov'])
    unrestricted=int(plan.solve(7,h.INF,ref)['cov'])
    protected=int(plan.solve(7,0,ref)['cov'])
    assert (fixed,unrestricted,protected)=={10:(419,421,419),20:(411,415,411),30:(403,406,403)}[cut]
print('PASS: all three primary references and fixed/unrestricted/zero-loss optima validated.')

sensitivity=json.loads((ROOT/'revision_analysis/new_sensitivity_results.json').read_text())
ref45={int(q)-1 for r in sensitivity if r['scenario']=='threshold45' for q in r['selected_refs']}
assert len(ref45)==326
p45=build(threshold=45)
assert int(p45.solve(0,h.INF)['cov'])==326
assert int(p45.solve(7,h.INF,ref45)['cov'])==328
assert int(p45.solve(7,0,ref45)['cov'])==328
print('PASS: archived 45-minute reference 326; both unrestricted and zero-loss coverage 328.')
