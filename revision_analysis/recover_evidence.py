#!/usr/bin/env python3
"""Verified selected solutions and query-level audit from 2026-11-07 research package."""
import os, sys, csv, json, time
from collections import defaultdict
import numpy as np
from scipy.sparse import coo_array
from scipy.sparse.csgraph import maximum_bipartite_matching

def independent_vehicle_chains(tids,trips,turnaround):
    ids=sorted(tids); n=len(ids)
    starts=[(trips[t]['stops'][0][0],trips[t]['stops'][0][2]) for t in ids]
    ends=[(trips[t]['stops'][-1][0],trips[t]['stops'][-1][1]) for t in ids]
    edges=[(i,j) for i in range(n) for j in range(n) if i!=j and ends[i][0]==starts[j][0] and starts[j][1]>=ends[i][1]+turnaround]
    if not edges:return n
    mat=coo_array((np.ones(len(edges),dtype=np.int8),([e[0] for e in edges],[e[1] for e in edges])),shape=(n,n)).tocsr()
    matching=maximum_bipartite_matching(mat,perm_type='column')
    return n-int((matching!=-1).sum())
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=str(Path(os.environ.get('SAPPORO_BASE', HERE.parent)).resolve())
OUT=str(Path(os.environ.get('SAPPORO_OUT', HERE)).resolve())
Path(OUT).mkdir(parents=True, exist_ok=True)
if not (Path(BASE)/'revised'/'hold_harmless.py').exists():
    raise SystemExit(f'Run from the GitHub repository root ({BASE}) or set SAPPORO_BASE to the project root')
sys.path.insert(0,BASE+'/revised')
import hold_harmless as h
cfg=h.DEFAULT_CONFIG.copy()
cfg.update(json.load(open(BASE+'/sapporo_reconstruction/data/config.json')))
trips,transfers,queries,weights=h.load(BASE+'/sapporo_reconstruction/data')
bus={t:tr for t,tr in trips.items() if tr['mode']=='bus'}
by_route=defaultdict(list); o0={}
for tid,tr in bus.items():
 by_route[tr['route']].append(tid);o0[tr['route']]=tr['op']
print('enumerating reachability',flush=True)
t0=time.time(); depidx=h.departure_index(trips)
support=[h.enumerate_support(q,trips,depidx,transfers,cfg) for q in queries]
print('supports',len(queries),sum(bool(s) for s in support),sum(map(len,support)),'sec',round(time.time()-t0,2),flush=True)
packages=h.build_packages(by_route,trips,8,0,cfg['turnaround_minutes'])
planner=h.Planner(cfg,packages,o0,support,weights)
fullh={o:sum(packages[r][-1]['hours'] for r in by_route if o0[r]==o) for o in cfg['operators']}
planner.caps_h={o:fullh[o]*0.8 for o in fullh}
ref=planner.solve(0,h.INF)
print('reference',ref['cov'],ref['selected'],flush=True)
cases={'K7_L0':(7,0),'K7_L3':(7,3),'K1_L3':(1,3),'K1_L5':(1,5),'K1_unrestricted':(1,h.INF),'K7_unrestricted':(7,h.INF)}
result={'setting':{'threshold_minutes':60,'offset':0,'cut_depth':0.2,'query_count':len(queries),'full_reachable':sum(bool(s) for s in support),'num_supports':sum(map(len,support)),'caps_hours':planner.caps_h,'caps_vehicles':{o:cfg['operators'][o]['vehicle_cap'] for o in cfg['operators']}},'cases':{}}

def describe(k,sol):
 selected=[]; hrs_byop=defaultdict(float);veh_byop=defaultdict(int)
 for j in sol['selected']:
  opt=planner.options[j]; vv=independent_vehicle_chains(opt['trips'],trips,cfg['turnaround_minutes']); hh=sum((trips[t]['stops'][-1][1]-trips[t]['stops'][0][2]) for t in opt['trips'])/60
  assert vv==opt['veh'] and abs(hh-opt['hours'])<1e-8
  hrs_byop[opt['op']]+=hh;veh_byop[opt['op']]+=vv
  selected.append(dict(route=opt['route'],baseline_operator=o0[opt['route']],selected_operator=opt['op'],package_level=opt['level'],n_trips=len(opt['trips']),hours=round(hh,3),vehicles=vv,first_trips=sorted(opt['trips'])[:10]))
 assert all(hrs_byop[o]<=planner.caps_h[o]+1e-7 and veh_byop[o]<=cfg['operators'][o]['vehicle_cap'] for o in cfg['operators'])
 gained=sorted(sol['reach']-ref['reach']); lost=sorted(ref['reach']-sol['reach'])
 formatq=lambda idx: {'id':idx+1,'origin':queries[idx][0],'destination':queries[idx][1],'departure':f'{queries[idx][2]//60:02d}:{queries[idx][2]%60:02d}'}
 return dict(K=k,coverage=sol['cov'],gains=len(gained),losses=len(lost),reassigned=sol['reassigned'],hours={x:round(hrs_byop[x],3) for x in cfg['operators']},vehicles={x:veh_byop[x] for x in cfg['operators']},packages=selected,gained_queries=[formatq(q) for q in gained],lost_queries=[formatq(q) for q in lost],reachability_ids=sorted([q+1 for q in sol['reach']]))
result['cases']['reference_K0']=describe(0,ref)
for name,(K,L) in cases.items():
 sol=planner.solve(K,L,ref['reach']);result['cases'][name]=describe(K,sol)
 print(name,sol['cov'],'+',len(sol['reach']-ref['reach']),'-',len(ref['reach']-sol['reach']),sol['reassigned'],flush=True)
with open(OUT+'/worked_example_20pct.json','w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
with open(OUT+'/worked_example_query_changes.csv','w',newline='') as f:
 w=csv.writer(f);w.writerow(['case','change','query_id','origin','destination','departure'])
 for case,v in result['cases'].items():
  for change,flag in (('gained','gained_queries'),('lost','lost_queries')):
   for q in v[flag]:w.writerow([case,change,q['id'],q['origin'],q['destination'],q['departure']])
with open(OUT+'/worked_example_resources.csv','w',newline='') as f:
 w=csv.writer(f);w.writerow(['case','route','baseline_operator','selected_operator','package_level','retained_trips','hours','vehicles'])
 for case,v in result['cases'].items():
  for p in v['packages']:w.writerow([case,p['route'],p['baseline_operator'],p['selected_operator'],p['package_level'],p['n_trips'],p['hours'],p['vehicles']])
print('saved JSON and two CSVs. Total seconds',round(time.time()-t0,2),flush=True)
