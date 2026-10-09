"""Versioned, run-bound agent self-reports; never authoritative task completion."""
import json
import re


def request_report(prompt, run_id):
    example = {'version':1, 'run_id':run_id, 'outcome':'partial', 'summary':'',
               'completed':[], 'verification':[], 'remaining':[], 'question':''}
    return prompt + '\n\nAI2Apps result reporting contract:\n' + (
        'At the end of this execution, append exactly one fenced block labelled ai2apps-result '
        'to your final reply, containing JSON with the following fields. '
        'outcome must be completed, partial, waiting_user, or failed. '
        'Use completed only when all requested work is done; list actual verification and evidence, '
        'never invent checks. Use partial for unfinished work, waiting_user when a user answer or '
        'decision is needed (put the question in question), and failed when blocked by an execution error. '
        'completed, verification and remaining are arrays of strings. summary is a short description. '
        'For completed, remaining must be empty and question must be empty. '
        'Report in the user\'s language. This report is a self-assessment, not permission to mark the Todo done.\n'
    ) + '```ai2apps-result\n' + json.dumps(example, ensure_ascii=False) + '\n```'


def parse_report(text, run_id):
    blocks = re.findall(r'```ai2apps-result\s*\n(.*?)\n```', text, re.S)
    if not blocks: return {'result_report_state':'missing', 'result_report':None}
    invalid = {'result_report_state':'invalid', 'result_report':None}
    if len(blocks) != 1 or len(blocks[0]) > 32000: return invalid
    try:
        value = json.loads(blocks[0])
        if not isinstance(value, dict): return invalid
        if type(value.get('version')) is not int or value['version'] != 1 or value.get('run_id') != run_id: return invalid
        if value.get('outcome') not in ('completed','partial','waiting_user','failed'): return invalid
        for key in ('summary','question'):
            if not isinstance(value.get(key), str) or len(value[key]) > 4000: return invalid
        if not value['summary'].strip(): return invalid
        for key in ('completed','verification','remaining'):
            items=value.get(key)
            if not isinstance(items,list) or len(items)>50: return invalid
            if any(not isinstance(item,str) or len(item)>2000 for item in items): return invalid
        if value['outcome']=='completed' and (value['remaining'] or value['question'].strip()): return invalid
        if value['outcome']=='waiting_user' and not value['question'].strip(): return invalid
        keys=('version','run_id','outcome','summary','completed','verification','remaining','question')
        return {'result_report_state':'valid', 'result_report':{key:value[key] for key in keys}}
    except (ValueError, TypeError):
        return invalid


def turn_report(turn, run_id):
    # Only assistant messages, never command output or user-provided JSON.
    messages=[i for i in turn.get('items',[]) if i.get('type')=='agentMessage']
    finals=[i for i in messages if i.get('phase') in ('final_answer','final')]
    return parse_report((finals or messages)[-1].get('text','') if messages else '', run_id)
