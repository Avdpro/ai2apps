"""Bounded operation diagnostics; no input values, URLs or page contents."""
from __future__ import annotations

class InputDiagnostics:
    def __init__(self):
        self.events=[]
        self.attempted=0
        self.acknowledged=0
        self.uncertain=0
        self.not_sent=0
        self.readback='not_recorded'
        self.focus={'unhide_requests':0,'activate_requests':0,'system_foreground_observed':None}

    def begin(self,kind,context):
        item={'kind':kind,'context':context,'state':'dispatched','input_dispatched':True}
        self.attempted+=1
        self.readback='pending'
        self.events.append(item)
        if len(self.events)>64:self.events.pop(0)
        return item

    def finish(self,item,*,acknowledged=False,not_sent=False):
        if acknowledged:
            self.acknowledged+=1;item['state']='acknowledged'
        elif not_sent:
            self.not_sent+=1;self.attempted-=1;item.update(state='not_dispatched',input_dispatched=False)
            if not self.attempted:self.readback='not_required'
        else:
            self.uncertain+=1;item['state']='uncertain'

    def snapshot(self):
        return {'input_dispatched':bool(self.attempted),'commands_attempted':self.attempted,
            'commands_acknowledged':self.acknowledged,'commands_uncertain':self.uncertain,
            'readback_status':self.readback,
            'state':'uncertain' if self.uncertain else 'partial' if self.not_sent and self.acknowledged else 'acknowledged' if self.acknowledged else 'not_dispatched',
            'events':[dict(v) for v in self.events],'focus':dict(self.focus)}
