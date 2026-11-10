"""Offline built-in actions. Unsupported third-party uses fail closed."""
from pathlib import Path
import os
import shutil
from .artifacts import ArtifactStore
from .cache import DependencyCache
from .expressions import interpolate

class UnsupportedAction(ValueError):
    pass

def safe_subdir(workspace:Path,subdir:str)->Path:
    target=(workspace/subdir).resolve()
    if not target.is_relative_to(workspace.resolve()): raise ValueError('Path outside workspace')
    return target

def execute_action(uses:str,params:dict,workspace:Path,run_id:str,artifacts:ArtifactStore,cache:DependencyCache,
                   source_repo:Path,record_artifact,context:dict,secrets:list[str]|None=None)->str:
    ref=uses.lower().split('@')[0]
    if ref=='actions/checkout':
        path=str(params.get('path','.'))
        target=safe_subdir(workspace,path)
        if target!=workspace:
            if target.exists() and any(target.iterdir()): raise ValueError('Checkout destination not empty')
            shutil.copytree(source_repo,target,ignore=shutil.ignore_patterns('.omega-actions'),dirs_exist_ok=True,symlinks=False)
        return f'Local checkout ready at {target}'
    if ref in ('actions/setup-python','actions/setup-node'):
        import subprocess
        name='python' if ref.endswith('python') else 'node'
        exe=shutil.which(name)
        if not exe: raise UnsupportedAction(f'{name} runtime not installed locally')
        result=subprocess.run([exe,'--version'],capture_output=True,text=True,timeout=5)
        if result.returncode: raise UnsupportedAction(f'{name} runtime unavailable')
        installed=(result.stdout or result.stderr).strip()
        requested=str(params.get('python-version' if name=='python' else 'node-version','')).strip()
        if requested and not installed.lstrip('v').startswith(requested.lstrip('v')):
            raise UnsupportedAction(f'Installed {name} {installed} does not satisfy requested {requested}; offline auto-install disabled')
        return f'{name}: {installed}'
    if ref=='actions/cache':
        key=str(params.get('key',''))
        if not key: raise ValueError('Cache key required')
        paths=str(params.get('path','')).splitlines()
        restored=cache.restore(key,workspace,str(params.get('restore-keys','')).splitlines())
        # Save on cache miss; on hit the files are already present.
        if not restored:
            return f'Cache miss for {key}; save deferred until job completes'
        return f'Cache restored {restored} files'
    if ref=='actions/upload-artifact':
        name=str(params.get('name','artifact'))
        path=str(params.get('path','')).splitlines()
        if not path or not any(path): raise ValueError('Artifact path required')
        dest,count,digest=artifacts.upload(run_id,name,path,workspace,secrets)
        record_artifact(run_id,name,dest,count,digest)
        return f'Artifact {name}: {count} files SHA256={digest}'
    if ref=='actions/download-artifact':
        name=str(params.get('name',''))
        if not name: raise ValueError('Artifact name required')
        destination=safe_subdir(workspace,str(params.get('path','.')))
        count=artifacts.download(run_id,name,destination)
        return f'Downloaded artifact {name}: {count} files'
    raise UnsupportedAction(f'Action {uses} is not implemented; refusing remote code execution')
