"""Native and Docker subprocess runner with timeouts, process-tree termination and redacted streams."""
import asyncio
import codecs
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from .redaction import StreamMasker

class ExecutionDenied(RuntimeError):
    pass

async def terminate_tree(proc):
    if proc.returncode is not None: return
    try:
        if os.name=='nt':
            await asyncio.create_subprocess_exec('taskkill','/F','/T','/PID',str(proc.pid),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        else: os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: await asyncio.wait_for(proc.wait(),timeout=2)
    except asyncio.TimeoutError:
        if os.name=='nt': proc.kill()
        else:
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: return
        await proc.wait()

async def run_command(command:str,workspace:Path,env:dict[str,str],shell:str,timeout:float,
                      secrets:list[str],on_log,engine:str='native',image:str='',network:str='none',mount_root:Path|None=None) -> tuple[int,float]:
    workspace=workspace.resolve()
    mount_root=(mount_root or workspace).resolve()
    if not workspace.is_relative_to(mount_root): raise ExecutionDenied('Working directory outside mounted workspace')
    if not workspace.is_dir(): raise FileNotFoundError('Working directory does not exist')
    if timeout<=0: raise ValueError('Timeout must be positive')
    if engine=='docker':
        if not shutil.which('docker'): raise ExecutionDenied('Docker not installed')
        image=image or 'python:3.13-slim'
        inspect=await asyncio.create_subprocess_exec('docker','image','inspect',image,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        if await inspect.wait()!=0: raise ExecutionDenied('Docker image not available locally; offline mode never pulls images')
        for value in env.values():
            if '\n' in str(value) or '\r' in str(value): raise ExecutionDenied('Multiline environment value unsupported in Docker env file')
        fd,env_file=tempfile.mkstemp(prefix='omega-env-')
        os.chmod(env_file,0o600)
        os.close(fd)
        docker_env={k:(v.replace(str(mount_root),'/workspace') if k.startswith('GITHUB_') else v) for k,v in env.items()}
        with open(env_file,'w') as f:
            for key,value in docker_env.items(): f.write(f'{key}={value}\n')
        argv=['docker','run','-i','--rm','--network',network,'--cpus','2','--memory','2g','--pids-limit','256',
              '--security-opt','no-new-privileges','--cap-drop','ALL','--env-file',env_file,
              '-v',f'{mount_root}:/workspace','-w','/workspace/'+str(workspace.relative_to(mount_root)),image,'sh','-es']
    elif engine=='native':
        env_file=None
        if shell in ('bash','sh'):
            executable=shutil.which(shell)
            if not executable: raise ExecutionDenied(f'{shell} not installed')
            argv=[executable,'-eo','pipefail','-s'] if shell=='bash' else [executable,'-e','-s']
        elif shell=='python': argv=[sys.executable,'-']
        elif shell in ('pwsh','powershell'):
            executable=shutil.which(shell)
            if not executable: raise ExecutionDenied(f'{shell} not installed')
            argv=[executable,'-NoProfile','-NonInteractive','-Command','-']
        elif shell=='cmd' and os.name=='nt': argv=['cmd','/D','/S','/C',command]
        else: raise ExecutionDenied(f'Unsupported shell: {shell}')
    else: raise ExecutionDenied(f'Unknown execution engine: {engine}')
    start=time.monotonic(); proc=None
    try:
        proc=await asyncio.create_subprocess_exec(*argv,cwd=workspace,env=env if engine=='native' else None,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,
                start_new_session=(os.name!='nt'))
        masker=StreamMasker(secrets)
        decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
        async def send_script():
            proc.stdin.write(command.encode('utf-8'))
            await proc.stdin.drain()
            proc.stdin.close()
        async def consume():
            while True:
                chunk=await proc.stdout.read(4096)
                if not chunk: break
                filtered=masker.feed(decoder.decode(chunk))
                if filtered: on_log(filtered)
            tail=masker.feed(decoder.decode(b'',final=True))+masker.finish()
            if tail: on_log(tail)
        try:
            await asyncio.wait_for(asyncio.gather(send_script(),proc.wait(),consume()),timeout=timeout)
        except (asyncio.TimeoutError,asyncio.CancelledError):
            await terminate_tree(proc)
            raise
        return proc.returncode,time.monotonic()-start
    finally:
        if env_file: Path(env_file).unlink(missing_ok=True)
