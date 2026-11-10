import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest
from omega_actions.remote import GitHubClient, GitHubError
from omega_actions.automation import ActionController, PolicyError, ActionPlan
from omega_actions.ai_bridge import ChatPlanner, AIUnavailable

class FakeTransport:
    def __init__(self): self.calls=[]
    def __call__(self, method,url,headers,body=None):
        self.calls.append((method,url,headers,body))
        if url.endswith('/user/repos?per_page=50'):
            return 200,{'content-type':'application/json'},json.dumps([{'full_name':'mojealterego/Digital-Life','private':True}]).encode()
        if url.endswith('/repos/mojealterego/Digital-Life'):
            return 200,{},b'{"full_name":"mojealterego/Digital-Life","default_branch":"main"}'
        if url.endswith('/repos/mojealterego/Digital-Life/git/refs'):
            return 201,{},b'{"ref":"refs/heads/omega/abc"}'
        return 200,{},b'{}'

def test_github_client_limits_host_and_encodes_paths():
    t=FakeTransport(); c=GitHubClient('sample-token',transport=t)
    assert c.repos()[0]['private'] is True
    assert c.repo('mojealterego/Digital-Life')['default_branch']=='main'
    assert t.calls[0][2]['Authorization']=='Bearer sample-token'
    with pytest.raises(ValueError): c.repo('mojealterego/../../etc')
    with pytest.raises(ValueError): c.repo('https://evil.invalid')

def test_plan_requires_approval_and_write_opt_in(tmp_path):
    t=FakeTransport(); c=GitHubClient('sample-token',transport=t)
    control=ActionController(tmp_path/'plans.db',c,allowed_repos={'mojealterego/Digital-Life'},write_enabled=False)
    p=control.propose('create_branch','mojealterego/Digital-Life',{'branch':'omega/abc','sha':'a'*40})
    with pytest.raises(PolicyError): control.execute(p['id'])
    control.approve(p['id'])
    with pytest.raises(PolicyError): control.execute(p['id'])
    assert not any(x[0]=='POST' for x in t.calls)

def test_approved_plan_executes_once_and_audits(tmp_path):
    t=FakeTransport(); c=GitHubClient('sample-token',transport=t)
    control=ActionController(tmp_path/'plans.db',c,allowed_repos={'mojealterego/Digital-Life'},write_enabled=True)
    p=control.propose('create_branch','mojealterego/Digital-Life',{'branch':'omega/abc','sha':'a'*40})
    control.approve(p['id'])
    result=control.execute(p['id'])
    assert result['status']=='success'
    assert sum(x[0]=='POST' for x in t.calls)==1
    with pytest.raises(PolicyError): control.execute(p['id'])
    assert control.history()[0]['status']=='success'

def test_rejects_main_branch_and_out_of_scope(tmp_path):
    control=ActionController(tmp_path/'plans.db',GitHubClient('x',transport=FakeTransport()),allowed_repos={'mojealterego/Digital-Life'},write_enabled=True)
    with pytest.raises(PolicyError): control.propose('create_branch','other/repo',{'branch':'omega/test','sha':'a'*40})
    with pytest.raises(PolicyError): control.propose('create_branch','mojealterego/Digital-Life',{'branch':'main','sha':'a'*40})
    with pytest.raises(PolicyError): control.propose('run_actions','mojealterego/Digital-Life',{})

def test_offline_chat_planner_no_cloud_cost():
    p=ChatPlanner()
    assert p.plan('Pokaż repozytoria')['operation']=='list_repos'
    assert p.plan('Uruchom workflow testów lokalnie')['operation']=='local_workflows'
    assert p.plan('Napisz nową funkcję')['operation']=='needs_model'

def test_expired_plan_is_not_executed(tmp_path):
    t=FakeTransport(); control=ActionController(tmp_path/'plans.db',GitHubClient('x',transport=t),allowed_repos={'mojealterego/Digital-Life'},write_enabled=True,ttl_seconds=1)
    p=control.propose('create_branch','mojealterego/Digital-Life',{'branch':'omega/abc','sha':'a'*40})
    control.approve(p['id'])
    with sqlite3.connect(tmp_path/'plans.db') as db: db.execute('UPDATE plans SET expires_at=0 WHERE id=?',(p['id'],))
    with pytest.raises(PolicyError): control.execute(p['id'])
    assert not t.calls

def test_github_write_cannot_create_cloud_actions_workflow():
    client=GitHubClient('x',transport=FakeTransport())
    with pytest.raises(ValueError):
        client.put_file('mojealterego/Digital-Life','omega/change','.github/workflows/bill.yml','on: push','add workflow')
