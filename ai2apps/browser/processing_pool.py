"""Bounded task pools and Profile input serialization for shared WebAgents."""
import asyncio
from functools import wraps

async def ordered_pool(items, worker, limit):
    items=list(items);results=[None]*len(items);queue=asyncio.Queue()
    for index,item in enumerate(items):queue.put_nowait((index,item))
    async def consume():
        while not queue.empty():
            index,item=queue.get_nowait()
            results[index]=await worker(item)
    async with asyncio.TaskGroup() as group:
        for _ in range(min(limit,len(items))):group.create_task(consume())
    return results

class InputLock:
    def __init__(self):self.lock=asyncio.Lock();self.owner=None;self.depth=0
    async def __aenter__(self):
        task=asyncio.current_task()
        if self.owner is not task:await self.lock.acquire();self.owner=task
        self.depth+=1
    async def __aexit__(self,*args):
        self.depth-=1
        if not self.depth:self.owner=None;self.lock.release()

def serialized_input(fn):
    @wraps(fn)
    async def wrapped(self,*args,**kwargs):
        lock=getattr(self,'input_lock',None)
        if lock is None:return await fn(self,*args,**kwargs)
        async with lock:return await fn(self,*args,**kwargs)
    return wrapped
