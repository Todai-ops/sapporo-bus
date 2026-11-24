"""Deterministic temporal-spacing package construction for sensitivity tests."""
from collections import defaultdict
import math
from pathlib import Path
import sys
import hold_harmless as h

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

