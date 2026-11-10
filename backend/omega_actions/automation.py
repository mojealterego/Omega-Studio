"""Explicit approval, allowlist and durable audit for GitHub mutations."""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .remote import GitHubClient

class PolicyError(RuntimeError): pass

OPERATIONS=frozenset({'create_branch','put_file','create_pr','status'})

@dataclass(frozen=True)
class ActionPlan:
    id:str
    operation:str
    repo:str
    arguments:dict[str,Any]
    status:str
    expires_at:int

class ActionController:
    def __init__(self,db_path:Path,client:GitHubClient,*,allowed_repos:set[str],write_enabled:bool=False,ttl_seconds:int=600):
        self.db_path=Path(db_path);self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self.client=client;self.allowed_repos=allowed_repos;self.write_enabled=write_enabled;self.ttl_seconds=ttl_seconds
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,operation TEXT NOT NULL,repo TEXT NOT NULL,args TEXT NOT NULL,status TEXT NOT NULL,expires_at INTEGER NOT NULL,result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,plan_id TEXT NOT NULL,event TEXT NOT NULL,at INTEGER NOT NULL)')

    def _connect(self):
        db=sqlite3.connect(self.db_path,timeout=10)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=10000')
        return db

    def _validate(self,operation:str,repo:str,args:dict):
        if operation not in OPERATIONS: raise PolicyError('Operation not permitted')
        if repo not in self.allowed_repos: raise PolicyError('Repository not on allowlist')
        if not isinstance(args,dict): raise PolicyError('Arguments must be a JSON object')
        try:
            if operation=='create_branch':
                if set(args)!={'branch','sha'}: raise ValueError('Invalid arguments')
                if not args['branch'].startswith('omega/') or len(args['sha'])!=40: raise ValueError('Invalid branch or SHA')
            elif operation=='put_file':
                if not {'branch','path','content','message'}.issubset(args): raise ValueError('Missing fields')
                if not args['branch'].startswith('omega/'): raise ValueError('Write requires omega/*')
            elif operation=='create_pr':
                if not {'title','head'}.issubset(args) or not args['head'].startswith('omega/'):
                    raise ValueError('PR requires omega/*')
                if args.get('base','main')!='main': raise ValueError('Only main base permitted')
            elif operation=='status':
                if not {'sha','state','description'}.issubset(args): raise ValueError('Missing status fields')
        except (KeyError,TypeError,ValueError) as exc: raise PolicyError(str(exc)) from exc

    def propose(self,operation:str,repo:str,args:dict):
        self._validate(operation,repo,args)
        pid=uuid.uuid4().hex; expires=int(time.time())+self.ttl_seconds
        with self._connect() as db:
            db.execute('INSERT INTO plans(id,operation,repo,args,status,expires_at) VALUES(?,?,?,?,?,?)',
                       (pid,operation,repo,json.dumps(args,ensure_ascii=False),'proposed',expires))
            db.execute('INSERT INTO audit(plan_id,event,at) VALUES(?,?,?)',(pid,'proposed',int(time.time())))
        return {'id':pid,'operation':operation,'repo':repo,'arguments':args,'status':'proposed','expires_at':expires}

    def approve(self,pid:str):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE plans SET status=? WHERE id=? AND status=? AND expires_at>?',
                               ('approved',pid,'proposed',int(time.time()))).rowcount
            if not changed: raise PolicyError('Plan unavailable or expired')
            db.execute('INSERT INTO audit(plan_id,event,at) VALUES(?,?,?)',(pid,'approved',int(time.time())))
        return {'id':pid,'status':'approved'}

    def execute(self,pid:str):
        if not self.write_enabled: raise PolicyError('GitHub writes disabled by policy')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT operation,repo,args,status,expires_at FROM plans WHERE id=?',(pid,)).fetchone()
            if not row or row[3]!='approved' or row[4]<=int(time.time()): raise PolicyError('Plan not approved, already executed or expired')
            operation,repo,args,_,_=row; args=json.loads(args)
            self._validate(operation,repo,args)
            db.execute('UPDATE plans SET status=? WHERE id=?',('executing',pid))
            db.execute('INSERT INTO audit(plan_id,event,at) VALUES(?,?,?)',(pid,'executing',int(time.time())))
        try:
            if operation=='create_branch': result=self.client.create_branch(repo,**args)
            elif operation=='put_file': result=self.client.put_file(repo,**args)
            elif operation=='create_pr': result=self.client.create_pr(repo,**args)
            else: result=self.client.status(repo,**args)
            state='success'
        except Exception as exc:
            result={'error':type(exc).__name__,'detail':str(exc)[:300]};state='failure'
        with self._connect() as db:
            db.execute('UPDATE plans SET status=?,result=? WHERE id=?',(state,json.dumps(result,ensure_ascii=False)[:30000],pid))
            db.execute('INSERT INTO audit(plan_id,event,at) VALUES(?,?,?)',(pid,state,int(time.time())))
        return {'id':pid,'status':state,'result':result}

    def history(self,limit:int=50):
        with self._connect() as db:
            rows=db.execute('SELECT id,operation,repo,args,status,expires_at,result FROM plans ORDER BY rowid DESC LIMIT ?', (min(max(limit,1),100),)).fetchall()
        return [{'id':x[0],'operation':x[1],'repo':x[2],'arguments':json.loads(x[3]),'status':x[4],'expires_at':x[5],
                 'result':json.loads(x[6]) if x[6] else None} for x in rows]
