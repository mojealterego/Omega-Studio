"""Deterministic synthetic GitHub event simulator and local workflow harness."""
import asyncio
import heapq
import hashlib
from pathlib import Path
import random
import tempfile
from .config import Settings
from .engine import Engine
from .compiler import load_workflow,compile_workflow
from .storage import StateStore

EVENTS={'push','pull_request','workflow_dispatch'}

class GitHubActionsDigitalTwin:
    """In-memory GitHub Checks/Actions event contract, without network access."""
    def __init__(self,seed:int=2026):
        self.seed=seed; self.events=[]; self.checks={}; self.artifacts={}
    def dispatch(self,event:str):
        payload=synthetic_event(event,self.seed+len(self.events))
        self.events.append(payload)
        return payload
    def create_check(self,sha:str,name:str):
        if len(sha)!=40: raise ValueError('SHA must be 40 hexadecimal characters')
        key=(sha,name)
        if key in self.checks: raise ValueError('Duplicate check')
        self.checks[key]={'status':'in_progress','conclusion':None}
        return key
    def complete_check(self,key,conclusion:str):
        if key not in self.checks: raise KeyError('Unknown check')
        if conclusion not in ('success','failure','cancelled','neutral'): raise ValueError('Invalid conclusion')
        self.checks[key]={'status':'completed','conclusion':conclusion}
    def upload_artifact(self,name:str,content:bytes):
        import hashlib
        self.artifacts[name]={'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}


def synthetic_event(name:str,seed:int=2026)->dict:
    if name not in EVENTS: raise ValueError('Unsupported synthetic event')
    rnd=random.Random(seed)
    return {'event':name,'ref':'refs/heads/main','after':f'{rnd.getrandbits(160):040x}',
            'sender':'omega-simulator','number':rnd.randint(1,1000) if name=='pull_request' else None}


class VirtualWorkerPool:
    """Seeded virtual worker scheduling for external architecture contract tests."""
    def __init__(self,seed:int=2026,slots:int=3):
        if slots<1: raise ValueError('At least one slot required')
        self.random=random.Random(seed); self.slots=slots
    def execute(self,workflow:Path,fail_jobs:set[str]|None=None)->dict:
        compiled=compile_workflow(load_workflow(workflow))
        failed=fail_jobs or set(); status={}; timeline=[]; pending=set(compiled.jobs)
        active=[]; tick=0; serial=0
        while pending or active:
            for jid in compiled.order:
                if jid not in pending or any(dep not in status for dep in compiled.jobs[jid].needs): continue
                if len(active)>=self.slots: break
                pending.remove(jid)
                if any(status[d]!='success' for d in compiled.jobs[jid].needs):
                    status[jid]='skipped';timeline.append({'job':jid,'status':'skipped','time':tick})
                    continue
                duration=self.random.randint(1,9)
                serial+=1;heapq.heappush(active,(tick+duration,serial,jid))
                timeline.append({'job':jid,'status':'started','time':tick})
            if not active:
                if pending: raise RuntimeError('Virtual scheduler deadlock')
                break
            tick,_,jid=heapq.heappop(active)
            status[jid]='failure' if jid in failed else 'success'
            timeline.append({'job':jid,'status':status[jid],'time':tick})
        return {'status':'failure' if 'failure' in status.values() else 'success','jobs':status,'timeline':timeline,'virtual_ticks':tick}

async def simulate(workflow:Path,repo:Path,seed:int=2026)->dict:
    with tempfile.TemporaryDirectory(prefix='omega-sim-') as d:
        settings=Settings(Path(d)/'engine',unsafe_native=True,max_parallel=3)
        event=synthetic_event('push',seed)
        engine=Engine(settings,StateStore(settings.home/'state.db'))
        result=await engine.run(workflow,repo,secrets={'SIMULATED_TOKEN':'omega-secret-test'},
                                event=event['event'],event_payload=event)
        logs=engine.store.logs(result['id'])
        twin=GitHubActionsDigitalTwin(seed)
        simulated_event=twin.dispatch('push')
        check=twin.create_check(simulated_event['after'],'omega-local')
        twin.complete_check(check,'success' if result['status']=='success' else 'failure')
        virtual=VirtualWorkerPool(seed).execute(workflow)
        return {'seed':seed,'event':event,'virtual_worker_pool':virtual,'digital_twin_checks':len(twin.checks),'result':result,'steps':engine.store.run(result['id'])['steps'],
                'log_count':len(logs),'secret_masked':'omega-secret-test' not in str(logs),
                'artifact_count':len(engine.store.run(result['id'])['artifacts'])}
