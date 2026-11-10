"""Fail-closed, opt-in multi-provider chat gateway.

Provider endpoints are pinned to trusted HTTPS origins (or loopback for local
engines). Credentials never appear in URLs, errors, results, or debug logs.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import re
from urllib.parse import urlsplit
import httpx


class ProviderError(ValueError):
    """Safe, redacted error suitable for the UI."""


@dataclass(frozen=True)
class Provider:
    id: str
    title: str
    endpoint: str
    style: str = 'openai'
    secret_name: str = ''
    remote: bool = True


# Provider endpoint changes require an application update and a security review.
_CATALOG = (
    Provider('openai','OpenAI','https://api.openai.com/v1/chat/completions',secret_name='OPENAI_API_KEY'),
    Provider('anthropic','Anthropic','https://api.anthropic.com/v1/messages','anthropic','ANTHROPIC_API_KEY'),
    Provider('gemini','Google Gemini','https://generativelanguage.googleapis.com/v1beta/models','gemini','GEMINI_API_KEY'),
    Provider('github-models','GitHub Models','https://models.github.ai/inference/chat/completions',secret_name='GITHUB_TOKEN'),
    Provider('huggingface','Hugging Face Inference','https://router.huggingface.co/v1/chat/completions',secret_name='HF_TOKEN'),
    Provider('openrouter','OpenRouter','https://openrouter.ai/api/v1/chat/completions',secret_name='OPENROUTER_API_KEY'),
    Provider('groq','Groq','https://api.groq.com/openai/v1/chat/completions',secret_name='GROQ_API_KEY'),
    Provider('deepseek','DeepSeek','https://api.deepseek.com/chat/completions',secret_name='DEEPSEEK_API_KEY'),
    Provider('mistral','Mistral AI','https://api.mistral.ai/v1/chat/completions',secret_name='MISTRAL_API_KEY'),
    Provider('xai','xAI','https://api.x.ai/v1/chat/completions',secret_name='XAI_API_KEY'),
    Provider('together','Together AI','https://api.together.xyz/v1/chat/completions',secret_name='TOGETHER_API_KEY'),
    Provider('fireworks','Fireworks AI','https://api.fireworks.ai/inference/v1/chat/completions',secret_name='FIREWORKS_API_KEY'),
    Provider('perplexity','Perplexity','https://api.perplexity.ai/chat/completions',secret_name='PERPLEXITY_API_KEY'),
    Provider('cerebras','Cerebras','https://api.cerebras.ai/v1/chat/completions',secret_name='CEREBRAS_API_KEY'),
    Provider('sambanova','SambaNova','https://api.sambanova.ai/v1/chat/completions',secret_name='SAMBANOVA_API_KEY'),
    Provider('nvidia','NVIDIA NIM','https://integrate.api.nvidia.com/v1/chat/completions',secret_name='NVIDIA_API_KEY'),
    Provider('novita','Novita AI','https://api.novita.ai/v3/openai/chat/completions',secret_name='NOVITA_API_KEY'),
    Provider('hyperbolic','Hyperbolic','https://api.hyperbolic.xyz/v1/chat/completions',secret_name='HYPERBOLIC_API_KEY'),
    Provider('qwen','Qwen DashScope International','https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions',secret_name='DASHSCOPE_API_KEY'),
    Provider('siliconflow','SiliconFlow','https://api.siliconflow.cn/v1/chat/completions',secret_name='SILICONFLOW_API_KEY'),
    Provider('ollama','Ollama','http://127.0.0.1:11434/api/chat','ollama',remote=False),
    Provider('llama-cpp','llama.cpp Server','http://127.0.0.1:8080/v1/chat/completions',remote=False),
    Provider('lm-studio','LM Studio','http://127.0.0.1:1234/v1/chat/completions',remote=False),
    Provider('vllm','vLLM','http://127.0.0.1:8000/v1/chat/completions',remote=False),
)
_PROVIDERS = {p.id:p for p in _CATALOG}
_MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,127}\Z')


def get_provider(provider_id: str) -> Provider:
    if not isinstance(provider_id,str) or provider_id not in _PROVIDERS:
        raise ProviderError('Nieznany dostawca API')
    return _PROVIDERS[provider_id]


def list_providers() -> list[dict]:
    return [dict(id=p.id,title=p.title,endpoint=p.endpoint,style=p.style,
                 secret_name=p.secret_name,remote=p.remote) for p in _CATALOG]


class ProviderGateway:
    def __init__(self, client: httpx.AsyncClient):
        self.client=client

    async def chat(self, provider_id: str, model: str, message: str, *, api_key: str | None = None,
                   enable_remote: bool = False, max_tokens: int = 512) -> dict:
        p=get_provider(provider_id)
        if not isinstance(model,str) or not _MODEL.fullmatch(model):
            raise ProviderError('Niepoprawna nazwa modelu')
        if not isinstance(message,str) or not 1 <= len(message) <= 16000:
            raise ProviderError('Wiadomość musi mieć od 1 do 16000 znaków')
        if not isinstance(max_tokens,int) or isinstance(max_tokens,bool) or not 1 <= max_tokens <= 4096:
            raise ProviderError('Niepoprawny limit tokenów')
        if p.remote and not enable_remote:
            raise ProviderError('Zewnętrzne API są wyłączone — wymagają jawnej zgody na koszt')
        if p.remote and (not api_key or not isinstance(api_key,str)):
            raise ProviderError('Klucz API nie został skonfigurowany')
        url=p.endpoint
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if p.style=='gemini':
            if '/' in model or ':' in model: raise ProviderError('Niepoprawna nazwa modelu Gemini')
            url=f'{url}/{model}:generateContent'
            headers['x-goog-api-key']=api_key or ''
            payload={'contents':[{'role':'user','parts':[{'text':message}]}],
                     'generationConfig':{'maxOutputTokens':max_tokens}}
        elif p.style=='anthropic':
            headers['x-api-key']=api_key or ''
            headers['anthropic-version']='2023-06-01'
            payload={'model':model,'max_tokens':max_tokens,'messages':[{'role':'user','content':message}]}
        else:
            if p.remote:headers['Authorization']='Bearer '+(api_key or '')
            payload={'model':model,'messages':[{'role':'user','content':message}],'stream':False}
            if p.style!='ollama':payload['max_tokens']=max_tokens
        # Endpoint validation is independent of caller input; redirects never followed.
        target=urlsplit(url)
        if p.remote:
            if target.scheme!='https' or target.port not in (None,443) or target.username or target.password:
                raise ProviderError('Niedozwolony adres API')
        elif target.scheme!='http' or target.hostname!='127.0.0.1' or target.username or target.password:
            raise ProviderError('Niedozwolony lokalny endpoint')
        try:
            async with self.client.stream('POST',url,json=payload,headers=headers,follow_redirects=False,
                                          timeout=httpx.Timeout(60,connect=10)) as response:
                if response.status_code!=200:
                    raise ProviderError(f'Dostawca {p.id}: HTTP {response.status_code}')
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data)+len(chunk)>1024*1024:raise ProviderError('Odpowiedź przekracza limit 1 MiB')
                    data.extend(chunk)
        except ProviderError:
            raise
        except (httpx.HTTPError,TimeoutError) as exc:
            raise ProviderError(f'Dostawca {p.id}: błąd sieci lub timeout') from None
        try:
            parsed=json.loads(data)
            if p.style=='gemini':
                text=''.join(x.get('text','') for c in parsed['candidates'] for x in c['content']['parts'])
                usage=parsed.get('usageMetadata',{})
            elif p.style=='anthropic':
                text=''.join(x.get('text','') for x in parsed['content'] if x.get('type')=='text')
                usage=parsed.get('usage',{})
            elif p.style=='ollama':
                text=parsed['message']['content'];usage={}
            else:
                text=parsed['choices'][0]['message']['content'];usage=parsed.get('usage',{})
            if not isinstance(text,str) or not text:raise ValueError('Empty response')
            return {'provider':p.id,'model':model,'text':text[:200000],
                    'usage':usage if isinstance(usage,dict) else {}}
        except (ValueError,TypeError,KeyError,IndexError) as exc:
            raise ProviderError(f'Dostawca {p.id}: nieobsługiwany format odpowiedzi') from None
