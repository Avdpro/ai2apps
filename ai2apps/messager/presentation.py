"""User-facing projection of verified task results; never execution authority."""
import re


def dialogue_language(text, fallback):
    """Choose between supported receipt languages from the user's prose."""
    prose = re.sub(r'https?://\S+|`[^`]*`', ' ', text)
    han = len(re.findall(r'[\u3400-\u9fff]', prose))
    latin_words = len(re.findall(r'[A-Za-z]+', prose))
    if han >= 3 and han >= latin_words:
        return 'zh'
    if latin_words >= 4 and latin_words > han:
        return 'en'
    return 'zh' if fallback.startswith('zh') else 'en'


FAILURE_REASONS = {
    'tool_name_correction_exhausted': (
        'Bot 收到纠正提示后仍提交了无效工具名，这次调用没有执行',
        'The Bot still used an invalid tool name after receiving correction guidance. That call did not execute',
    ),
    'tool_not_available': (
        '尝试调用的能力在本次执行中不可用',
        'The capability it tried to call was unavailable in this run',
    ),
    'session_memory_unavailable': (
        '读取任务上下文时出现问题',
        'Task context could not be prepared',
    ),
    'approval_denied': (
        '所需操作的授权已拒绝或取消',
        'The requested operation was denied or cancelled',
    ),
    'capability_policy_denied': (
        '执行策略拒绝了所需操作',
        'The execution policy blocked a required operation',
    ),
    'uncertain_execution': (
        '有操作的结果无法确认',
        'The outcome of an operation could not be verified',
    ),
    'model_rate_limited': ('模型服务限流，本次执行未能继续', 'The run could not continue because the model was rate limited'),
    'max_steps_exceeded': ('本次执行已达到步骤上限', 'The run reached its step limit'),
    'provider_ambiguous': ('无法确定本次调用所属的应用，操作未执行', 'The App for this call could not be identified. The operation did not execute'),
    'app_unavailable': ('本次调用所属的应用不可用，操作未执行', 'The App for this call was unavailable. The operation did not execute'),
    'provider_not_authorized': ('所选能力或审核入口不在本次任务的授权范围，操作未提交', 'The selected capability or review entry was outside this task authorization. No operation was submitted'),
    'provider_binding_changed': ('所选能力或审核入口的版本已变化，操作未提交', 'The selected capability or review entry changed. No operation was submitted'),
}

NEXT_STEPS = {
    'provider_not_authorized': ('核对当前可用能力和访问权限，再发起尚未完成的部分。', 'Review the available capabilities and access permissions, then request the unfinished work.'),
    'provider_binding_changed': ('重新读取当前能力声明，再发起尚未完成的部分。', 'Read the current capability declaration, then request the unfinished work.'),
    'provider_ambiguous': ('明确要用的应用或提供更具体的目标，再发起尚未完成的部分。', 'Specify the App or narrow the target, then request the unfinished work.'),
    'app_unavailable': ('恢复所需应用后，再发起尚未完成的部分。', 'Restore the required App, then request the unfinished work.'),
    'approval_denied': ('如仍需要这项操作，可单独发起并核对授权请求。', 'If the operation is still needed, request it separately and review its approval.'),
    'capability_policy_denied': ('先核对任务允许的能力，再决定如何完成剩余部分。', 'Review the capabilities allowed for this task before requesting the remaining work.'),
    'uncertain_execution': ('先核对操作是否已生效，再决定如何继续。', 'Check whether the operation took effect before deciding how to proceed.'),
    'model_rate_limited': ('模型服务恢复后可继续尚未完成的部分。', 'Continue the unfinished work when the model service is available.'),
    'max_steps_exceeded': ('可缩小剩余范围，或在允许的设置里扩大预算后继续未完成的部分。', 'Narrow the remaining work, or increase the budget where available and request the unfinished part.'),
}

TERMINAL_REASONS = {
    'cancelled': ('执行已取消', 'Execution was cancelled'),
    'interrupted': ('执行中断', 'Execution was interrupted'),
    'timed_out': ('执行超时', 'Execution timed out'),
}


def stopped_continuation(title, status, error_code, original_request, *, zh):
    reason = FAILURE_REASONS.get(error_code) or TERMINAL_REASONS.get(status)
    reason_text = reason[0 if zh else 1].rstrip('.。') if reason else ''
    if zh:
        message = f'「{title}」上一次没有完成。'
        if reason_text:
            message += reason_text + '。'
        if original_request:
            return message + f'如果要重新尝试，请发「请新开一个任务：{original_request}」'
        return message + '如果要重新尝试，请发一条新消息，写明你希望 Bot 做什么。'
    message = f'The previous attempt at “{title}” ended before it finished. '
    if reason_text:
        message += reason_text + '. '
    if original_request:
        return message + f'To try again, send “Start a new task: {original_request}”'
    return message + 'To try again, send a new message describing what you want the Bot to do.'


def public_content(content,artifacts):
    # Compatibility for the exact platform-generated legacy marker. Identifiers
    # come from verified artifacts, never from a model-supplied pattern or regex.
    markers=['Generated artifact_id='+a['artifact_id']+'. Use an installed capability accepting this artifact ID for further operations.' for a in artifacts]
    def clean(text):
        for marker in markers:text=text.replace(marker,'')
        return text.strip()
    if isinstance(content,str):return clean(content)
    if isinstance(content,list):return [{**part,'text':clean(part['text'])} if isinstance(part,dict) and part.get('type')=='text' and isinstance(part.get('text'),str) else part for part in content]
    return ''


def text_content(content):
    return content if isinstance(content,str) else '\n'.join(p['text'] for p in content if isinstance(p,dict) and p.get('type')=='text' and isinstance(p.get('text'),str))


def result_content(content,*,status,next_label=None,zh=True,error_code=None,step_label=None,completed_calls=None,
                   failure_receipts=(),blocked_tool=None):
    if status!='completed':
        reason = FAILURE_REASONS.get(error_code) or TERMINAL_REASONS.get(status)
        label = (f'「{step_label}」没有完成。' if step_label else '这一步没有完成。') if zh else (
            f'“{step_label}” did not finish. ' if step_label else 'This step did not finish. ')
        progress = ' '.join(receipt['progress'] for receipt in failure_receipts if receipt.get('progress'))
        if completed_calls == 0:
            counts = '这一步没有完成任何工具调用。' if zh else 'No tool calls completed in this step.'
        elif completed_calls:
            counts = f'停止前完成了 {completed_calls} 次工具调用。' if zh else f'Completed tool calls before stopping: {completed_calls}.'
        else:
            counts = ''
        parts = [label.strip()]
        if progress or counts:
            parts.append(('**实际进展** ' if zh else '**Progress** ') + (progress or counts))
        if reason or blocked_tool:
            parts.append(('**卡点** ' if zh else '**Blocked at** ') +
                         (f'`{blocked_tool}` · ' if blocked_tool and reason else f'`{blocked_tool}`' if blocked_tool else '') +
                         (reason[0 if zh else 1].rstrip('.。') + ('。' if zh else '.') if reason else ''))
        else:
            parts.append('**卡点** 执行结束，记录中没有可确认的具体原因。' if zh else
                         '**Blocked at** Execution ended without a confirmed cause in the record.')
        evidence = '\n\n'.join(receipt['evidence'] for receipt in failure_receipts if receipt.get('evidence'))
        if evidence:
            parts.append(('**已有结果（部分）**' if zh else '**Available results (partial)**') + '\n\n' + evidence)
        next_step = NEXT_STEPS.get(error_code) or (
            '可补充目标或来源要求，再单独发起尚未完成的部分。', 'Clarify the target or source requirements and request the unfinished work separately.')
        parts.append(('**下一步** ' if zh else '**Next step** ') + next_step[0 if zh else 1] + ' ' +
                     ('后续步骤不会自动执行。' if zh else 'Follow-up steps will not run automatically.'))
        return '\n\n'.join(parts)
    if not next_label:return content
    text=('这一步已完成，接下来处理「'+next_label+'」。' if zh else 'This step is complete. Next: “'+next_label+'”.')
    # Intermediate deliverables remain canonical artifacts; preserve their typed
    # media blocks while the Bot supplies queue-aware, factual user feedback.
    media=[p for p in content if isinstance(p,dict) and p.get('type')!='text'] if isinstance(content,list) else []
    return [{'type':'text','text':text},*media]
