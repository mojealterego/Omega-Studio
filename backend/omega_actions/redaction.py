"""Streaming Aho-Corasick secret masker with delayed output across chunk boundaries."""
from collections import deque

class StreamMasker:
    def __init__(self, secrets):
        words=[s for s in secrets if isinstance(s,str) and s]
        self.maximum=max((len(s) for s in words),default=1)
        self.next=[{}]; self.fail=[0]; self.out=[[]]
        for word in set(words):
            node=0
            for c in word:
                if c not in self.next[node]:
                    self.next[node][c]=len(self.next)
                    self.next.append({}); self.fail.append(0); self.out.append([])
                node=self.next[node][c]
            self.out[node].append(len(word))
        q=deque(self.next[0].values())
        while q:
            node=q.popleft()
            for c,child in self.next[node].items():
                f=self.fail[node]
                while f and c not in self.next[f]: f=self.fail[f]
                self.fail[child]=self.next[f].get(c,0)
                self.out[child].extend(self.out[self.fail[child]])
                q.append(child)
        self.node=0; self.buffer=deque(); self.intervals=deque(); self.position=-1; self.emitted=-1; self.masking=False
    def _emit(self,final=False):
        output=[]
        while self.buffer and (final or len(self.buffer)>=self.maximum):
            ch=self.buffer.popleft(); self.emitted+=1
            while self.intervals and self.intervals[0][1]<self.emitted: self.intervals.popleft()
            hidden=bool(self.intervals and self.intervals[0][0]<=self.emitted<=self.intervals[0][1])
            if hidden:
                if not self.masking: output.append('***')
                self.masking=True
            else:
                output.append(ch); self.masking=False
        return ''.join(output)
    def feed(self,text:str) -> str:
        result=[]
        for c in text:
            self.position+=1
            while self.node and c not in self.next[self.node]: self.node=self.fail[self.node]
            self.node=self.next[self.node].get(c,0)
            for length in self.out[self.node]:
                start=self.position-length+1
                if self.intervals and start<=self.intervals[-1][1]+1:
                    a,b=self.intervals.pop(); self.intervals.append((min(a,start),max(b,self.position)))
                else: self.intervals.append((start,self.position))
            self.buffer.append(c)
            result.append(self._emit())
        return ''.join(result)
    def finish(self):
        return self._emit(final=True)

def redact(text:str,secrets) -> str:
    masker=StreamMasker(secrets)
    return masker.feed(text)+masker.finish()
