"""Localhost-only FastAPI server. Mutation requires a random bearer-like CSRF token."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
import uuid
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from .billing import estimate
from .compiler import load_workflow,compile_workflow
from .config import Settings
from .engine import Engine
from .storage import StateStore
from .vault import SecretVault
from .remote import GitHubClient, GitHubError
from .automation import ActionController, PolicyError
from .ai_bridge import ChatPlanner, AIUnavailable
from .agent_gateway import ToolGateway, ToolError, OpenAIOrchestrator
from .github_oauth import DeviceFlowManager, OAuthError
from .compatibility import inspect_workflow
from .model_studio import ModelCatalog, ModelParameters, GGUFError, HFDownload, HFError, hf_resolve_url
from .digital_twin import simulate_architecture
from .providers import ProviderGateway, ProviderError, get_provider, list_providers

class CompileRequest(BaseModel):
    workflow: str | None = None
    yaml_text: str | None = Field(default=None,max_length=1024*1024)
    repo: str | None = None

class RunRequest(CompileRequest):
    event: str = 'workflow_dispatch'
    executor: str = 'auto'

class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=4000)
    provider: str = "offline"
    model: str = "qwen2.5:3b"

class ProviderChatRequest(BaseModel):
    provider: str = Field(min_length=2,max_length=48)
    model: str = Field(min_length=1,max_length=128)
    message: str = Field(min_length=1,max_length=16000)
    max_tokens: int = Field(default=512,ge=1,le=4096)
    confirm_cost: bool = False

class OAuthStartRequest(BaseModel):
    client_id: str = Field(min_length=8,max_length=100)

class AgentRequest(BaseModel):
    message: str = Field(min_length=1,max_length=4000)
    model: str = "gpt-5.5"

class PlanRequest(BaseModel):
    operation: str
    repo: str
    arguments: dict

class ModelDownloadRequest(BaseModel):
    repo: str = Field(min_length=3,max_length=256)
    revision: str = Field(default="main",max_length=128)
    filename: str = Field(min_length=5,max_length=512)
    sha256: str | None = None

class SimulationRequest(BaseModel):
    seed: int = 20261110
    jobs: int = Field(default=500,ge=1,le=10000)
    workers: int = Field(default=4,ge=1,le=64)
    failure_rate: float = Field(default=0.15,ge=0,le=1)

class SecretRequest(BaseModel):
    name: str
    value: str


def create_app(settings:Settings|None=None)->FastAPI:
    settings=settings or Settings.from_env(); settings.prepare()
    store=StateStore(settings.home/'state.db'); engine=Engine(settings,store)
    token=secrets.token_urlsafe(32)
    app=FastAPI(title='OMEGA Actions Local',docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]'])
    app.state.token=token; app.state.engine=engine; app.state.tasks=set(); app.state.oauth=DeviceFlowManager()
    app.state.provider_transport=None
    static=Path(__file__).parent/'static'
    app.mount('/static',StaticFiles(directory=static),name='static')

    @app.middleware('http')
    async def guard(request:Request,call_next):
        if request.url.path.startswith('/api/'):
            if request.headers.get('X-OMEGA-Token')!=token:
                return JSONResponse({'detail':'Unauthorized'},status_code=401)
            origin=request.headers.get('origin')
            if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}' :
                return JSONResponse({'detail':'Origin rejected'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.get('/',response_class=HTMLResponse)
    async def index():
        html=(static/'index.html').read_text('utf-8').replace('OMEGA_SESSION_TOKEN',token)
        return HTMLResponse(html)

    def compiled(body:CompileRequest):
        if body.yaml_text is not None:
            parsed=load_workflow(body.yaml_text)
        elif body.workflow:
            parsed=load_workflow(Path(body.workflow).expanduser().resolve())
        else: raise HTTPException(422,'Workflow path or YAML text required')
        return compile_workflow(parsed,settings.max_matrix)

    @app.post('/api/compile')
    async def compile_endpoint(body:CompileRequest):
        try:
            c=compiled(body)
            return {'name':c.name,'jobs':[{'id':j.id,'base':j.base_id,'needs':j.needs,'matrix':j.matrix,'steps':len(j.raw.get('steps',[]))} for j in c.jobs.values()],
                    'order':c.order,'trigger':c.source.get('on',{})}
        except (ValueError,OSError,KeyError) as exc: raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/compatibility')
    async def omega_compatibility(body:CompileRequest):
        try:
            if body.yaml_text is not None:source=load_workflow(body.yaml_text)
            elif body.workflow:source=load_workflow(Path(body.workflow).expanduser().resolve())
            else:raise HTTPException(422,'Workflow required')
            return inspect_workflow(source)
        except (ValueError,OSError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.get('/api/workflows')
    async def workflows(repo:str):
        root=Path(repo).expanduser().resolve()
        if not root.is_dir(): raise HTTPException(404,'Repository folder not found')
        folder=root/'.github'/'workflows'
        return {'repo':str(root),'workflows':[str(p) for p in sorted(folder.glob('*')) if p.suffix in ('.yml','.yaml') and p.is_file()] if folder.exists() else []}

    @app.post('/api/runs')
    async def run_endpoint(body:RunRequest):
        if body.executor not in ('auto','native','docker'): raise HTTPException(422,'Invalid executor')
        if body.yaml_text is not None:
            # Uploaded workflow definitions are stored only in OMEGA's private state directory.
            folder=settings.home/'uploads'; folder.mkdir(exist_ok=True)
            path=folder/(uuid.uuid4().hex+'.yml')
            path.write_text(body.yaml_text,encoding='utf-8')
        elif body.workflow: path=Path(body.workflow).expanduser().resolve()
        else: raise HTTPException(422,'Workflow required')
        try: compile_workflow(load_workflow(path),settings.max_matrix)
        except (ValueError,OSError) as exc: raise HTTPException(422,str(exc)) from exc
        repo=Path(body.repo or (path.parent.parent.parent if path.parent.name=='workflows' else '.')).expanduser().resolve()
        if not repo.is_dir(): raise HTTPException(422,'Repository directory not found')
        rid=uuid.uuid4().hex
        async def execute():
            try:
                password=os.getenv('OMEGA_VAULT_PASSWORD')
                values=SecretVault(settings.home/'vault.json',password).all() if password else {}
                await engine.run(path,repo,secrets=values,event=body.event,run_id=rid,engine=body.executor)
            except Exception as exc:
                if store.run(rid):
                    store.log(rid,'engine',-1,f'Engine error: {type(exc).__name__}\n')
                    store.run_status(rid,'failure')
        task=asyncio.create_task(execute()); app.state.tasks.add(task)
        task.add_done_callback(app.state.tasks.discard)
        await asyncio.sleep(0)
        return {'id':rid,'status':'queued'}

    @app.get('/api/runs')
    async def list_runs(): return store.list_runs()

    @app.get('/api/runs/{run_id}')
    async def get_run(run_id:str):
        item=store.run(run_id)
        if not item: raise HTTPException(404,'Run not found')
        return item

    @app.post('/api/runs/{run_id}/cancel')
    async def cancel(run_id:str):
        if not engine.cancel(run_id): raise HTTPException(409,'Run is not active')
        return {'cancel_requested':True}

    @app.post('/api/runs/{run_id}/rerun')
    async def rerun(run_id:str):
        old=store.run(run_id)
        if not old: raise HTTPException(404,'Run not found')
        return await run_endpoint(RunRequest(workflow=old['payload']['workflow'],repo=old['repo'],event=old['event']))

    @app.get('/api/runs/{run_id}/events')
    async def events(run_id:str,after:int=0):
        if not store.run(run_id): raise HTTPException(404,'Run not found')
        async def stream():
            cursor=max(0,after)
            while True:
                rows=store.logs(run_id,cursor,200)
                for row in rows:
                    cursor=row['seq']; yield f'data: {json.dumps(row,ensure_ascii=False)}\n\n'
                item=store.run(run_id)
                if item and item['status'] in ('success','failure','cancelled') and not rows:
                    yield f'event: done\ndata: {json.dumps({"status":item["status"]})}\n\n'; break
                await asyncio.sleep(0.3)
        return StreamingResponse(stream(),media_type='text/event-stream')

    @app.get('/api/artifacts/{run_id}/{name}')
    async def artifact(run_id:str,name:str):
        record=store.get_artifact(run_id,name)
        if not record: raise HTTPException(404,'Artifact not found')
        path=Path(record['path']).resolve()
        if not path.is_relative_to(settings.home/'artifacts') or not path.is_file(): raise HTTPException(403,'Artifact path denied')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']: raise HTTPException(409,'Artifact checksum mismatch')
        try: engine.artifacts.verify(run_id,name)
        except (ValueError,OSError): raise HTTPException(409,'Artifact seal mismatch')
        return FileResponse(path,filename=f'{name}.zip',media_type='application/zip')

    @app.get('/api/billing')
    async def billing(usd_per_minute:float=0.008,pln_per_usd:float=4.0):
        try: return estimate(store,usd_per_minute,pln_per_usd)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc

    @app.get('/api/providers')
    async def provider_catalog():
        return {'providers':list_providers(),'cloud_enabled':os.getenv('OMEGA_ENABLE_PAID_AI','false').lower()=='true'}

    @app.post('/api/providers/chat')
    async def provider_chat(body:ProviderChatRequest):
        try:
            provider=get_provider(body.provider)
            allow_cloud=(os.getenv('OMEGA_ENABLE_PAID_AI','false').lower()=='true' and body.confirm_cost)
            if provider.remote and not allow_cloud:
                raise ProviderError('Zewnętrzne API są wyłączone — wymagana zgoda na koszt i konfiguracja operatora')
            credential=None
            if provider.secret_name:
                password=os.getenv('OMEGA_VAULT_PASSWORD')
                if not password:raise ProviderError('Skarbiec API nie został skonfigurowany')
                credential=SecretVault(settings.home/'vault.json',password).all().get(provider.secret_name)
            async with httpx.AsyncClient(transport=app.state.provider_transport,trust_env=False) as client:
                return await ProviderGateway(client).chat(body.provider,body.model,body.message,
                            api_key=credential,enable_remote=allow_cloud,max_tokens=body.max_tokens)
        except ProviderError as exc:
            raise HTTPException(422,str(exc)) from None

    @app.get('/api/secrets')
    async def secret_names():
        password=os.getenv('OMEGA_VAULT_PASSWORD')
        if not password: raise HTTPException(503,'Set OMEGA_VAULT_PASSWORD in server environment')
        return {'names':SecretVault(settings.home/'vault.json',password).list()}

    @app.post('/api/secrets')
    async def save_secret(body:SecretRequest):
        password=os.getenv('OMEGA_VAULT_PASSWORD')
        if not password: raise HTTPException(503,'Vault not configured')
        SecretVault(settings.home/'vault.json',password).set(body.name,body.value)
        return {'name':body.name,'saved':True}

    def github_client():
        credential=os.getenv('OMEGA_GITHUB_TOKEN','')
        if not credential:
            password=os.getenv('OMEGA_VAULT_PASSWORD')
            if password:
                vault=SecretVault(settings.home/'vault.json',password)
                values=vault.all()
                if values.get('GITHUB_TOKEN_EXPIRES_AT') and int(values['GITHUB_TOKEN_EXPIRES_AT'])<=int(time.time())+60:
                    if not values.get('GITHUB_REFRESH_TOKEN') or not values.get('GITHUB_CLIENT_ID'):
                        raise HTTPException(503,'GitHub OAuth token expired; reconnect account')
                    from .github_oauth import github_oauth_transport
                    try:
                        refreshed=github_oauth_transport('https://github.com/login/oauth/access_token',
                            {'client_id':values['GITHUB_CLIENT_ID'],'refresh_token':values['GITHUB_REFRESH_TOKEN'],
                             'grant_type':'refresh_token'})
                        if not refreshed.get('access_token'):raise ValueError('Refresh rejected')
                        values['GITHUB_TOKEN']=refreshed['access_token']
                        if refreshed.get('refresh_token'):values['GITHUB_REFRESH_TOKEN']=refreshed['refresh_token']
                        values['GITHUB_TOKEN_EXPIRES_AT']=str(int(time.time())+int(refreshed.get('expires_in',3600)))
                        for key in ('GITHUB_TOKEN','GITHUB_REFRESH_TOKEN','GITHUB_TOKEN_EXPIRES_AT'):
                            vault.set(key,values[key])
                    except (ValueError,OAuthError) as exc:
                        raise HTTPException(503,'GitHub token refresh failed; reconnect account') from exc
                credential=values.get('GITHUB_TOKEN','')
        if not credential: raise HTTPException(503,'GitHub token not configured on local backend')
        return GitHubClient(credential)

    def controller():
        allowed=set(x.strip() for x in os.getenv('OMEGA_ALLOWED_REPOS','mojealterego/Digital-Life').split(',') if x.strip())
        return ActionController(settings.home/'github_plans.db',github_client(),allowed_repos=allowed,
                                write_enabled=os.getenv('OMEGA_GITHUB_WRITE_ENABLED','false').lower()=='true')

    @app.get('/mobile',response_class=HTMLResponse)
    async def mobile():
        return HTMLResponse((static/'mobile.html').read_text('utf-8').replace('OMEGA_SESSION_TOKEN',token))

    @app.get('/api/omega/status')
    async def omega_status():
        return {'github_connected':bool(os.getenv('OMEGA_GITHUB_TOKEN') or os.getenv('OMEGA_VAULT_PASSWORD')),
                'github_write_enabled':os.getenv('OMEGA_GITHUB_WRITE_ENABLED','false').lower()=='true',
                'paid_ai_enabled':os.getenv('OMEGA_ENABLE_PAID_AI','false').lower()=='true',
                'allowed_repos':sorted(set(x.strip() for x in os.getenv('OMEGA_ALLOWED_REPOS','mojealterego/Digital-Life').split(',') if x.strip())),
                'github_actions_invocations':0,'mode':'local-only','version':'2.0.0'}

    @app.post('/api/omega/oauth/start')
    async def omega_oauth_start(body:OAuthStartRequest):
        if not os.getenv('OMEGA_VAULT_PASSWORD'):
            raise HTTPException(503,'Set OMEGA_VAULT_PASSWORD to encrypt the GitHub token')
        try:return await asyncio.to_thread(app.state.oauth.start,body.client_id)
        except OAuthError as exc:raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/oauth/poll')
    async def omega_oauth_poll():
        try:
            result=await asyncio.to_thread(app.state.oauth.poll)
            if 'access_token' not in result:return result
            password=os.getenv('OMEGA_VAULT_PASSWORD')
            if not password:raise HTTPException(503,'Vault password missing')
            vault=SecretVault(settings.home/'vault.json',password)
            vault.set('GITHUB_TOKEN',result['access_token'])
            if result.get('refresh_token'):
                vault.set('GITHUB_REFRESH_TOKEN',result['refresh_token'])
                vault.set('GITHUB_CLIENT_ID',result['client_id'])
            if result.get('expires_in'):
                vault.set('GITHUB_TOKEN_EXPIRES_AT',str(int(time.time())+int(result['expires_in'])))
            return {'status':'connected','saved_in_encrypted_vault':True}
        except OAuthError as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/omega/github/repos')
    async def omega_repos():
        try:
            permitted=set(x.strip() for x in os.getenv('OMEGA_ALLOWED_REPOS','mojealterego/Digital-Life').split(',') if x.strip())
            return [{'full_name':r['full_name'],'private':r.get('private',False)} for r in github_client().repos() if r.get('full_name') in permitted]
        except (GitHubError,ValueError) as exc: raise HTTPException(502,str(exc)) from exc

    @app.get('/api/omega/github/workflows')
    async def omega_github_workflows(repo:str):
        try:
            if repo not in set(x.strip() for x in os.getenv('OMEGA_ALLOWED_REPOS','mojealterego/Digital-Life').split(',') if x.strip()):
                raise HTTPException(403,'Repository not allowed')
            return github_client().workflows(repo)
        except (GitHubError,ValueError) as exc: raise HTTPException(502,str(exc)) from exc

    @app.post('/api/omega/chat')
    async def omega_chat(body:ChatRequest):
        try:
            planner=ChatPlanner()
            if body.provider=='offline': return planner.plan(body.message)
            if body.provider not in ('local','openai'): raise HTTPException(422,'Unknown AI provider')
            if body.provider=='openai' and not body.model.startswith(('gpt-','o')): raise HTTPException(422,'Invalid OpenAI model')
            return await asyncio.to_thread(planner.model_plan,body.message,provider=body.provider,
                                           model=body.model,api_key=os.getenv('OPENAI_API_KEY'))
        except (AIUnavailable,ValueError) as exc: raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/agent/run')
    async def omega_agent(body:AgentRequest):
        try:
            gateway=ToolGateway(github_client(),controller())
            orchestrator=OpenAIOrchestrator(gateway)
            return await asyncio.to_thread(orchestrator.run,body.message,
                                           api_key=os.getenv('OPENAI_API_KEY',''),model=body.model,
                                           enabled=os.getenv('OMEGA_ENABLE_PAID_AI','false').lower()=='true')
        except (ToolError,GitHubError,PolicyError,ValueError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/mcp')
    async def omega_mcp(request:Request):
        payload=await request.json()
        if not isinstance(payload,dict) or payload.get('jsonrpc')!='2.0':
            raise HTTPException(400,'JSON-RPC 2.0 required')
        method=payload.get('method'); rid=payload.get('id')
        if method=='initialize':
            result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},
                    'serverInfo':{'name':'omega-actions-local','version':'2.0.0'}}
        elif method=='ping':result={}
        elif method=='notifications/initialized':return JSONResponse({},status_code=202)
        elif method=='tools/list':
            result={'tools':[{'name':x['name'],'description':x['description'],'inputSchema':x['parameters']}
                             for x in ToolGateway.TOOL_SPECS]}
        elif method=='tools/call':
            params=payload.get('params',{})
            try:
                value=await asyncio.to_thread(ToolGateway(github_client(),controller()).invoke,
                                              params.get('name',''),params.get('arguments',{}))
                result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
            except (ToolError,GitHubError,PolicyError,ValueError) as exc:
                result={'content':[{'type':'text','text':str(exc)[:300]}],'isError':True}
        else:
            return {'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}}
        return {'jsonrpc':'2.0','id':rid,'result':result}

    @app.post('/api/omega/plans')
    async def omega_propose(body:PlanRequest):
        try: return controller().propose(body.operation,body.repo,body.arguments)
        except (PolicyError,ValueError) as exc: raise HTTPException(422,str(exc)) from exc

    @app.get('/api/omega/plans')
    async def omega_plans():
        try: return controller().history()
        except (PolicyError,ValueError) as exc: raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/plans/{plan_id}/approve')
    async def omega_approve(plan_id:str):
        try: return controller().approve(plan_id)
        except (PolicyError,ValueError) as exc: raise HTTPException(409,str(exc)) from exc

    @app.post('/api/omega/plans/{plan_id}/execute')
    async def omega_execute(plan_id:str):
        try: return await asyncio.to_thread(controller().execute,plan_id)
        except (PolicyError,ValueError) as exc: raise HTTPException(409,str(exc)) from exc

    @app.get('/api/models')
    async def models():
        return {'models':ModelCatalog(settings.home/'models').list()}

    @app.get('/api/models/parameters')
    async def model_parameters():
        p=settings.home/'model-parameters.json'
        if not p.exists():return ModelParameters().to_dict()
        try:return ModelParameters(**json.loads(p.read_text('utf-8'))).to_dict()
        except (OSError,ValueError,TypeError):raise HTTPException(409,'Invalid stored model parameters')

    @app.post('/api/models/parameters')
    async def save_model_parameters(body:dict):
        try:params=ModelParameters(**body).to_dict()
        except (TypeError,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
        p=settings.home/'model-parameters.json'
        tmp=p.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(params,indent=2),encoding='utf-8')
        if os.name!='nt':tmp.chmod(0o600)
        tmp.replace(p)
        return params

    @app.post('/api/models/hf/download')
    async def download_hf_model(body:ModelDownloadRequest):
        try:
            hf_resolve_url(body.repo,body.revision,body.filename)
            name=Path(body.filename).name
            target=settings.home/'models'/name
            if target.exists():raise HTTPException(409,'Model already exists')
            password=os.getenv('OMEGA_VAULT_PASSWORD')
            hf_token=SecretVault(settings.home/'vault.json',password).all().get('HF_TOKEN') if password else None
            return await asyncio.to_thread(HFDownload().download,body.repo,body.revision,body.filename,target,
                                           hf_token,body.sha256)
        except (ValueError,HFError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.get('/api/models/{name}')
    async def model_info(name:str):
        try:return ModelCatalog(settings.home/'models').inspect(name)
        except (ValueError,GGUFError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.post('/api/omega/simulation')
    async def simulation_endpoint(body:SimulationRequest):
        return await asyncio.to_thread(simulate_architecture,seed=body.seed,jobs=body.jobs,
                                       worker_count=body.workers,network_failure_rate=body.failure_rate)

    @app.get('/api/omega/telemetry')
    async def telemetry_endpoint():
        return {'ci_run':engine.telemetry.snapshot('ci_run'),
                'audit_head':engine.ledger.verify(),
                'scope':'LOCAL_RUNTIME_ONLY'}

    @app.get('/api/health')
    async def health(): return {'status':'ok','engine':'OMEGA Actions Local','version':'2.0.0'}
    return app
