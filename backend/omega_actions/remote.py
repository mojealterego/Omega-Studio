"""Bounded GitHub REST adapter. Never invokes GitHub-hosted Actions."""
from __future__ import annotations
import base64
import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$')
SHA_PATTERN = re.compile(r'^[0-9a-fA-F]{40}$')

class GitHubError(RuntimeError):
    def __init__(self,status:int,message:str):
        super().__init__(f'GitHub API HTTP {status}: {message[:300]}')
        self.status=status

def http_transport(method:str,url:str,headers:dict[str,str],body:bytes|None=None):
    req=Request(url,data=body,headers=headers,method=method)
    try:
        with urlopen(req,timeout=20) as response:
            return response.status,dict(response.headers),response.read(2_000_001)
    except HTTPError as exc:
        return exc.code,dict(exc.headers),exc.read(8192)
    except URLError as exc:
        raise GitHubError(0,'Connection unavailable') from exc

class GitHubClient:
    BASE='https://api.github.com'
    def __init__(self,token:str,transport=http_transport):
        if not token or '\n' in token or '\r' in token: raise ValueError('Invalid GitHub credential')
        self._token=token; self._transport=transport

    def _call(self,method:str,path:str,data:dict|None=None):
        if not path.startswith('/') or '://' in path or '\\' in path or '..' in path:
            raise ValueError('Unsafe API path')
        headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+self._token,
                 'X-GitHub-Api-Version':'2022-11-28','User-Agent':'OMEGA-Actions-Local/2.0'}
        payload=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
        if payload is not None: headers['Content-Type']='application/json'
        status,_,body=self._transport(method,self.BASE+path,headers,payload)
        if status<200 or status>=300:
            raise GitHubError(status,body.decode('utf-8','replace'))
        try: return json.loads(body)
        except (ValueError,UnicodeError) as exc: raise GitHubError(status,'Invalid JSON') from exc

    @staticmethod
    def repo_path(repo:str)->str:
        if not REPO_PATTERN.fullmatch(repo) or any(x in ('.','..') for x in repo.split('/')):
            raise ValueError('Repository must be owner/name')
        return '/repos/'+repo

    def repos(self): return self._call('GET','/user/repos?per_page=50')
    def repo(self,repo:str): return self._call('GET',self.repo_path(repo))
    def workflows(self,repo:str):
        try:
            data=self._call('GET',self.repo_path(repo)+'/contents/.github/workflows')
        except GitHubError as exc:
            if exc.status==404: return []
            raise
        if not isinstance(data,list): raise GitHubError(200,'Unexpected workflows response')
        return [{'name':x.get('name'),'path':x.get('path')} for x in data if x.get('name','').endswith(('.yml','.yaml'))]

    def create_branch(self,repo:str,branch:str,sha:str):
        if not branch.startswith('omega/') or not re.fullmatch(r'omega/[A-Za-z0-9._/-]{1,100}',branch) or '..' in branch:
            raise ValueError('Only omega/* branches are permitted')
        if not SHA_PATTERN.fullmatch(sha): raise ValueError('Invalid commit SHA')
        return self._call('POST',self.repo_path(repo)+'/git/refs',{'ref':'refs/heads/'+branch,'sha':sha})

    def put_file(self,repo:str,branch:str,path:str,content:str,message:str,sha:str|None=None):
        if not re.fullmatch(r'omega/[A-Za-z0-9._/-]{1,100}',branch) or '..' in branch: raise ValueError('Write requires omega/* branch')
        if path.startswith('/') or '\\' in path or any(p in ('.','..','') for p in path.split('/')) or path.startswith('.github/workflows/'):
            raise ValueError('Invalid file path')
        if not message.strip() or len(content.encode())>512_000: raise ValueError('Empty message or file too large')
        data={'message':message[:200], 'branch':branch,
              'content':base64.b64encode(content.encode('utf-8')).decode('ascii')}
        if sha:
            if not SHA_PATTERN.fullmatch(sha): raise ValueError('Invalid blob SHA')
            data['sha']=sha
        safe='/'.join(quote(part,safe='') for part in path.split('/'))
        return self._call('PUT',self.repo_path(repo)+'/contents/'+safe,data)

    def create_pr(self,repo:str,title:str,head:str,base:str='main',body:str=''):
        if not re.fullmatch(r'omega/[A-Za-z0-9._/-]{1,100}',head) or '..' in head or not title.strip() or base!= 'main':
            raise ValueError('Pull request must originate from omega/* into main')
        return self._call('POST',self.repo_path(repo)+'/pulls',{'title':title[:200],'head':head,'base':base,'body':body[:10000],'draft':True})

    def status(self,repo:str,sha:str,state:str,description:str):
        if not SHA_PATTERN.fullmatch(sha) or state not in ('pending','success','failure','error'):
            raise ValueError('Invalid status request')
        return self._call('POST',self.repo_path(repo)+'/statuses/'+sha,
                          {'state':state,'context':'omega-actions/local','description':description[:140]})
