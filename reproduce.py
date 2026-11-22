#!/usr/bin/env python3
"""Portable Sapporo study reproduction runner (Python 3.12+)."""
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(*cmd, extra_env=None):
    env=os.environ.copy()
    env['PYTHONHASHSEED']='0'
    env['SAPPORO_BASE']=str(ROOT)
    env['SAPPORO_OUT']=str(ROOT/'revision_analysis'/'reproduced')
    if extra_env: env.update(extra_env)
    print('> '+' '.join(map(str,cmd)),flush=True)
    subprocess.run([str(x) for x in cmd],env=env,cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--quick',action='store_true',help='Source hashes, deterministic builder, synthetic model tests and worked case')
    group.add_argument('--full',action='store_true',help='Quick checks plus all model/sensitivity solves and saved output comparison')
    args=p.parse_args()
    py=sys.executable
    run(py,ROOT/'scripts'/'verify_sources.py')
    run(py,ROOT/'gtfs_sources'/'build_study_dataset.py')
    run(py,'-m','unittest','discover','-s','revised','-p','test_*.py','-v')
    run(py,ROOT/'revision_analysis'/'recover_evidence.py')
    if args.full:
        run(py,ROOT/'revised'/'hold_harmless.py','--data',ROOT/'sapporo_reconstruction'/'data','--out',ROOT/'reproduced'/'main')
        run(py,ROOT/'revision_analysis'/'run_sensitivity.py')
        run(py,ROOT/'revision_analysis'/'reconcile_solves.py')
        run(py,ROOT/'scripts'/'compare_outputs.py')
    print('Reproducibility checks passed.',flush=True)

if __name__=='__main__':main()
