"""Optional adapter to nektos/act (MIT); no GitHub-hosted runner invocation."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path

class ActError(RuntimeError):pass

class ActBridge:
    def __init__(self,binary:str='act'):
        self.binary=binary

    def command(self,repo:Path,workflow:Path,job:str|None=None)->list[str]:
        root=Path(repo).expanduser().resolve()
        path=Path(workflow).expanduser().resolve()
        allowed=root/'.github'/'workflows'
        if not root.is_dir() or not path.is_file() or not path.is_relative_to(allowed) or path.suffix not in ('.yml','.yaml'):
            raise ActError('Workflow must exist in local .github/workflows')
        cmd=[self.binary,'workflow_dispatch','-W',str(path),'--workdir',str(root),'--pull=false']
        if job:
            if not job.replace('-','').replace('_','').isalnum():raise ActError('Invalid job name')
            cmd.extend(['-j',job])
        return cmd

    def run(self,repo:Path,workflow:Path,job:str|None=None,timeout:int=3600)->dict:
        if not shutil.which(self.binary):raise ActError('Install nektos/act and Docker/Podman locally')
        if timeout<1 or timeout>86400:raise ActError('Invalid timeout')
        cmd=self.command(repo,workflow,job)
        try:
            proc=subprocess.run(cmd,cwd=Path(repo).resolve(),capture_output=True,text=True,
                                timeout=timeout,check=False,env={k:v for k,v in os.environ.items() if k not in ('GITHUB_TOKEN','GH_TOKEN','OPENAI_API_KEY')})
        except subprocess.TimeoutExpired as exc:raise ActError('Local act execution timed out') from exc
        return {'exit_code':proc.returncode,'status':'success' if proc.returncode==0 else 'failure',
                'stdout':proc.stdout[-200000:],'stderr':proc.stderr[-200000:],'executor':'act-local'}
