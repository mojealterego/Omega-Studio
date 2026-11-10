"""Explicit opt-in installation of local Git hooks; never invoked during package build."""
from pathlib import Path
import os
import shlex
import subprocess
import sys

def install_hook(repo:Path,event:str,workflow:Path)->Path:
    if event not in ('post-commit','pre-push'): raise ValueError('Unsupported hook')
    repo=Path(repo).expanduser().resolve()
    git=subprocess.run(['git','-C',str(repo),'rev-parse','--git-path','hooks'],capture_output=True,text=True,check=True)
    hooks=Path(git.stdout.strip())
    if not hooks.is_absolute(): hooks=(repo/hooks).resolve()
    hooks.mkdir(parents=True,exist_ok=True)
    target=hooks/event
    if target.exists(): raise FileExistsError('Refusing to overwrite existing hook')
    command=' '.join(shlex.quote(x) for x in [sys.executable,'-m','omega_actions','run',str(workflow.resolve()),'--repo',str(repo),'--unsafe-native'])
    script='#!/bin/sh\n'+command+'\n'
    target.write_text(script,encoding='utf-8')
    if os.name!='nt': target.chmod(0o700)
    return target
