"""Read-only language toolchain discovery, no installations or implicit execution."""
from __future__ import annotations
import shutil
import subprocess

LANGUAGES={
 'python':['python3'], 'javascript':['node'], 'typescript':['tsc'], 'rust':['rustc','cargo'],
 'go':['go'], 'java':['java','javac'], 'kotlin':['kotlinc'], 'c':['cc'], 'cpp':['c++'],
 'shell':['sh'], 'git':['git'], 'cmake':['cmake']}

def detect_toolchains(commands:list[str]|None=None)->dict[str,dict]:
    commands=commands or sorted({cmd for cmds in LANGUAGES.values() for cmd in cmds})
    result={}
    for name in commands:
        if not name or '/' in name or '\\' in name or len(name)>100:
            raise ValueError('Toolchain names must be simple executable names')
        path=shutil.which(name)
        result[name]={'available':bool(path),'path':path}
        if path:
            try:
                p=subprocess.run([path,'--version'],capture_output=True,text=True,timeout=3,check=False)
                result[name]['version']=(p.stdout or p.stderr).splitlines()[0][:180] if p.stdout or p.stderr else ''
            except (OSError,subprocess.TimeoutExpired):result[name]['version']='unavailable'
    return result
