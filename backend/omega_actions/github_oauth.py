"""GitHub App device flow (RFC 8628). Authorization stays outside the model."""
from __future__ import annotations
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

class OAuthError(RuntimeError):pass

def github_oauth_transport(path:str,params:dict):
    if path not in ('https://github.com/login/device/code','https://github.com/login/oauth/access_token'):
        raise OAuthError('Invalid OAuth endpoint')
    req=Request(path,data=urlencode(params).encode(),headers={'Accept':'application/json',
                 'Content-Type':'application/x-www-form-urlencoded','User-Agent':'OMEGA-Actions/2.0'},method='POST')
    try:
        with urlopen(req,timeout=20) as response:return json.loads(response.read(16000))
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:raise OAuthError('GitHub OAuth unavailable') from exc

class DeviceFlowManager:
    def __init__(self,transport=github_oauth_transport,clock=time.time):
        self.transport=transport;self.clock=clock;self.session=None

    def start(self,client_id:str):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{8,100}',client_id):raise OAuthError('Invalid GitHub App client ID')
        data=self.transport('https://github.com/login/device/code',{'client_id':client_id})
        if data.get('verification_uri')!='https://github.com/login/device':raise OAuthError('Untrusted verification URL')
        try:
            interval=max(5,int(data.get('interval',5)))
            expires=min(900,max(60,int(data.get('expires_in',900))))
            if not data['device_code'] or not data['user_code']:raise ValueError('Missing code')
        except (KeyError,TypeError,ValueError) as exc:raise OAuthError('Invalid GitHub device response') from exc
        now=self.clock()
        self.session={'client_id':client_id,'device_code':data['device_code'],'interval':interval,
                      'next_poll':now+interval,'expires_at':now+expires}
        return {'user_code':data['user_code'],'verification_uri':'https://github.com/login/device',
                'interval':interval,'expires_in':expires}

    def poll(self):
        session=self.session
        if not session:raise OAuthError('No active GitHub authorization')
        now=self.clock()
        if now>=session['expires_at']:
            self.session=None;raise OAuthError('GitHub authorization expired')
        if now<session['next_poll']:raise OAuthError('Wait for the GitHub polling interval')
        session['next_poll']=now+session['interval']
        data=self.transport('https://github.com/login/oauth/access_token',
            {'client_id':session['client_id'],'device_code':session['device_code'],
             'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
        if data.get('access_token'):
            self.session=None
            return {'access_token':data['access_token'],'token_type':data.get('token_type','bearer'),
                    'refresh_token':data.get('refresh_token'),
                    'expires_in':int(data.get('expires_in',0)),
                    'client_id':session['client_id']}
        error=data.get('error','unknown')
        if error=='authorization_pending':return {'status':'pending','retry_after':session['interval']}
        if error=='slow_down':
            session['interval']+=5
            session['next_poll']=now+session['interval']
            return {'status':'pending','retry_after':session['interval']}
        self.session=None
        raise OAuthError('GitHub authorization failed: '+str(error)[:80])
