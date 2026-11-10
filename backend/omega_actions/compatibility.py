"""Read-only preflight capability inspection for local GitHub Actions workflows."""
from __future__ import annotations
import re
from .compiler import compile_workflow

BUILTINS={'actions/checkout','actions/setup-python','actions/setup-node','actions/cache',
          'actions/upload-artifact','actions/download-artifact'}
NETWORK=re.compile(r'\b(?:curl|wget|pip\s+install|npm\s+(?:ci|install)|docker\s+pull|git\s+clone|cargo\s+(?:install|fetch))\b',re.I)
DOCKER=re.compile(r'\b(?:docker|podman|kubectl)\b',re.I)

def inspect_workflow(source:dict)->dict:
    compiled=compile_workflow(source)
    python_versions=set();node_versions=set();actions=set();unsupported=set();shells=set();contexts=set()
    network=False;containers=False;services=[]
    for job_id,job in compiled.jobs.items():
        raw=job.raw
        if raw.get('container') or raw.get('services'):
            containers=True
            if raw.get('services'):services.append(job_id)
        for step in raw.get('steps',[]):
            uses=str(step.get('uses',''))
            if uses:
                actions.add(uses)
                if uses.split('@')[0].lower() not in BUILTINS:unsupported.add(uses)
                params=step.get('with',{}) or {}
                if uses.lower().startswith('actions/setup-python') and 'python-version' in params:
                    python_versions.add(str(params['python-version']))
                if uses.lower().startswith('actions/setup-node') and 'node-version' in params:
                    node_versions.add(str(params['node-version']))
            run=str(step.get('run',''))
            if NETWORK.search(run):network=True
            if DOCKER.search(run):containers=True
            if step.get('shell'):shells.add(str(step['shell']))
            contexts.update(re.findall(r'\$\{\{\s*([A-Za-z_][A-Za-z_0-9.]*)',run+' '+str(step.get('with',{}))))
    return {'name':compiled.name,'job_count':len(compiled.jobs),'dag_order':list(compiled.order),
            'python_versions':sorted(python_versions),'node_versions':sorted(node_versions),
            'actions':sorted(actions),'unsupported_actions':sorted(unsupported),'shells':sorted(shells),
            'expression_contexts':sorted(contexts),'requires_network':network,
            'requires_containers':containers,'jobs_with_services':services,
            'fully_offline_verified':False,
            'summary':'Static preflight only. Runtime availability and full GitHub Actions compatibility are not guaranteed.'}
