"""Adaptive bounded local scheduler with EWMA CPU/RAM admission control.

The 'Ricci-inspired' label is conceptual; this is not a differential-geometric Ricci flow solver.
"""
import asyncio
import psutil

class AdaptiveScheduler:
    def __init__(self,max_parallel:int):
        self.max_parallel=max(1,max_parallel)
        self.condition=asyncio.Condition()
        self.active=0
        self.cpu_ewma=0.0; self.mem_ewma=0.0
        self.alpha=0.25; self.samples=[]
    def sample(self)->dict:
        cpu=psutil.cpu_percent(interval=None)/100.0
        mem=psutil.virtual_memory().percent/100.0
        self.cpu_ewma=self.alpha*cpu+(1-self.alpha)*self.cpu_ewma
        self.mem_ewma=self.alpha*mem+(1-self.alpha)*self.mem_ewma
        target=max(1,min(self.max_parallel,round(self.max_parallel*(1-max(self.cpu_ewma,self.mem_ewma)*0.6))))
        measurement={'cpu':cpu,'ram':mem,'ewma_cpu':self.cpu_ewma,'ewma_ram':self.mem_ewma,'target':target,'active':self.active}
        self.samples.append(measurement)
        if len(self.samples)>10000: self.samples=self.samples[-1000:]
        return measurement
    async def acquire(self):
        async with self.condition:
            while True:
                measurement=self.sample()
                if self.active<measurement['target']:
                    self.active+=1
                    return measurement
                try: await asyncio.wait_for(self.condition.wait(),timeout=0.25)
                except asyncio.TimeoutError: continue
    async def release(self):
        async with self.condition:
            self.active=max(0,self.active-1)
            self.condition.notify_all()
