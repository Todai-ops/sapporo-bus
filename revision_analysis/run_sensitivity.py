#!/usr/bin/env python3
"""Additional sensitivity runs using original reconstructed GTFS pilot and MILP."""
import os, sys, json, csv, math, time, copy
from collections import defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=str(Path(os.environ.get('SAPPORO_BASE', HERE.parent)).resolve())
OUT=str(Path(os.environ.get('SAPPORO_OUT', HERE)).resolve())
Path(OUT).mkdir(parents=True, exist_ok=True)
if not (Path(BASE)/'revised'/'hold_harmless.py').exists():
    raise SystemExit(f'Run from the GitHub repository root ({BASE}) or set SAPPORO_BASE to the project root')
sys.path.insert(0,BASE+'/revised')
import hold_harmless as h
cfg=h.DEFAULT_CONFIG.copy(); cfg.update(json.load(open(BASE+'/sapporo_reconstruction/data/config.json')))
trips,transfers,queries,weights=h.load(BASE+'/sapporo_reconstruction/data')
bus={t:tr for t,tr in trips.items() if tr['mode']=='bus'}
by_route=defaultdict(list);o0={}
for tid,tr in bus.items():by_route[tr['route']].append(tid);o0[tr['route']]=tr['op']
idx=h.departure_index(trips);Kmax=len(cfg['eligible_route_units']);depth=.2

from package_design import build_maxmin_package

frozen_refs={r['scenario']:set(int(q)-1 for q in r['selected_refs']) for r in json.load(open(BASE+'/revision_analysis/new_sensitivity_results.json'))}
cases=[('threshold30',30,8,'bitrev'),('threshold45',45,8,'bitrev'),('baseline60',60,8,'bitrev'),('threshold75',75,8,'bitrev'),('threshold90',90,8,'bitrev'),('levels16',60,16,'bitrev'),('temporal_spacing8',60,8,'maxmin')]
rows=[]; verbose=[]
t0=time.time()
for name,threshold,levels,method in cases:
 pCfg=dict(cfg);pCfg['max_itinerary_minutes']=threshold
 support=[h.enumerate_support(q,trips,idx,transfers,pCfg) for q in queries]
 packages=(h.build_packages if method=='bitrev' else build_maxmin_package)(by_route,trips,levels,0,cfg['turnaround_minutes'])
 planner=h.Planner(pCfg,packages,o0,support,weights)
 fullh={o:sum(packages[r][-1]['hours'] for r in by_route if o0[r]==o) for o in pCfg['operators']}
 planner.caps_h={o:fullh[o]*(1-depth) for o in fullh}
 ref=planner.solve(0,h.INF);fixed=int(ref['cov'])
 frozen=frozen_refs[name]
 assert len(frozen)==fixed, f'{name}: archived reference size {len(frozen)} != optimal {fixed}'
 U=planner.solve(Kmax,h.INF,frozen);P=planner.solve(Kmax,0,frozen);one=planner.solve(1,h.INF,frozen)
 Lstar=h.minimum_allowance(planner,{(Kmax,h.INF):U,(Kmax,0):P},Kmax,P['cov']+1,frozen) if U['cov']>P['cov'] else None
 first=planner.solve(Kmax,Lstar,frozen) if Lstar is not None else P
 cg=int(U['cov']-fixed);cost=int(U['cov']-P['cov'])
 row=dict(scenario=name,threshold=threshold,levels=levels,order=method,queries=len(queries),full=int(sum(bool(s) for s in support)),minimal_supports=sum(map(len,support)),packages=sum(map(len,packages.values())),options=planner.J,fixed=fixed,K1_unrestricted=int(one['cov']),unrestricted=int(U['cov']),protected=int(P['cov']),coord_gain=cg,protection_cost=cost,protection_share=(round(100*cost/cg,1) if cg else 'undefined'),Lstar=(Lstar if Lstar is not None else ''),Lstar_cov=int(first['cov']),Lstar_gross=len(first['reach']-frozen),Lstar_losses=len(frozen-first['reach']),unrestricted_gross=len(U['reach']-frozen),unrestricted_losses=len(frozen-U['reach']),reassigned_K1=';'.join(one['reassigned']),reassigned_Lstar=';'.join(first['reassigned']),n_solves=planner.n_solves,hours_Bankei=round(U['hours']['Bankei'],3),hours_Jotetsu=round(U['hours']['Jotetsu'],3),veh_Bankei=U['veh']['Bankei'],veh_Jotetsu=U['veh']['Jotetsu'])
 rows.append(row)
 verbose.append(dict(scenario=name,setting=row,selected_refs=sorted([q+1 for q in frozen]),selected_packages_K1=[(planner.options[j]['route'],planner.options[j]['op'],planner.options[j]['level']) for j in one['selected']],selected_packages_K7_protected=[(planner.options[j]['route'],planner.options[j]['op'],planner.options[j]['level']) for j in P['selected']]))
 print(name,'full',row['full'],'fixed',fixed,'U',row['unrestricted'],'P',row['protected'],'L*',row['Lstar'],'solves',planner.n_solves,'secs',round(time.time()-t0,2),flush=True)
with open(OUT+'/new_sensitivity_results.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with open(OUT+'/new_sensitivity_results.json','w') as f:json.dump(verbose,f,ensure_ascii=False,indent=2)
print('ALL DONE seconds',round(time.time()-t0,2))
