"""User-configurable counterfactual billing estimates, not real GitHub invoices."""
from .storage import StateStore

def estimate(store:StateStore,usd_per_minute:float=0.008,pln_per_usd:float=4.0)->dict:
    if usd_per_minute<0 or pln_per_usd<=0: raise ValueError('Invalid price parameters')
    runs=store.list_runs(5000)
    seconds=0.0
    for r in runs:
        for j in r['jobs'].values():
            if j['started'] is not None and j['finished'] is not None:
                seconds+=max(0,j['finished']-j['started'])
    minutes=seconds/60
    return {'local_job_minutes':round(minutes,3),'estimated_hosted_usd':round(minutes*usd_per_minute,4),
            'estimated_hosted_pln':round(minutes*usd_per_minute*pln_per_usd,2),
            'usd_per_minute_assumed':usd_per_minute,'pln_per_usd_assumed':pln_per_usd,
            'disclaimer':'Hypothetical hosted compute estimate, not a verified invoice or actual savings. Local electricity/hardware costs excluded.'}
