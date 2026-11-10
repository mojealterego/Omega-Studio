"""SQLite WAL event store and execution history."""
import json
import sqlite3
import threading
import time
from pathlib import Path

class StateStore:
    def __init__(self,path:Path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(path,check_same_thread=False,timeout=30)
        with self.lock:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA busy_timeout=30000')
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, workflow TEXT NOT NULL, repo TEXT NOT NULL, event TEXT NOT NULL, status TEXT NOT NULL, started REAL NOT NULL, finished REAL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (run_id TEXT NOT NULL, id TEXT NOT NULL, status TEXT NOT NULL, started REAL, finished REAL, PRIMARY KEY(run_id,id));
            CREATE TABLE IF NOT EXISTS steps (run_id TEXT NOT NULL, job_id TEXT NOT NULL, idx INTEGER NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, duration REAL, PRIMARY KEY(run_id,job_id,idx));
            CREATE TABLE IF NOT EXISTS logs (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, job_id TEXT NOT NULL, step INTEGER NOT NULL, ts REAL NOT NULL, text TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS logs_run_idx ON logs(run_id,seq);
            CREATE TABLE IF NOT EXISTS artifacts (run_id TEXT NOT NULL, name TEXT NOT NULL, sha256 TEXT NOT NULL, path TEXT NOT NULL, files INTEGER NOT NULL, PRIMARY KEY(run_id,name));
            '''); self.db.commit()
    def execute(self,sql,args=()):
        with self.lock:
            cur=self.db.execute(sql,args); self.db.commit(); return cur
    def create_run(self,run_id,workflow,repo,event,payload):
        self.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(run_id,workflow,str(repo),event,'queued',time.time(),None,json.dumps(payload)))
    def recover_interrupted(self) -> int:
        """Mark interrupted runs as failed; call only when no other owner is executing."""
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            count=self.db.execute("UPDATE runs SET status='failure',finished=? WHERE status IN ('queued','running')",(time.time(),)).rowcount
            self.db.execute("UPDATE jobs SET status='cancelled',finished=? WHERE status IN ('queued','running')",(time.time(),))
            self.db.execute("UPDATE steps SET status='cancelled' WHERE status IN ('queued','running')")
            self.db.commit()
        return count

    def run_status(self,run_id,status):
        self.execute('UPDATE runs SET status=?,finished=? WHERE id=?',(status,time.time() if status in ('success','failure','cancelled') else None,run_id))
    def job_status(self,run_id,jid,status):
        with self.lock:
            self.db.execute('INSERT OR IGNORE INTO jobs(run_id,id,status,started,finished) VALUES(?,?,?,?,?)',(run_id,jid,'queued',None,None))
            self.db.execute('UPDATE jobs SET status=?,started=CASE WHEN ?="running" THEN COALESCE(started,?) ELSE started END,finished=CASE WHEN ? IN ("success","failure","cancelled","skipped") THEN ? ELSE NULL END WHERE run_id=? AND id=?',
                            (status,status,time.time(),status,time.time(),run_id,jid)); self.db.commit()
    def step_status(self,run_id,jid,idx,name,status,duration=None):
        self.execute('INSERT INTO steps(run_id,job_id,idx,name,status,duration) VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,job_id,idx) DO UPDATE SET status=excluded.status,duration=excluded.duration',(run_id,jid,idx,name,status,duration))
    def log(self,run_id,jid,idx,text):
        if text:
            self.execute('INSERT INTO logs(run_id,job_id,step,ts,text) VALUES(?,?,?,?,?)',(run_id,jid,idx,time.time(),text[:65536]))
    def logs(self,run_id,since=0,limit=2000):
        with self.lock:
            rows=self.db.execute('SELECT seq,job_id,step,ts,text FROM logs WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?', (run_id,since,limit)).fetchall()
        return [{'seq':r[0],'job':r[1],'step':r[2],'ts':r[3],'text':r[4]} for r in rows]
    def add_artifact(self,run_id,name,path,count,digest):
        self.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?,?)',(run_id,name,digest,str(path),count))
    def get_artifact(self,run_id,name):
        with self.lock:
            row=self.db.execute('SELECT path,sha256,files FROM artifacts WHERE run_id=? AND name=?',(run_id,name)).fetchone()
        return {'path':row[0],'sha256':row[1],'files':row[2]} if row else None
    def run(self,run_id):
        with self.lock:
            r=self.db.execute('SELECT id,workflow,repo,event,status,started,finished,payload FROM runs WHERE id=?',(run_id,)).fetchone()
            if not r: return None
            jobs=self.db.execute('SELECT id,status,started,finished FROM jobs WHERE run_id=?',(run_id,)).fetchall()
            steps=self.db.execute('SELECT job_id,idx,name,status,duration FROM steps WHERE run_id=? ORDER BY job_id,idx',(run_id,)).fetchall()
            artifacts=self.db.execute('SELECT name,sha256,files FROM artifacts WHERE run_id=?',(run_id,)).fetchall()
        return {'id':r[0],'workflow':r[1],'repo':r[2],'event':r[3],'status':r[4],'started':r[5],'finished':r[6],
                'payload':json.loads(r[7]),'jobs':{j[0]:{'status':j[1],'started':j[2],'finished':j[3]} for j in jobs},
                'steps':[{'job':s[0],'idx':s[1],'name':s[2],'status':s[3],'duration':s[4]} for s in steps],
                'artifacts':[{'name':a[0],'sha256':a[1],'files':a[2]} for a in artifacts]}
    def list_runs(self,limit=100):
        with self.lock:
            rows=self.db.execute('SELECT id FROM runs ORDER BY started DESC LIMIT ?',(limit,)).fetchall()
        return [self.run(row[0]) for row in rows]
    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close(); self.db=None
    def __del__(self):
        try: self.close()
        except (AttributeError,RuntimeError,sqlite3.ProgrammingError): return
