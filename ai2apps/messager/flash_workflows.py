"""Trusted fixed workflows. Configuration and user input never contain code."""
import ast
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from types import MappingProxyType


def calculate(text):
    if not isinstance(text,str) or not text.strip() or len(text)>512:
        raise ValueError('请输入不超过 512 字符的数学表达式 / Enter a mathematical expression (max 512 characters)')
    text=text.strip()
    try:tree=ast.parse(text,mode='eval')
    except (SyntaxError,ValueError,RecursionError):raise ValueError('表达式格式不正确 / Invalid expression') from None
    if sum(1 for _ in ast.walk(tree))>128:raise ValueError('表达式过于复杂 / Expression is too complex')
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            raw=ast.get_source_segment(text,node)
            if len(raw)>64:raise ValueError('数值过大 / Number is too large')
            value=Decimal(raw.replace('_',''))
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand)
            if isinstance(node.op,ast.USub):value=-value
        elif isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,ast.Mod,ast.Pow)):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):value=a+b
            elif isinstance(node.op,ast.Sub):value=a-b
            elif isinstance(node.op,ast.Mult):value=a*b
            elif isinstance(node.op,ast.Div):value=a/b
            elif isinstance(node.op,ast.FloorDiv):value=(a/b).to_integral_value(rounding='ROUND_FLOOR')
            elif isinstance(node.op,ast.Mod):value=a-(a/b).to_integral_value(rounding='ROUND_FLOOR')*b
            else:
                if b!=b.to_integral_value() or abs(b)>100:raise ValueError('指数须为 -100 至 100 的整数 / Exponent must be an integer between -100 and 100')
                value=a**int(b)
        else:raise ValueError('仅支持数字、括号和 + - * / // % **；不接受文字、函数或代码 / Only numbers, parentheses and arithmetic operators are accepted')
        if not value.is_finite() or (value and abs(value.adjusted())>100):raise ValueError('数值超出允许范围 / Number is out of range')
        return value
    try:
        with localcontext() as ctx:
            ctx.prec=28;ctx.Emax=100;ctx.Emin=-100
            value=visit(tree.body)
            return format(value.normalize(),'f') if value else '0'
    except (DecimalException,ValueError,OverflowError,RecursionError) as exc:
        if isinstance(exc,ValueError):raise
        raise ValueError('无法计算：除数不能为零，数值必须在允许范围内 / Invalid arithmetic or number out of range') from None


@dataclass(frozen=True)
class Workflow:
    id:str
    version:str
    name:str
    name_en:str
    description:str
    validate:object
    execute:object


class WorkflowRegistry:
    def __init__(self,workflows):
        values={}
        for workflow in workflows:
            if not callable(workflow.validate) or not callable(workflow.execute):raise ValueError('Trusted workflow callbacks required')
            key=(workflow.id,workflow.version)
            if key in values:raise ValueError('Duplicate workflow version')
            values[key]=workflow
        self.workflows=MappingProxyType(values)

    def get(self,config):
        workflow=self.workflows.get((config['workflow_id'],config['workflow_version']))
        if not workflow:raise ValueError('工作流版本不可用 / Workflow version unavailable')
        return workflow

    def catalog(self):
        return [{'id':w.id,'version':w.version,'name':w.name,'name_en':w.name_en,'description':w.description,
                 'input':{'kind':'text','max_length':512},'requires_model':False,'requires_apps':[]}
                for w in self.workflows.values()]


def validate_calculator(text,attachments):
    if attachments:raise ValueError('计算器只接受数学表达式，不接受附件 / Calculator accepts expressions, not attachments')
    calculate(text)
    return {'expression':text.strip()}


REGISTRY=WorkflowRegistry((Workflow('calculator','1','数学表达式计算','Calculator',
    '输入数学表达式；28 位十进制精度，不调用 AI 模型。',validate_calculator,
    lambda value:{'content':value['expression']+' = '+calculate(value['expression']),'model_calls':0}),))
