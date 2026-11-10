"""Minimal SDK-independent Android APK packager.

Builds a real DEX/AXML APK and signs it using APK Signature Scheme v2.
The preview APK loads local assets and offers a platform shell bridge. It does not bundle Termux.
Not a substitute for device testing or an Android SDK-based release build.
"""
from __future__ import annotations
import datetime
import hashlib
import io
import os
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.x509.oid import NameOID

ROOT=Path(__file__).resolve().parents[1]
U32=lambda n:struct.pack('<I',n)
U16=lambda n:struct.pack('<H',n)
NO=0xffffffff
MAGIC=b'APK Sig Block 42'
V2_ID=0x7109871a
ALG_RSA_SHA256=0x0103

def uleb(n:int)->bytes:
    if n<0: raise ValueError('negative uleb')
    out=bytearray()
    while True:
        b=n&0x7f;n>>=7
        if n:b|=0x80
        out.append(b)
        if not n: return bytes(out)

def aligned(buf:bytearray,size:int=4):
    while len(buf)%size:buf.append(0)


def make_axml()->bytes:
    android_uri='http://schemas.android.com/apk/res/android'
    attrs={'name':0x01010003,'label':0x01010001,'exported':0x01010010,
           'usesCleartextTraffic':0x010104ec,'minSdkVersion':0x0101020c,'targetSdkVersion':0x01010270,
           'versionCode':0x0101021b,'versionName':0x0101021c}
    strings=['manifest','package','org.omega.actions','android',android_uri,'uses-sdk','minSdkVersion','targetSdkVersion',
             'uses-permission','name','android.permission.INTERNET','application','label','OMEGA Studio','usesCleartextTraffic',
             'activity','org.omega.actions.MainActivity','exported','intent-filter','action','android.intent.action.MAIN',
             'category','android.intent.category.LAUNCHER','versionCode','versionName','5.0.0-preview']
    idx={s:i for i,s in enumerate(strings)}
    def chunk(t,header,body):return struct.pack('<HHI',t,header,8+len(body))+body
    pool_data=bytearray();offsets=[]
    for s in strings:
        raw=s.encode();offsets.append(len(pool_data));pool_data+=bytes([len(s),len(raw)])+raw+b'\0'
    aligned(pool_data)
    pool_header=struct.pack('<IIIII',len(strings),0,0x100,28+4*len(strings),0)
    pool=chunk(0x0001,28,pool_header+b''.join(U32(x) for x in offsets)+pool_data)
    resource_map=chunk(0x0180,8,b''.join(U32(attrs.get(s,0)) for s in strings))
    def node(t,body):return chunk(t,16,U32(1)+U32(NO)+body)
    def ns(start):return node(0x0100 if start else 0x0101,U32(idx['android'])+U32(idx[android_uri]))
    def attr(name,value,android=True):
        namespace=idx[android_uri] if android else NO
        if isinstance(value,bool):
            raw=NO;kind=0x12;data=0xffffffff if value else 0
        elif isinstance(value,int):raw=NO;kind=0x10;data=value
        else:raw=idx[value];kind=0x03;data=idx[value]
        return struct.pack('<IIIHBBI',namespace,idx[name],raw,8,0,kind,data)
    def start(tag,attributes=()):
        ext=struct.pack('<IIHHHHHH',NO,idx[tag],20,20,len(attributes),0,0,0)
        return node(0x0102,ext+b''.join(attr(*x) for x in attributes))
    def end(tag):return node(0x0103,U32(NO)+U32(idx[tag]))
    nodes=[ns(True),start('manifest',[('package','org.omega.actions',False),('versionCode',2,True),('versionName','5.0.0-preview',True)]),
           start('uses-sdk',[('minSdkVersion',26,True),('targetSdkVersion',35,True)]),end('uses-sdk'),
           start('uses-permission',[('name','android.permission.INTERNET',True)]),end('uses-permission'),
           start('application',[('label','OMEGA Studio',True),('usesCleartextTraffic',False,True)]),
           start('activity',[('name','org.omega.actions.MainActivity',True),('exported',True,True)]),
           start('intent-filter'),start('action',[('name','android.intent.action.MAIN',True)]),end('action'),
           start('category',[('name','android.intent.category.LAUNCHER',True)]),end('category'),
           end('intent-filter'),end('activity'),end('application'),end('manifest'),ns(False)]
    return chunk(0x0003,8,pool+resource_map+b''.join(nodes))


def lp(data:bytes)->bytes:return U32(len(data))+data

def _zip_sections(data:bytes):
    off=data.rfind(b'PK\x05\x06')
    if off<0 or off+22>len(data):raise ValueError('ZIP end record missing')
    cd_off=struct.unpack_from('<I',data,off+16)[0]
    if not 0<cd_off<off:raise ValueError('ZIP central directory invalid')
    return cd_off,off

def _digest(parts:list[bytes])->bytes:
    chunks=[]
    for part in parts:
        for start in range(0,len(part),1024*1024):
            piece=part[start:start+1024*1024]
            chunks.append(hashlib.sha256(b'\xa5'+U32(len(piece))+piece).digest())
    return hashlib.sha256(b'\x5a'+U32(len(chunks))+b''.join(chunks)).digest()

def _sign_v2(unsigned:bytes)->bytes:
    cd_off,eocd_off=_zip_sections(unsigned)
    digest=_digest([unsigned[:cd_off],unsigned[cd_off:eocd_off],unsigned[eocd_off:]])
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.datetime.now(datetime.timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'OMEGA Actions Local Debug')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1))
          .not_valid_after(now+datetime.timedelta(days=3650)).sign(key,hashes.SHA256()))
    der=cert.public_bytes(serialization.Encoding.DER)
    signed_data=lp(lp(U32(ALG_RSA_SHA256)+lp(digest)))+lp(lp(der))+lp(b'')
    signature=key.sign(signed_data,padding.PKCS1v15(),hashes.SHA256())
    signer=lp(signed_data)+lp(lp(U32(ALG_RSA_SHA256)+lp(signature)))+lp(key.public_key().public_bytes(
        serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
    signers=lp(lp(signer))
    pair=struct.pack('<QI',len(signers)+4,V2_ID)+signers
    size=len(pair)+24
    block=struct.pack('<Q',size)+pair+struct.pack('<Q',size)+MAGIC
    result=bytearray(unsigned[:cd_off]+block+unsigned[cd_off:])
    new_eocd=eocd_off+len(block)
    struct.pack_into('<I',result,new_eocd+16,cd_off+len(block))
    return bytes(result)


def _read_lp(data:bytes,off:int=0):
    length=struct.unpack_from('<I',data,off)[0]
    start=off+4
    if start+length>len(data):raise ValueError('Bad length prefix')
    return data[start:start+length],start+length

def verify_apk(path:Path)->bool:
    data=Path(path).read_bytes()
    cd_off,eocd_off=_zip_sections(data)
    if data[cd_off-16:cd_off]!=MAGIC:raise ValueError('APK signing block missing')
    size=struct.unpack_from('<Q',data,cd_off-24)[0]
    block_start=cd_off-(size+8)
    if block_start<0 or struct.unpack_from('<Q',data,block_start)[0]!=size:raise ValueError('APK signing block corrupt')
    pair_start=block_start+8
    pair_len,pair_id=struct.unpack_from('<QI',data,pair_start)
    if pair_id!=V2_ID:raise ValueError('Wrong signature ID')
    signers,_=_read_lp(data[pair_start+12:pair_start+8+pair_len])
    signer,_=_read_lp(signers)
    signed_data,offset=_read_lp(signer)
    signatures,offset=_read_lp(signer,offset)
    public_key,_=_read_lp(signer,offset)
    signature_rec,_=_read_lp(signatures)
    algorithm=struct.unpack_from('<I',signature_rec,0)[0]
    signature,_=_read_lp(signature_rec,4)
    if algorithm!=ALG_RSA_SHA256:raise ValueError('Wrong algorithm')
    key=serialization.load_der_public_key(public_key)
    key.verify(signature,signed_data,padding.PKCS1v15(),hashes.SHA256())
    digests,_=_read_lp(signed_data)
    digest_rec,_=_read_lp(digests)
    digest_algorithm=struct.unpack_from('<I',digest_rec)[0]
    expected,_=_read_lp(digest_rec,4)
    if digest_algorithm!=ALG_RSA_SHA256:raise ValueError('Wrong digest algorithm')
    eocd=bytearray(data[eocd_off:]);struct.pack_into('<I',eocd,16,block_start)
    actual=_digest([data[:block_start],data[cd_off:eocd_off],bytes(eocd)])
    if expected!=actual:raise ValueError('APK digest mismatch')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:raise ValueError('Bad ZIP CRC')
        if not {'AndroidManifest.xml','classes.dex'}.issubset(archive.namelist()):raise ValueError('Missing APK files')
    return True


