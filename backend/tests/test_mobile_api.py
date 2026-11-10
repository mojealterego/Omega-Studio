from fastapi.testclient import TestClient
from omega_actions.api import create_app
from omega_actions.config import Settings

def test_mobile_requires_token_and_disables_paid_ai(tmp_path):
    app=create_app(Settings(tmp_path))
    client=TestClient(app,base_url="http://localhost")
    assert client.get('/mobile').status_code==200
    assert client.get('/api/omega/status').status_code==401
    headers={'X-OMEGA-Token':app.state.token}
    status=client.get('/api/omega/status',headers=headers)
    assert status.status_code==200
    assert status.json()['paid_ai_enabled'] is False
    assert client.post('/api/omega/agent/run',headers=headers,json={'message':'show repos'}).status_code in (422,503)

def test_mcp_readonly_contract_and_origin_guard(tmp_path):
    app=create_app(Settings(tmp_path));client=TestClient(app,base_url="http://localhost")
    headers={'X-OMEGA-Token':app.state.token}
    r=client.post('/api/omega/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
    assert r.status_code==200
    names={x['name'] for x in r.json()['result']['tools']}
    assert 'omega_list_repos' in names
    assert 'omega_execute_plan' not in names
    assert client.post('/api/omega/mcp',headers={**headers,'Origin':'https://evil.example'},json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).status_code==403

def test_device_flow_stores_token_in_vault_not_http_response(tmp_path,monkeypatch):
    from omega_actions.vault import SecretVault
    monkeypatch.setenv('OMEGA_VAULT_PASSWORD','test-only-vault-password')
    app=create_app(Settings(tmp_path))
    class FakeOAuth:
        def start(self,client_id):
            return {'user_code':'ABCD-EFGH','verification_uri':'https://github.com/login/device','interval':5,'expires_in':900}
        def poll(self):
            return {'access_token':'ghu_test','refresh_token':'ghr_test','client_id':'Iv1.abc12345','expires_in':3600}
    app.state.oauth=FakeOAuth()
    client=TestClient(app,base_url='http://localhost')
    headers={'X-OMEGA-Token':app.state.token}
    assert client.post('/api/omega/oauth/start',headers=headers,json={'client_id':'Iv1.abc12345'}).status_code==200
    response=client.post('/api/omega/oauth/poll',headers=headers)
    assert response.json()['status']=='connected'
    assert 'ghu_test' not in response.text
    assert SecretVault(tmp_path/'vault.json','test-only-vault-password').get('GITHUB_TOKEN')=='ghu_test'
