"""Real contract tests for the multi-provider chat gateway, with HTTP transport fakes."""
import json
import pytest
import httpx
from omega_actions.providers import ProviderGateway, ProviderError, list_providers, get_provider


def test_catalog_has_distinct_supported_providers():
    providers = list_providers()
    ids = [p['id'] for p in providers]
    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    assert {'openai', 'anthropic', 'gemini', 'github-models', 'huggingface', 'ollama', 'llama-cpp', 'lm-studio'} <= set(ids)
    assert all(p['secret_name'].isidentifier() or p['secret_name'] == '' for p in providers)
    assert all('://' in p['endpoint'] for p in providers)


def test_catalog_rejects_unregistered_provider():
    with pytest.raises(ProviderError):
        get_provider('https://evil.example/api')


@pytest.mark.asyncio
async def test_openai_compatible_roundtrip_with_authorization():
    seen = {}
    def handler(request):
        seen['url'] = str(request.url)
        seen['auth'] = request.headers.get('Authorization')
        seen['payload'] = json.loads(request.content)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Witaj z modelu'}}], 'usage': {'total_tokens': 9}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ProviderGateway(client).chat('openai', 'gpt-4.1-mini', 'Cześć', api_key='test-secret', enable_remote=True)
    assert result['text'] == 'Witaj z modelu'
    assert result['usage']['total_tokens'] == 9
    assert seen['url'] == 'https://api.openai.com/v1/chat/completions'
    assert seen['auth'] == 'Bearer test-secret'
    assert seen['payload']['messages'] == [{'role':'user','content':'Cześć'}]
    assert 'test-secret' not in json.dumps(result)


@pytest.mark.asyncio
async def test_anthropic_request_and_response():
    def handler(request):
        assert request.headers['x-api-key'] == 'private-anthropic'
        assert request.headers['anthropic-version'] == '2023-06-01'
        payload = json.loads(request.content)
        assert payload['messages'][0]['content'] == 'Test'
        return httpx.Response(200, json={'content':[{'type':'text','text':'Odpowiedź'}], 'usage': {'input_tokens':3}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ProviderGateway(client).chat('anthropic', 'claude-sonnet-4-5', 'Test', api_key='private-anthropic', enable_remote=True)
    assert result['text'] == 'Odpowiedź'


@pytest.mark.asyncio
async def test_gemini_uses_header_not_url_query_key():
    def handler(request):
        assert request.headers['x-goog-api-key'] == 'gemini-secret'
        assert 'gemini-secret' not in str(request.url)
        assert json.loads(request.content)['contents'][0]['parts'][0]['text'] == 'Test'
        return httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':'OK'}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ProviderGateway(client).chat('gemini', 'gemini-2.5-flash', 'Test', api_key='gemini-secret', enable_remote=True)
    assert result['text'] == 'OK'


@pytest.mark.asyncio
async def test_local_ollama_does_not_require_remote_opt_in():
    def handler(request):
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        return httpx.Response(200,json={'message':{'content':'lokalnie'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await ProviderGateway(client).chat('ollama','llama3.2','Test')
    assert result['text']=='lokalnie'


@pytest.mark.asyncio
async def test_remote_provider_fails_closed_before_network_call():
    def handler(request):
        raise AssertionError('remote call forbidden')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway=ProviderGateway(client)
        with pytest.raises(ProviderError,match='wyłączone'):
            await gateway.chat('openai','gpt-4.1-mini','test',api_key='secret')
        with pytest.raises(ProviderError,match='Klucz'):
            await gateway.chat('openai','gpt-4.1-mini','test',enable_remote=True)


@pytest.mark.asyncio
async def test_provider_http_errors_are_redacted():
    def handler(request):
        return httpx.Response(401,text='Authorization: Bearer SECRET-DO-NOT-LOG')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError) as error:
            await ProviderGateway(client).chat('openai','gpt-4.1-mini','test',api_key='SECRET-DO-NOT-LOG',enable_remote=True)
    assert 'SECRET-DO-NOT-LOG' not in str(error.value)
    assert '401' in str(error.value)


@pytest.mark.asyncio
async def test_rejects_oversized_or_invalid_inputs():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,json={}))) as client:
        gw=ProviderGateway(client)
        for model,message in [('', 'hello'), ('good', ''), ('good','x'*17000), ('bad\nname','hi')]:
            with pytest.raises(ProviderError):
                await gw.chat('ollama',model,message)
