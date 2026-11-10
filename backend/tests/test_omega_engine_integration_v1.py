"""Integration evidence for recovery, HMAC audit and local REST simulation."""
import asyncio
from pathlib import Path
import httpx
import pytest
from omega_actions.config import Settings
from omega_actions.engine import Engine
from omega_actions.storage import StateStore
from omega_actions.audit_ledger import IntegrityLedger
from omega_actions.api import create_app


def test_state_store_recovers_only_interrupted_runs(tmp_path):
    store=StateStore(tmp_path/'state.db')
    store.create_run('running','ci',tmp_path,'push',{})
    store.run_status('running','running')
    store.job_status('running','build','running')
    store.create_run('finished','ci',tmp_path,'push',{})
    store.run_status('finished','success')
    assert store.recover_interrupted()==1
    assert store.run('running')['status']=='failure'
    assert store.run('finished')['status']=='success'


def test_engine_appends_audit_events_without_exposing_secrets(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    workflow=repo/'ci.yml'
    workflow.write_text('jobs:\n  check:\n    steps:\n      - run: echo audit-ok\n')
    settings=Settings(tmp_path/'home',unsafe_native=True)
    engine=Engine(settings)
    result=asyncio.run(engine.run(workflow,repo,secrets={'SENSITIVE':'never-print-this'}))
    assert result['status']=='success'
    ledger=IntegrityLedger(settings.home/'audit.db',key=(settings.home/'audit.key').read_bytes())
    assert ledger.verify()['records']>=2
    assert 'never-print-this' not in str(ledger.events())
    assert engine.telemetry.snapshot('ci_run')['count_total']==1


@pytest.mark.asyncio
async def test_local_simulation_endpoint_requires_session_token(tmp_path):
    app=create_app(Settings(tmp_path/'state'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as c:
        assert (await c.post('/api/omega/simulation',json={'seed':1,'jobs':16})).status_code==401
        ok=await c.post('/api/omega/simulation',headers={'X-OMEGA-Token':app.state.token},
                        json={'seed':1,'jobs':16,'workers':2,'failure_rate':0.1})
        assert ok.status_code==200
        assert ok.json()['scope']=='DETERMINISTIC_SIMULATION_ONLY'
        assert all(ok.json()['invariants'].values())
