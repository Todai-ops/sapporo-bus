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

# Alternative departure construction: nested max-min temporal spacing by direction.
# First pick first service; repeatedly select time farthest from any selected time,
# breaking ties by earlier departure, then trip ID. Each m retains ceil(m*n/levels).
def build_maxmin_package(by_route,trips,levels,offset,turnaround):
 pkg={}
 for r,tids in by_route.items():
  dirs=defaultdict(list)
  for t in tids:
   tr=trips[t]
   dirs[(tr['stops'][0][0],tr['stops'][-1][0])].append(t)
  orders=[]
  for ts in dirs.values():
   seq=sorted(ts,key=lambda tid:(trips[tid]['stops'][0][2],tid))
   chosen=[0];remainder=set(range(1,len(seq)))
   while remainder:
    nxt=max(remainder,key=lambda i:(min(abs(trips[seq[i]]['stops'][0][2]-trips[seq[j]]['stops'][0][2]) for j in chosen),-i))
    chosen.append(nxt);remainder.remove(nxt)
   orders.append((seq,chosen))
  packages={}
  for m in range(1,levels+1):
   s=set()
   for seq,order in orders:
    n=len(seq)
    s.update(seq[i] for i in order[:math.ceil(n*m/levels)])
   packages.setdefault(frozenset(s),m)
  pkg[r]=[dict(level=m,trips=tt,hours=sum((trips[t]['stops'][-1][1]-trips[t]['stops'][0][2]) for t in tt)/60,vehicles=h.min_vehicles(tt,trips,turnaround)) for tt,m in sorted(packages.items(),key=lambda a:a[1])]
 return pkg

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
 U=planner.solve(Kmax,h.INF,ref['reach']);P=planner.solve(Kmax,0,ref['reach']);one=planner.solve(1,h.INF,ref['reach'])
 Lstar=h.minimum_allowance(planner,{(Kmax,h.INF):U,(Kmax,0):P},Kmax,P['cov']+1,ref['reach']) if U['cov']>P['cov'] else None
 first=planner.solve(Kmax,Lstar,ref['reach']) if Lstar is not None else P
 cg=int(U['cov']-fixed);cost=int(U['cov']-P['cov'])
 row=dict(scenario=name,threshold=threshold,levels=levels,order=method,queries=len(queries),full=int(sum(bool(s) for s in support)),minimal_supports=sum(map(len,support)),packages=sum(map(len,packages.values())),options=planner.J,fixed=fixed,K1_unrestricted=int(one['cov']),unrestricted=int(U['cov']),protected=int(P['cov']),coord_gain=cg,protection_cost=cost,protection_share=(round(100*cost/cg,1) if cg else 'undefined'),Lstar=(Lstar if Lstar is not None else ''),Lstar_cov=int(first['cov']),Lstar_gross=len(first['reach']-ref['reach']),Lstar_losses=len(ref['reach']-first['reach']),unrestricted_gross=len(U['reach']-ref['reach']),unrestricted_losses=len(ref['reach']-U['reach']),reassigned_K1=';'.join(one['reassigned']),reassigned_Lstar=';'.join(first['reassigned']),n_solves=planner.n_solves,hours_Bankei=round(U['hours']['Bankei'],3),hours_Jotetsu=round(U['hours']['Jotetsu'],3),veh_Bankei=U['veh']['Bankei'],veh_Jotetsu=U['veh']['Jotetsu'])
 rows.append(row)
 verbose.append(dict(scenario=name,setting=row,selected_refs=sorted([q+1 for q in ref['reach']]),selected_packages_K1=[(planner.options[j]['route'],planner.options[j]['op'],planner.options[j]['level']) for j in one['selected']],selected_packages_K7_protected=[(planner.options[j]['route'],planner.options[j]['op'],planner.options[j]['level']) for j in P['selected']]))
 print(name,'full',row['full'],'fixed',fixed,'U',row['unrestricted'],'P',row['protected'],'L*',row['Lstar'],'solves',planner.n_solves,'secs',round(time.time()-t0,2),flush=True)
with open(OUT+'/new_sensitivity_results.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with open(OUT+'/new_sensitivity_results.json','w') as f:json.dump(verbose,f,ensure_ascii=False,indent=2)
print('ALL DONE seconds',round(time.time()-t0,2))
