"""Window-boundary publication: background writes never mutate published tags."""
import os
import threading
import time
from metal_bank import native


class WindowScheduler:
    def __init__(self, model, mailbox):
        self.model = model; self.mailbox = mailbox
        self.cv = threading.Condition(); self.io = threading.Lock()
        self.jobs = {}; self.closed = set(); self.step = 0; self.stop = False
        self.foreground = 0; self.error = None; self.reads = []; self.events = []; self.tokens = [];self.incoming=[]
        self.trace = os.environ.get('L2_TRACE_SCHEDULER') == '1'
        self.min_lead=int(os.environ.get('L2_MIN_LEAD_LAYERS','0'));assert self.min_lead in (0,1,2)
        self.thread = threading.Thread(target=self.loop, daemon=True); self.thread.start()

    def event(self, kind, **kw):
        if self.trace:self.events.append(dict(kind=kind, step=self.step, time=time.perf_counter(), **kw))

    def begin(self, step):
        with self.cv:
            assert not any(j['state'] in ('queued', 'loading') for j in self.jobs.values())
            self.step = step; self.jobs = {}; self.closed = set(); self.admitted = 0
            self.spent = 0; self.foreground_reads = 0; self.used = set();self.received=0
            self.resident = {l: set(b.main) | set(b.hot) for l,b in self.model.banks.items()}
            self.free = {l: list(range(48,56)) for l in range(40)}
            self.event('token_begin')

    def loop(self):
        try:
            while not self.stop:
                rows = self.mailbox.drain()
                with self.cv:
                    rows+=self.incoming;self.incoming=[]
                    for row in rows:
                        assert row[0] == self.step
                        self.received+=1
                        self.event('notice_received', candidates=len(row)-1)
                        if os.environ.get('L2_DISABLE_PREFETCH')=='1':continue
                        for code in row[1:]:
                            if code == -2:continue
                            if code < 0:raise RuntimeError('GPU notification failure')
                            layer,expert = divmod(code,384)
                            assert 0 <= layer < 40
                            if layer in self.closed:
                                self.event('expired',layer=layer,expert=expert);continue
                            frontier=max(self.closed,default=-1)+1
                            if layer<frontier+self.min_lead:
                                self.event('lead_rejected',layer=layer,expert=expert);continue
                            if expert in self.resident[layer] or (layer,expert) in self.jobs:continue
                            if self.spent >= 64 or not self.free[layer]:
                                self.event('budget_rejected',layer=layer,expert=expert,reason='reads' if self.spent>=64 else 'slots');continue
                            slot = self.free[layer].pop(0)
                            self.jobs[layer,expert] = dict(layer=layer,expert=expert,slot=slot,state='queued')
                            self.spent += 1; self.admitted += 1
                            self.event('queued',layer=layer,expert=expert)
                    job = next((j for j in self.jobs.values() if j['state']=='queued'),None) if not self.foreground else None
                if job is None:time.sleep(.0001);continue
                with self.io:
                    with self.cv:
                        if self.foreground or job['state']!='queued':continue
                        job['state']='loading'
                    bank=self.model.banks[job['layer']];begin=time.perf_counter()
                    count=native.preadv_fused_experts(bank.fd,0,bank.info['record_bytes'],[bank.records[job['expert']]],[job['slot']],*bank.arrays,bank.workers)
                    assert count==bank.info['record_bytes']
                    with self.cv:
                        job['state']='ready';job['ready_time']=time.perf_counter()
                        self.reads.append(dict(step=self.step,layer=job['layer'],expert=job['expert'],begin=begin,end=job['ready_time'],bytes=count))
                        self.cv.notify_all()
        except BaseException as error:
            with self.cv:self.error=error;self.cv.notify_all()

    def snapshot(self, layer):
        with self.cv:
            if self.error:raise self.error
            return {e:j['slot'] for (l,e),j in self.jobs.items() if l==layer and j['state']=='ready'}

    def enqueue_packet(self, codes):
        with self.cv:self.incoming.append([self.step,*codes])

    def close_layers(self, first, end, usage):
        with self.cv:
            for layer in range(first,end):
                self.closed.add(layer)
                self.event('layer_closed',layer=layer)
                for (l,e),job in self.jobs.items():
                    if l!=layer:continue
                    if usage[layer] & (1 << (job['slot']-48)):self.used.add((l,e))
                    if job['state']=='queued':
                        job['state']='cancelled';self.spent-=1
                        self.event('cancelled_deadline',layer=l,expert=e)

    def read(self, layer, ids, slots, original):
        with self.cv:self.foreground+=1
        began=time.perf_counter()
        try:
            with self.io:
                self.event('foreground_acquired',layer=layer,wait=time.perf_counter()-began)
                self.event('foreground_read_begin',layer=layer,experts=list(ids))
                original(ids,slots)
                self.event('foreground_read_end',layer=layer,experts=list(ids))
                self.foreground_reads+=len(ids)
        finally:
            with self.cv:self.foreground-=1

    def finish(self, expected_notices):
        began=time.perf_counter()
        # Notifications are explicitly evaluated as part of the final model roots.
        # A final mailbox drain must finish before reusing the next token's slots.
        while True:
            with self.cv:
                if self.error:raise self.error
                if self.received==expected_notices and len(self.closed)==40 and not any(j['state'] in ('queued','loading') for j in self.jobs.values()):break
            if time.perf_counter()-began>30:raise TimeoutError('L2 drain')
            time.sleep(.001)
        with self.cv:
            loaded=sum(j['state']=='ready' for j in self.jobs.values())
            assert loaded<=64
            self.tokens.append(dict(step=self.step,reads=loaded,used=len(self.used),unused=loaded-len(self.used),foreground=self.foreground_reads,tail_wait=time.perf_counter()-began))

    def close(self):
        self.stop=True;self.thread.join()
        if self.error:raise self.error
