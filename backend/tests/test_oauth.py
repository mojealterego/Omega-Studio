import pytest
from omega_actions.github_oauth import DeviceFlowManager, OAuthError

class Transport:
    def __init__(self):self.calls=[]
    def __call__(self,path,data):
        self.calls.append((path,data))
        if path.endswith('/device/code'):
            return {'device_code':'secret-device','user_code':'ABCD-EFGH','verification_uri':'https://github.com/login/device','expires_in':900,'interval':5}
        return {'access_token':'ghu_test_token','token_type':'bearer'}

def test_device_flow_enforces_interval_and_never_returns_device_code():
    t=Transport();m=DeviceFlowManager(transport=t,clock=lambda:1000)
    response=m.start('Iv1.abc123456789')
    assert response['user_code']=='ABCD-EFGH'
    assert 'device_code' not in response
    with pytest.raises(OAuthError):m.poll()
    assert len(t.calls)==1
    m.clock=lambda:1005
    token=m.poll()
    assert token['access_token']=='ghu_test_token'
    with pytest.raises(OAuthError):m.poll()

def test_device_flow_rejects_untrusted_verification_url():
    def evil(path,data):return {'device_code':'x','user_code':'ABC','verification_uri':'https://evil.invalid','expires_in':900,'interval':5}
    with pytest.raises(OAuthError):DeviceFlowManager(transport=evil).start('Iv1_test123456789')

def test_device_flow_preserves_refresh_metadata_for_encrypted_storage():
    def transport(path,data):
        if path.endswith('/device/code'):
            return {'device_code':'d','user_code':'ABCD-EFGH','verification_uri':'https://github.com/login/device','expires_in':900,'interval':5}
        return {'access_token':'ghu_short','refresh_token':'ghr_long','expires_in':28800}
    m=DeviceFlowManager(transport=transport,clock=lambda:1000)
    m.start('Iv1.abc123456789');m.clock=lambda:1005
    result=m.poll()
    assert result['refresh_token']=='ghr_long'
    assert result['client_id']=='Iv1.abc123456789'
    assert result['expires_in']==28800
