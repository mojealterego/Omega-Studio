"""Local CLI: execute, validate, serve, watch, simulate, vault and optional hooks."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import getpass
from .compiler import load_workflow,compile_workflow
from .config import Settings
from .engine import Engine
from .hooks import install_hook
from .simulator import simulate
from .schedule import matches
from datetime import datetime
from .storage import StateStore
from .vault import SecretVault
from .act_bridge import ActBridge, ActError
from .digital_twin import simulate_architecture
from .audit_ledger import IntegrityLedger, load_or_create_key

def main(argv=None)->int:
    parser=argparse.ArgumentParser(prog='omega-actions',description='Local GitHub-style CI/CD engine; no GitHub-hosted jobs')
    sub=parser.add_subparsers(dest='cmd',required=True)
    def work(p):
        p.add_argument('workflow',type=Path)
        p.add_argument('--repo',type=Path)
    r=sub.add_parser('run'); work(r)
    r.add_argument('--unsafe-native',action='store_true',help='Explicitly permit untrusted shell commands on this machine')
    r.add_argument('--executor',choices=('auto','native','docker'),default='auto')
    r.add_argument('--event',default='workflow_dispatch')
    c=sub.add_parser('validate'); work(c)
    a=sub.add_parser('act'); work(a); a.add_argument('--job'); a.add_argument('--timeout',type=int,default=3600)
    s=sub.add_parser('serve'); s.add_argument('--host',default='127.0.0.1'); s.add_argument('--port',type=int,default=8765); s.add_argument('--unsafe-native',action='store_true')
    v=sub.add_parser('vault'); v.add_argument('action',choices=('set','get','list','delete')); v.add_argument('key',nargs='?')
    sim=sub.add_parser('simulate'); work(sim); sim.add_argument('--seed',type=int,default=2026)
    hook=sub.add_parser('hook'); hook.add_argument('event',choices=('pre-push','post-commit')); work(hook)
    watch=sub.add_parser('watch'); work(watch); watch.add_argument('--interval',type=int,default=15); watch.add_argument('--unsafe-native',action='store_true')
    twin=sub.add_parser('digital-twin',help='Run seeded external-architecture simulation (no network)')
    twin.add_argument('--seed',type=int,default=20261110)
    twin.add_argument('--jobs',type=int,default=500)
    twin.add_argument('--workers',type=int,default=4)
    twin.add_argument('--failure-rate',type=float,default=0.15)
    audit=sub.add_parser('audit-verify',help='Verify local authenticated audit chain')
    recover=sub.add_parser('recover-interrupted',help='Mark stale CI runs failed; only when runner is stopped')
    args=parser.parse_args(argv)
    settings=Settings.from_env()
    if getattr(args,'unsafe_native',False):
        settings=Settings(settings.home,unsafe_native=True,max_parallel=settings.max_parallel,default_engine=settings.default_engine)
    try:
        if args.cmd=='digital-twin':
            result=simulate_architecture(seed=args.seed,jobs=args.jobs,worker_count=args.workers,
                                         network_failure_rate=args.failure_rate)
            print(json.dumps(result,indent=2,ensure_ascii=False))
            return 0 if all(result['invariants'].values()) else 1
        if args.cmd=='audit-verify':
            result=IntegrityLedger(settings.home/'audit.db',key=load_or_create_key(settings.home/'audit.key')).verify()
            print(json.dumps(result,indent=2))
            return 0
        if args.cmd=='recover-interrupted':
            count=StateStore(settings.home/'state.db').recover_interrupted()
            print(json.dumps({'interrupted_runs_closed':count}))
            return 0
        if args.cmd=='validate':
            result=compile_workflow(load_workflow(args.workflow),settings.max_matrix)
            print(json.dumps({'name':result.name,'jobs':list(result.jobs),'order':result.order},indent=2)); return 0
        if args.cmd=='serve':
            if args.host not in ('127.0.0.1','localhost','::1'):
                parser.error('Dashboard may only bind to localhost')
            import uvicorn
            from .api import create_app
            print(f'OMEGA Dashboard: http://127.0.0.1:{args.port}',flush=True)
            app=create_app(settings)
            if os.getenv('OMEGA_SHOW_SESSION_TOKEN','0')=='1':
                print('Local MCP X-OMEGA-Token: '+app.state.token,flush=True)
            uvicorn.run(app,host=args.host,port=args.port,log_level='warning'); return 0
        if args.cmd=='vault':
            pw=os.getenv('OMEGA_VAULT_PASSWORD') or getpass.getpass('Vault password: ')
            vault=SecretVault(settings.home/'vault.json',pw)
            if args.action=='list': print('\n'.join(vault.list())); return 0
            if not args.key: parser.error('Vault key required')
            if args.action=='set': vault.set(args.key,getpass.getpass('Secret value: '))
            elif args.action=='get': print(vault.get(args.key))
            else: vault.delete(args.key)
            return 0
        repo=(args.repo or args.workflow.parent.parent.parent).expanduser().resolve()
        if args.cmd=='act':
            result=ActBridge().run(repo,args.workflow,args.job,args.timeout)
            print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['status']=='success' else 1
        if args.cmd=='hook':
            print(install_hook(repo,args.event,args.workflow)); return 0
        if args.cmd=='simulate':
            result=asyncio.run(simulate(args.workflow,repo,args.seed)); print(json.dumps(result,indent=2)); return 0 if result['result']['status']=='success' else 1
        if args.cmd=='run':
            engine=Engine(settings,StateStore(settings.home/'state.db'))
            pw=os.getenv('OMEGA_VAULT_PASSWORD')
            secrets=SecretVault(settings.home/'vault.json',pw).all() if pw else {}
            result=asyncio.run(engine.run(args.workflow,repo,secrets=secrets,event=args.event,engine=args.executor))
            print(json.dumps(result,indent=2)); return 0 if result['status']=='success' else 1
        if args.cmd=='watch':
            if args.interval<1: parser.error('Interval must be positive')
            previous=None; last_schedule=None
            print(f'Watching {repo} every {args.interval}s; Ctrl-C to stop',flush=True)
            while True:
                commit=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
                if previous is None: previous=commit
                elif commit!=previous:
                    previous=commit
                    engine=Engine(settings,StateStore(settings.home/'state.db'))
                    result=asyncio.run(engine.run(args.workflow,repo,event='push',event_payload={'after':commit}))
                    print(json.dumps(result),flush=True)
                source=load_workflow(args.workflow)
                triggers=source.get('on',{})
                schedule=triggers.get('schedule',[]) if isinstance(triggers,dict) else []
                minute=datetime.now().strftime('%Y-%m-%dT%H:%M')
                if schedule and minute!=last_schedule:
                    last_schedule=minute
                    for entry in schedule:
                        if matches(str(entry.get('cron','')),datetime.now()):
                            engine=Engine(settings,StateStore(settings.home/'state.db'))
                            result=asyncio.run(engine.run(args.workflow,repo,event='schedule'))
                            print(json.dumps(result),flush=True)
                time.sleep(args.interval)
    except (ValueError,OSError,RuntimeError,subprocess.CalledProcessError,ActError) as exc:
        print(f'OMEGA error: {exc}',file=sys.stderr); return 2
    return 0
