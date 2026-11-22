#!/usr/bin/env python3
"""Replay and inventory every SciPy HiGHS solve using the archived original script."""
import os, sys, time, csv, json, math
from collections import defaultdict,Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=str(Path(os.environ.get('SAPPORO_BASE', HERE.parent)).resolve())
OUT=str(Path(os.environ.get('SAPPORO_OUT', HERE)).resolve())
Path(OUT).mkdir(parents=True, exist_ok=True)
if not (Path(BASE)/'revised'/'hold_harmless.py').exists():
    raise SystemExit(f'Run from the GitHub repository root ({BASE}) or set SAPPORO_BASE to the project root')
sys.path.insert(0,BASE+'/revised')
import hold_harmless as h
original_init=h.Planner.__init__; original_solve=h.Planner.solve; original_milp=h.milp
counter=[-1];last=[None];records=[];refs=defaultdict(dict)

def init(self,cfg,packages,o0,support,weights):
 original_init(self,cfg,packages,o0,support,weights)
 counter[0]+=1;self._phase=counter[0]
 self._fullh={o:sum(packages[r][-1]['hours'] for r in packages if o0[r]==o) for o in cfg['operators']}

def traced_milp(*args,**kwargs):
 res=original_milp(*args,**kwargs);last[0]=res;return res

def solve(self,K,L,ref=None,nogoods=()):
 last[0]=None
 result=original_solve(self,K,L,ref,nogoods)
 raw=last[0]
 depth=round(1-self.caps_h['Bankei']/self._fullh['Bankei'],5)
 key=(self._phase,depth)
 if ref is None:refkind='baseline_enumeration' if nogoods else 'fixed_optimum'
 else:
  seen=refs[key]
  if id(ref) not in seen:seen[id(ref)]=len(seen)
  refkind=['opt','alt1','alt2','alt3','alt4','alt5'][seen[id(ref)]] if seen[id(ref)]<6 else 'rule_or_alt_'+str(seen[id(ref)])
 def fmt(v):
  try:return float(v) if v is not None and math.isfinite(float(v)) else ''
  except:return ''
 records.append({'solve_id':len(records)+1,'offset':self._phase,'depth':depth,'K':K,'L':('infinity' if L is None else L),'reference_type':refkind,'ref_count':len(ref) if ref is not None else '', 'nogoods':len(nogoods), 'status':getattr(raw,'status',''), 'status_message':getattr(raw,'message',''), 'optimum_reachable':result['cov'] if result is not None else '', 'mip_gap':fmt(getattr(raw,'mip_gap',None)),'mip_dual_bound':fmt(getattr(raw,'mip_dual_bound',None)),'mip_node_count':getattr(raw,'mip_node_count',''),'objective_minimization':fmt(getattr(raw,'fun',None))})
 return result
h.Planner.__init__=init;h.Planner.solve=solve;h.milp=traced_milp
sys.argv=['hold_harmless.py','--data',BASE+'/sapporo_reconstruction/data','--out',OUT+'/rerun_archive_model']
t0=time.time();h.main()
# The last reference for each phase and depth is the explicit rule-based plan.
# Earlier labels were assigned by encounter order: opt, alt1, ..., rule.
for row in records:
 typ=row['reference_type']
 if typ.startswith('alt') or typ.startswith('rule_or_alt_'):
  ordinal=int(typ.split('_')[-1] if typ.startswith('rule_or_alt_') else typ[3:])
  key=(int(row['offset']),round(float(row['depth']),5))
  if ordinal == len(refs[key])-1:
   row['reference_type']='rule'
with open(OUT+'/solver_run_ledger.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
counts=Counter((x['offset'],x['depth'],x['status']) for x in records)
with open(OUT+'/solver_run_counts.csv','w',newline='') as f:
 w=csv.writer(f);w.writerow(['offset','depth','solver_status','n_runs'])
 for key,n in sorted(counts.items()):w.writerow([*key,n])
print('LEDGER TOTAL:',len(records),'SCI PY STATUS COUNTS:',dict(Counter(x['status'] for x in records)),'MAX MIP GAP:',max([x['mip_gap'] for x in records if isinstance(x['mip_gap'],float)],default=None),'TOTAL RUNTIME',round(time.time()-t0,2),flush=True)
