"""Async DAG orchestration, isolated workspaces, job/step state and offline actions."""
import asyncio
import fnmatch
import json
import os
from pathlib import Path
import shutil
import time
import uuid
from typing import Any
from .actions import execute_action, UnsupportedAction, safe_subdir
from .artifacts import ArtifactStore
from .cache import DependencyCache
from .compiler import load_workflow, compile_workflow, JobSpec
from .config import Settings
from .expressions import evaluate, interpolate, truth
from .redaction import redact
from .runner import run_command, ExecutionDenied
from .scheduler import AdaptiveScheduler
from .analysis import diagnose, retry_delay
from .services import DockerServices
from .storage import StateStore
from .audit_ledger import IntegrityLedger, load_or_create_key
from .resilience import LatencyTelemetry

class Engine:
    def __init__(self,settings:Settings,store:StateStore|None=None):
        self.settings=settings; self.settings.prepare()
        self.store=store or StateStore(settings.home/'state.db')
        self.artifacts=ArtifactStore(settings.home/'artifacts')
        self.cache=DependencyCache(settings.home/'cas')
        self.scheduler=AdaptiveScheduler(settings.max_parallel)
        self.ledger=IntegrityLedger(settings.home/'audit.db',key=load_or_create_key(settings.home/'audit.key'))
        self.telemetry=LatencyTelemetry(capacity=4096)
        self.cancellations:dict[str,asyncio.Event]={}
        self.active:dict[str,set[asyncio.Task]]={}
        self.locks:dict[str,asyncio.Lock]={}
        self.job_outputs:dict[str,dict[str,dict]]={}
    def cancel(self,run_id:str)->bool:
        flag=self.cancellations.get(run_id)
        if not flag: return False
        flag.set()
        for task in self.active.get(run_id,set()): task.cancel()
        return True
    async def run(self,workflow:Path,repo:Path,secrets:dict[str,str]|None=None,event:str='workflow_dispatch',
                  event_payload:dict|None=None,run_id:str|None=None,engine:str|None=None)->dict:
        repo=Path(repo).expanduser().resolve(); workflow=Path(workflow).expanduser().resolve()
        if not repo.is_dir() or not workflow.is_file(): raise FileNotFoundError('Repo/workflow not found')
        if self.settings.home.resolve().is_relative_to(repo):
            raise ValueError('OMEGA_ACTIONS_HOME must be outside source repository')
        compiled=compile_workflow(load_workflow(workflow),self.settings.max_matrix)
        run_id=run_id or uuid.uuid4().hex
        secrets=secrets or {}
        if any(not isinstance(v,str) for v in secrets.values()): raise ValueError('Secrets must be strings')
        payload=event_payload or {}
        self.store.create_run(run_id,compiled.name,repo,event,{'workflow':str(workflow),'event_payload':payload})
        started_at=time.monotonic()
        self.ledger.append('ci_run_started',{'id':run_id,'workflow':compiled.name,'jobs':len(compiled.jobs)})
        self.store.run_status(run_id,'running')
        self.cancellations[run_id]=asyncio.Event(); self.active[run_id]=set(); self.job_outputs[run_id]={}
        status:dict[str,str]={}; pending=set(compiled.jobs); running:dict[asyncio.Task,str]={}
        gitctx={'event_name':event,'repository':repo.name,'ref':payload.get('ref','refs/heads/main'),
                'sha':payload.get('after',''),'actor':payload.get('sender','local'),'workflow':compiled.name}
        mode=engine or self.settings.default_engine
        concurrency=compiled.source.get('concurrency')
        group=''
        if isinstance(concurrency,str): group=str(interpolate(concurrency,{'github':gitctx}))
        elif isinstance(concurrency,dict): group=str(interpolate(concurrency.get('group',''),{'github':gitctx}))
        lock=self.locks.setdefault(group,asyncio.Lock()) if group else None
        try:
            if lock: await lock.acquire()
            while pending or running:
                if self.cancellations[run_id].is_set():
                    for task in running: task.cancel()
                    if running: await asyncio.gather(*running,return_exceptions=True)
                    for jid in pending: self.store.job_status(run_id,jid,'cancelled'); status[jid]='cancelled'
                    for jid in running.values(): self.store.job_status(run_id,jid,'cancelled'); status[jid]='cancelled'
                    break
                ready=[jid for jid in compiled.order if jid in pending and all(dep in status for dep in compiled.jobs[jid].needs)]
                for jid in ready:
                    pending.remove(jid)
                    job=compiled.jobs[jid]
                    task=asyncio.create_task(self._job(run_id,job,repo,compiled.source,secrets,gitctx,status.copy(),mode))
                    running[task]=jid; self.active[run_id].add(task)
                if not running:
                    if pending: raise RuntimeError('Scheduler deadlock')
                    break
                done,_=await asyncio.wait(running,return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    jid=running.pop(task); self.active[run_id].discard(task)
                    try: result=task.result()
                    except asyncio.CancelledError: result='cancelled'
                    except Exception as exc:
                        self.store.log(run_id,jid,-1,redact(f'Worker error: {type(exc).__name__}: {exc}\n',secrets.values()))
                        result='failure'
                    status[jid]=result; self.store.job_status(run_id,jid,result)
            outcome='cancelled' if self.cancellations[run_id].is_set() else ('failure' if any(v=='failure' for v in status.values()) else 'success')
            self.store.run_status(run_id,outcome)
            self.telemetry.observe('ci_run',(time.monotonic()-started_at)*1000)
            self.ledger.append('ci_run_finished',{'id':run_id,'status':outcome,'jobs':status})
            return {'id':run_id,'status':outcome,'jobs':status}
        except BaseException:
            self.store.run_status(run_id,'failure')
            self.telemetry.observe('ci_run',(time.monotonic()-started_at)*1000)
            self.ledger.append('ci_run_exception',{'id':run_id,'status':'failure'})
            raise
        finally:
            if lock and lock.locked(): lock.release()
            self.active.pop(run_id,None); self.cancellations.pop(run_id,None); self.job_outputs.pop(run_id,None)
    async def _job(self,run_id:str,job:JobSpec,repo:Path,workflow:dict,secrets:dict,gitctx:dict,
                   deps:dict,mode:str)->str:
        jid=job.id
        self.store.job_status(run_id,jid,'queued')
        dep_failed=any(deps[d]!='success' for d in job.needs)
        needs_ctx={}
        for dep in job.needs:
            base=dep.split('[')[0]
            needs_ctx[base]={'result':deps[dep],'outputs':self.job_outputs.get(run_id,{}).get(dep,{})}
        ctx={'github':gitctx,'matrix':job.matrix,'secrets':secrets,'env':{},'needs':needs_ctx,
             'status':'failure' if dep_failed else 'success','steps':{}}
        cond=job.raw.get('if')
        if dep_failed and cond is None: return 'skipped'
        if cond is not None and not truth(evaluate(cond,ctx)): return 'skipped'
        await self.scheduler.acquire()
        self.store.job_status(run_id,jid,'running')
        try:
            return await self._execute_job(run_id,job,repo,workflow,secrets,ctx,mode)
        except asyncio.CancelledError:
            self.store.log(run_id,jid,-1,'Job cancelled\n'); raise
        finally:
            await self.scheduler.release()
    async def _execute_job(self,run_id,job,repo,workflow,secrets,ctx,mode)->str:
        jid=job.id
        workspace=(self.settings.home/'runs'/run_id/jid.replace('/','_')).resolve()
        workspace.mkdir(parents=True,exist_ok=True)
        def ignore(directory,names):
            return [n for n in names if n in ('.git','.omega-actions','node_modules','.venv','target','__pycache__') or (Path(directory)/n).is_symlink()]
        shutil.copytree(repo,workspace,dirs_exist_ok=True,ignore=ignore)
        io_dir=workspace/'.omega'; io_dir.mkdir(exist_ok=True)
        envfile=io_dir/'GITHUB_ENV'; outputfile=io_dir/'GITHUB_OUTPUT'; summaryfile=io_dir/'GITHUB_STEP_SUMMARY'
        allowed_env={'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE','TMPDIR','TEMP','TMP','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','VIRTUAL_ENV'}
        base_env={k:v for k,v in os.environ.items() if k in allowed_env}
        base_env.update({'CI':'true','GITHUB_WORKSPACE':str(workspace),'GITHUB_ENV':str(envfile),
                         'GITHUB_OUTPUT':str(outputfile),'GITHUB_STEP_SUMMARY':str(summaryfile),
                         'GITHUB_RUN_ID':run_id,'GITHUB_JOB':jid,'GITHUB_EVENT_NAME':ctx['github']['event_name']})
        def add_env(raw):
            for key,value in (raw or {}).items():
                if not isinstance(key,str) or not key.replace('_','').isalnum(): raise ValueError('Invalid environment name')
                base_env[key]=str(interpolate(value,ctx))
        add_env(workflow.get('env')); add_env(job.raw.get('env'))
        ctx['env']=base_env.copy()
        steps=job.raw.get('steps',[])
        pending_cache=[]
        started=time.monotonic()
        job_timeout=max(1,min(24*60*60,int(job.raw.get('timeout-minutes',60))*60))
        fail=False
        selected='docker' if mode=='docker' or (mode=='auto' and shutil.which('docker') and job.raw.get('container')) else 'native'
        if job.raw.get('services'):
            if selected!='docker':
                self.store.log(run_id,jid,-1,'Services require a Docker executor and locally available images\n')
                return 'failure'
            services_context=DockerServices(job.raw['services'])
        else:
            services_context=DockerServices({})
        await services_context.__aenter__()
        try:
            return await self._execute_steps(run_id,job,repo,workflow,secrets,ctx,mode,workspace,io_dir,envfile,outputfile,summaryfile,base_env,steps,pending_cache,started,job_timeout,selected,services_context)
        finally:
            await services_context.__aexit__(None,None,None)

    async def _execute_steps(self,run_id,job,repo,workflow,secrets,ctx,mode,workspace,io_dir,envfile,outputfile,summaryfile,base_env,steps,pending_cache,started,job_timeout,selected,services_context):
        jid=job.id
        fail=False
        for index,step in enumerate(steps):
            if self.cancellations[run_id].is_set(): return 'cancelled'
            stepname=str(step.get('name',step.get('uses',f'step-{index+1}')))
            ctx['status']='failure' if fail else 'success'
            if step.get('if') is not None and not truth(evaluate(step['if'],ctx)):
                self.store.step_status(run_id,jid,index,stepname,'skipped'); continue
            if fail and step.get('if') is None:
                self.store.step_status(run_id,jid,index,stepname,'skipped'); continue
            envfile.write_text('',encoding='utf-8'); outputfile.write_text('',encoding='utf-8')
            summaryfile.touch(exist_ok=True)
            ctx['env']=base_env.copy()
            for key,value in (step.get('env') or {}).items():
                ctx['env'][key]=str(interpolate(value,ctx))
            context_env=ctx['env'].copy()
            step_start=time.monotonic(); self.store.step_status(run_id,jid,index,stepname,'running')
            def on_log(chunk): self.store.log(run_id,jid,index,chunk)
            try:
                retry_conf=step.get('x-omega-retry',0)
                retries=max(0,min(5,int(retry_conf)))
                if 'uses' in step:
                    params={k:interpolate(v,ctx) for k,v in (step.get('with') or {}).items()}
                    action=str(interpolate(step['uses'],ctx))
                    message=execute_action(action,params,workspace,run_id,self.artifacts,self.cache,repo,self.store.add_artifact,ctx,list(secrets.values()))
                    on_log(redact(message+'\n',secrets.values()))
                    if action.lower().split('@')[0]=='actions/cache' and 'Cache miss' in message:
                        pending_cache.append((str(params['key']),str(params.get('path','')).splitlines()))
                    code=0
                else:
                    command=str(interpolate(step['run'],ctx))
                    wd=step.get('working-directory', (job.raw.get('defaults') or {}).get('run',{}).get('working-directory',
                           (workflow.get('defaults') or {}).get('run',{}).get('working-directory','.')))
                    cwd=safe_subdir(workspace,str(interpolate(wd,ctx)))
                    cwd.mkdir(parents=True,exist_ok=True)
                    shell=str(step.get('shell', (job.raw.get('defaults') or {}).get('run',{}).get('shell',
                              (workflow.get('defaults') or {}).get('run',{}).get('shell','bash' if os.name!='nt' else 'pwsh'))))
                    if selected=='native' and not self.settings.unsafe_native:
                        raise ExecutionDenied('Native workflow execution requires --unsafe-native or OMEGA_UNSAFE_NATIVE=1')
                    if selected=='docker' and not job.raw.get('container'):
                        image=self.settings.docker_image
                    else:
                        image=job.raw.get('container','')
                        if isinstance(image,dict): image=image.get('image','')
                    remaining=job_timeout-(time.monotonic()-started)
                    if remaining<=0: raise asyncio.TimeoutError('Job timeout')
                    timeout=min(remaining,max(1,int(step.get('timeout-minutes',job_timeout/60))*60))
                    code=1
                    for attempt in range(retries+1):
                        code,_=await run_command(command,cwd,context_env,shell,timeout,list(secrets.values()),on_log,
                                                 engine=selected,image=str(image),mount_root=workspace,network=services_context.network if services_context.started else 'none')
                        if code==0: break
                        if attempt<retries:
                            delay=retry_delay(attempt+1)
                            on_log(f'OMEGA retry {attempt+1}/{retries} after {delay:.2f}s (exit {code})\n')
                            await asyncio.sleep(delay)
                    if code==0 and attempt>0: on_log(f'OMEGA flaky candidate: passed after {attempt} retries\n')
                status='success' if code==0 else 'failure'
            except asyncio.CancelledError: raise
            except asyncio.TimeoutError:
                on_log('Step timed out\n'); status='failure'
            except (OSError,ValueError,ExecutionDenied,UnsupportedAction) as exc:
                on_log(redact(f'{type(exc).__name__}: {exc}\n',secrets.values())); status='failure'
            duration=time.monotonic()-step_start
            self.store.step_status(run_id,jid,index,stepname,status,duration)
            if envfile.exists():
                for k,v in self._read_env_file(envfile).items(): base_env[k]=v
            if outputfile.exists() and step.get('id'):
                ctx['steps'][step['id']]={'outputs':self._read_env_file(outputfile),'outcome':status}
            if summaryfile.exists() and summaryfile.stat().st_size:
                summary=summaryfile.read_text(encoding='utf-8',errors='replace')[:200000]
                on_log(redact('[STEP SUMMARY]\n'+summary+'\n',secrets.values()))
                summaryfile.write_text('',encoding='utf-8')
            if status!='success' and not truth(interpolate(step.get('continue-on-error',False),ctx)):
                fail=True
        if not fail:
            for key,paths in pending_cache:
                try:
                    count=self.cache.save(key,paths,workspace,list(secrets.values()))
                    self.store.log(run_id,jid,-1,f'Cache saved: {count} files\n')
                except (OSError,ValueError) as exc:
                    self.store.log(run_id,jid,-1,redact(f'Cache save error: {exc}\n',secrets.values()))
                    fail=True
        if not fail:
            outputs={}
            for key,value in (job.raw.get('outputs') or {}).items():
                outputs[key]=str(interpolate(value,ctx))
            self.job_outputs.setdefault(run_id,{})[jid]=outputs
        return 'failure' if fail and not truth(interpolate(job.raw.get('continue-on-error',False),ctx)) else 'success'
    @staticmethod
    def _read_env_file(path:Path)->dict[str,str]:
        lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
        out={}; i=0
        while i<len(lines):
            line=lines[i]; i+=1
            if '<<' in line:
                key,delimiter=line.split('<<',1)
                value=[]
                while i<len(lines) and lines[i]!=delimiter:
                    value.append(lines[i]); i+=1
                if i>=len(lines): raise ValueError('Unterminated GitHub environment multiline value')
                i+=1; out[key]='\n'.join(value)
            elif '=' in line:
                key,val=line.split('=',1); out[key]=val
        return {k:v for k,v in out.items() if k and k.replace('_','').isalnum()}
