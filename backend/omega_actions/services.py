"""Docker service lifecycle for local-image-only job containers, isolated bridge network."""
import asyncio
import json
import re
import shutil
import uuid

class ServiceError(RuntimeError):
    pass

async def docker(*args,timeout=20):
    if not shutil.which('docker'): raise ServiceError('Docker is unavailable')
    proc=await asyncio.create_subprocess_exec('docker',*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try: out,err=await asyncio.wait_for(proc.communicate(),timeout)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait(); raise ServiceError('Docker command timed out')
    if proc.returncode: raise ServiceError((err or out).decode(errors='replace')[:500])
    return out.decode().strip()

class DockerServices:
    def __init__(self,services:dict):
        self.services=services or {}
        self.network='omega-'+uuid.uuid4().hex[:16]
        self.containers=[]
        self.started=False
    async def __aenter__(self):
        if not self.services: return self
        await docker('network','create','--driver','bridge',self.network)
        self.started=True
        try:
            for name,config in self.services.items():
                if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,62}',name): raise ServiceError('Unsafe service name')
                image=config if isinstance(config,str) else config.get('image','')
                if not image: raise ServiceError('Service image required')
                await docker('image','inspect',image)
                args=['run','-d','--network',self.network,'--network-alias',name,
                      '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
                      '--memory','1g','--cpus','1']
                if isinstance(config,dict):
                    for k,v in (config.get('env') or {}).items():
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k): raise ServiceError('Invalid service env name')
                        args.extend(['--env',f'{k}={v}'])
                args.append(image)
                cid=await docker(*args)
                self.containers.append(cid)
            for cid in self.containers:
                # Inspect status; healthcheck is optional, not assumed healthy.
                status=json.loads(await docker('inspect','--format','{{json .State}}',cid))
                if not status.get('Running'): raise ServiceError('Service container exited')
            return self
        except BaseException:
            await self.__aexit__(None,None,None)
            raise
    async def __aexit__(self,*args):
        for cid in reversed(self.containers):
            try: await docker('rm','-f',cid)
            except ServiceError: continue
        if self.started:
            try: await docker('network','rm',self.network)
            except ServiceError: return
