import json
from pathlib import Path
from omega_actions.remote import GitHubClient
from omega_actions.automation import ActionController
from omega_actions.agent_gateway import ToolGateway, ToolError, OpenAIOrchestrator

class Transport:
    def __call__(self,method,url,headers,body=None):
        if url.endswith('/user/repos?per_page=50'):
            return 200,{},b'[{"full_name":"mojealterego/Digital-Life","private":true},{"full_name":"other/secret","private":true}]'
        if url.endswith('/repos/mojealterego/Digital-Life/contents/.github/workflows'):
            return 200,{},b'[{"name":"python-ci.yml","path":".github/workflows/python-ci.yml"}]'
        return 200,{},b'{}'

def gateway(tmp_path):
    client=GitHubClient('test',transport=Transport())
    ctl=ActionController(tmp_path/'plans.db',client,allowed_repos={'mojealterego/Digital-Life'},write_enabled=False)
    return ToolGateway(client,ctl)

def test_tool_gateway_filters_private_repos_and_never_executes_write(tmp_path):
    g=gateway(tmp_path)
    assert g.invoke('omega_list_repos',{})==[{'full_name':'mojealterego/Digital-Life','private':True}]
    assert g.invoke('omega_list_workflows',{'repo':'mojealterego/Digital-Life'})[0]['name']=='python-ci.yml'
    p=g.invoke('omega_propose_branch',{'repo':'mojealterego/Digital-Life','branch':'omega/ai','sha':'a'*40})
    assert p['status']=='proposed'
    try:g.invoke('omega_execute_plan',{'id':p['id']})
    except ToolError:pass
    else:raise AssertionError('Agent executed a write')

def test_openai_agent_rejects_disabled_paid_provider(tmp_path):
    g=gateway(tmp_path)
    agent=OpenAIOrchestrator(g,transport=lambda *a,**k:None)
    try:agent.run('pokaż repozytoria',api_key='key',model='gpt-5.5',enabled=False)
    except ToolError:pass
    else:raise AssertionError('Paid provider bypass')

def test_openai_agent_executes_only_approved_tool_contract(tmp_path):
    g=gateway(tmp_path)
    calls=[]
    def fake_api(payload,key):
        calls.append(payload)
        if len(calls)==1:
            return {'id':'resp-1','output':[{'type':'function_call','call_id':'call-1','name':'omega_list_repos','arguments':'{}'}]}
        return {'id':'resp-2','output':[{'type':'message','content':[{'type':'output_text','text':'Dostępne jest jedno repozytorium.'}]}]}
    result=OpenAIOrchestrator(g,transport=fake_api).run('pokaż repozytoria',api_key='key',model='gpt-5.5',enabled=True)
    assert len(calls)==2
    assert calls[1]['store'] is False
    assert calls[1]['input'][-1]['type']=='function_call_output'
    assert 'jedno repozytorium' in result['answer']
