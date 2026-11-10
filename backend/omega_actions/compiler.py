"""Workflow compiler: validates jobs, expands matrices, resolves dependencies, detects cycles."""
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any
from .yaml_loader import load_yaml

@dataclass(frozen=True)
class JobSpec:
    id: str
    base_id: str
    needs: tuple[str, ...]
    matrix: dict[str, Any]
    raw: dict

@dataclass(frozen=True)
class CompiledWorkflow:
    name: str
    jobs: dict[str, JobSpec]
    source: dict
    order: tuple[str, ...]

def load_workflow(source: str | Path) -> dict:
    if isinstance(source, Path):
        if source.stat().st_size > 1024*1024: raise ValueError('Workflow exceeds 1 MiB')
        return load_yaml(source.read_text(encoding='utf-8'))
    if '\n' not in source and len(source)<240 and Path(source).is_file():
        return load_workflow(Path(source))
    return load_yaml(source)

def expand_matrix(matrix: dict, limit: int=256) -> list[dict]:
    if not isinstance(matrix,dict): raise ValueError('strategy.matrix must be a mapping')
    axes = {k:v for k,v in matrix.items() if k not in ('include','exclude')}
    if any(not isinstance(v,list) or not v for v in axes.values()): raise ValueError('Matrix axes must be nonempty lists')
    keys = list(axes)
    count = 1
    for v in axes.values():
        count *= len(v)
        if count > limit: raise ValueError('Matrix exceeds configured limit')
    rows = [dict(zip(keys, values)) for values in product(*(axes[k] for k in keys))] if keys else []
    exclude = matrix.get('exclude',[]) or []
    include = matrix.get('include',[]) or []
    if not isinstance(exclude,list) or not isinstance(include,list): raise ValueError('Matrix include/exclude must be lists')
    for e in exclude:
        if not isinstance(e,dict): raise ValueError('Matrix exclude entries must be mappings')
        rows = [r for r in rows if not all(r.get(k)==v for k,v in e.items())]
    # GitHub include entries augment compatible original combinations, otherwise append a new combination.
    original_keys = set(keys)
    for item in include:
        if not isinstance(item,dict): raise ValueError('Matrix include entries must be mappings')
        compatible = [r for r in rows if all(k not in original_keys or r.get(k)==v for k,v in item.items())]
        if compatible:
            for row in compatible: row.update(item)
        else: rows.append(dict(item))
    if not rows and not keys and not include: rows=[{}]
    if len(rows)>limit: raise ValueError('Matrix exceeds configured limit')
    return rows

def compile_workflow(source: dict, max_matrix: int=256) -> CompiledWorkflow:
    raw_jobs = source.get('jobs')
    if not isinstance(raw_jobs,dict) or not raw_jobs: raise ValueError('Workflow requires jobs mapping')
    if len(raw_jobs)>512: raise ValueError('Too many jobs')
    variants = {}
    for base,raw in raw_jobs.items():
        if not isinstance(base,str) or not isinstance(raw,dict): raise ValueError('Invalid job definition')
        steps=raw.get('steps',[])
        if not isinstance(steps,list): raise ValueError('Job steps must be a list')
        for step in steps:
            if not isinstance(step,dict) or ('run' in step)==('uses' in step):
                raise ValueError('Each step must have exactly one of run or uses')
        strategy = raw.get('strategy',{}) or {}
        if not isinstance(strategy,dict): raise ValueError('Invalid strategy')
        matrix = strategy.get('matrix',{}) or {}
        rows=expand_matrix(matrix,max_matrix) if matrix else [{}]
        variants[base]=[(base if len(rows)==1 and not matrix else f'{base}[{i}]',row) for i,row in enumerate(rows)]
    jobs={}
    for base,raw in raw_jobs.items():
        needed=raw.get('needs',[])
        if isinstance(needed,str): needed=[needed]
        if not isinstance(needed,list): raise ValueError('Invalid needs')
        if any(n not in variants for n in needed): raise ValueError(f'Unknown dependency for {base}')
        dependencies=tuple(jid for n in needed for jid,_ in variants[n])
        for jid,matrix in variants[base]:
            if jid in jobs: raise ValueError('Duplicate expanded job id')
            jobs[jid]=JobSpec(jid,base,dependencies,matrix,raw)
    visiting=set(); visited=set(); order=[]
    def visit(node):
        if node in visiting: raise ValueError('Workflow dependency cycle')
        if node in visited: return
        visiting.add(node)
        for dep in jobs[node].needs: visit(dep)
        visiting.remove(node); visited.add(node); order.append(node)
    for jid in jobs: visit(jid)
    return CompiledWorkflow(str(source.get('name','Local workflow')),jobs,source,tuple(order))
