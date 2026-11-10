import httpx
from fastapi.testclient import TestClient
from omega_actions.api import create_app
from omega_actions.config import Settings


def test_provider_catalog_is_authenticated(tmp_path):
    app=create_app(Settings(home=tmp_path/'state'))
    with TestClient(app,base_url='http://localhost') as client:
        assert client.get('/api/providers').status_code==401
        response=client.get('/api/providers',headers={'X-OMEGA-Token':app.state.token})
        assert response.status_code==200
        assert any(p['id']=='anthropic' for p in response.json()['providers'])


def test_cloud_chat_requires_opt_in_and_encrypted_key(tmp_path,monkeypatch):
    monkeypatch.setenv('OMEGA_VAULT_PASSWORD','test-vault-password-for-unit-test')
    monkeypatch.setenv('OMEGA_ENABLE_PAID_AI','true')
    app=create_app(Settings(home=tmp_path/'state'))
    h={'X-OMEGA-Token':app.state.token}
    with TestClient(app,base_url='http://localhost') as client:
        request={'provider':'openai','model':'gpt-4.1-mini','message':'Cześć'}
        assert client.post('/api/providers/chat',json=request,headers=h).status_code==422
        request['confirm_cost']=True
        assert client.post('/api/providers/chat',json=request,headers=h).status_code==422
        saved=client.post('/api/secrets',json={'name':'OPENAI_API_KEY','value':'safe-test-secret'},headers=h)
        assert saved.status_code==200
        def handler(req):
            assert req.headers['Authorization']=='Bearer safe-test-secret'
            return httpx.Response(200,json={'choices':[{'message':{'content':'Działa'}}]})
        app.state.provider_transport=httpx.MockTransport(handler)
        response=client.post('/api/providers/chat',json=request,headers=h)
        assert response.status_code==200,response.text
        assert response.json()['text']=='Działa'
        assert 'safe-test-secret' not in response.text


def test_remote_env_guard_cannot_be_bypassed(tmp_path,monkeypatch):
    monkeypatch.setenv('OMEGA_VAULT_PASSWORD','test-password')
    monkeypatch.delenv('OMEGA_ENABLE_PAID_AI',raising=False)
    app=create_app(Settings(home=tmp_path/'state'))
    h={'X-OMEGA-Token':app.state.token}
    with TestClient(app,base_url='http://localhost') as client:
        r=client.post('/api/providers/chat',headers=h,json={'provider':'openai','model':'gpt-4.1-mini','message':'Cześć','confirm_cost':True})
        assert r.status_code==422
        assert 'wyłączone' in r.text
