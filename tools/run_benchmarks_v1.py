"""Reproducible local deterministic simulation benchmark (not a hardware benchmark)."""
from __future__ import annotations
import json
import platform
from pathlib import Path
import sys
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from omega_actions.digital_twin import simulate_architecture


def run():
    cases=[('nominal_5000',20261110,5000,8,0.15),
           ('outage_1000',7,1000,4,1.0),
           ('no_fault_250',99,250,4,0.0)]
    results={}
    for name,seed,jobs,workers,rate in cases:
        tracemalloc.start()
        start=time.perf_counter_ns()
        result=simulate_architecture(seed=seed,jobs=jobs,worker_count=workers,network_failure_rate=rate)
        elapsed=(time.perf_counter_ns()-start)/1e6
        _,peak=tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert all(result['invariants'].values()),name
        results[name]={'measured_wall_ms':round(elapsed,3),
                       'python_peak_alloc_bytes':peak,
                       'virtual_results':result}
    report={'measurement_scope':'LOCAL_CPU_SIMULATION_NOT_ANDROID',
            'python':platform.python_version(),'platform':platform.platform(),
            'cases':results}
    dest=ROOT/'validation'/'simulation_benchmarks_v1.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:{'wall_ms':v['measured_wall_ms'],
                         'peak_alloc_bytes':v['python_peak_alloc_bytes'],
                         'invariants':v['virtual_results']['invariants']} for k,v in results.items()},indent=2))

if __name__=='__main__':run()
