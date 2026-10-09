"""Bounded JSON expressions and run-local state. No eval, code or browser access."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import math
import operator
import re
from typing import Any

from jsonschema import Draft202012Validator, ValidationError, SchemaError

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MAX_BYTES = 262144
MAX_ITEMS = 10000
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
           ast.In: lambda a,b:a in b, ast.NotIn:lambda a,b:a not in b}


def bounded(value):
    try:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Expression must produce finite JSON data") from error
    if len(payload.encode()) > MAX_BYTES:
        raise ValueError("Variable value exceeds size limit")
    if isinstance(value, int) and value.bit_length() > 256:
        raise ValueError("Integer exceeds size limit")
    return value


def parse_expression(expression: str):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 4000:
        raise ValueError("Expression must be nonempty text of at most 4000 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as error:
        raise ValueError("Invalid expression syntax") from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 128:
        raise ValueError("Expression is too complex")
    allowed = (ast.Expression, ast.Constant, ast.Name, ast.Attribute, ast.Load, ast.Subscript,
               ast.List, ast.Dict, ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Call,
               ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, *BINARY, *COMPARE)
    for node in nodes:
        if not isinstance(node, allowed):
            raise ValueError(f"Unsupported expression construct: {type(node).__name__}")
        if isinstance(node, ast.Constant) and (not isinstance(node.value, (str, bool, int, float, type(None)))
                                                or isinstance(node.value, float) and not math.isfinite(node.value)):
            raise ValueError("Unsupported literal")
        if isinstance(node, ast.Name) and node.id not in {"input", "vars", "steps", "true", "false", "null", "len", "length", "min", "max", "abs"}:
            raise ValueError(f"Unknown expression name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Private attributes are not expressions")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or
                node.func.id not in {"len", "length", "min", "max", "abs"} or node.keywords):
            raise ValueError("Only len/length/min/max/abs calls are allowed")
    return tree.body


def validate_expression(expression, variables=None):
    tree = parse_expression(expression)
    if variables is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "vars" and node.attr not in variables:
                raise ValueError(f"Undeclared variable: {node.attr}")
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "vars" and isinstance(node.slice, ast.Constant) and node.slice.value not in variables:
                raise ValueError(f"Undeclared variable: {node.slice.value}")
    return tree


def evaluate(expression: str, inputs: dict, variables: dict, outputs: dict):
    tree = parse_expression(expression)
    env = {"input": inputs, "vars": variables, "steps": outputs,
           "true": True, "false": False, "null": None}
    def read(node, depth=0):
        if depth > 24:
            raise ValueError("Expression nesting exceeds limit")
        child = lambda n: read(n, depth+1)
        if isinstance(node, ast.Constant): return bounded(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env: raise ValueError("Function name must be called")
            return env[node.id]
        if isinstance(node, ast.Attribute):
            value = child(node.value)
            if not isinstance(value, dict) or node.attr not in value: raise ValueError(f"Missing field: {node.attr}")
            return value[node.attr]
        if isinstance(node, ast.Subscript):
            value, index = child(node.value), child(node.slice)
            if isinstance(value, (list, str)):
                if type(index) is not int or index < 0 or index >= len(value): raise ValueError("Array index out of range")
            elif not isinstance(value, dict) or not isinstance(index, str) or index not in value:
                raise ValueError("Invalid object key")
            return value[index]
        if isinstance(node, ast.List): return [child(n) for n in node.elts]
        if isinstance(node, ast.Dict):
            keys = [child(n) for n in node.keys]
            if any(not isinstance(key, str) for key in keys): raise ValueError("Object keys must be strings")
            return dict(zip(keys, [child(n) for n in node.values]))
        if isinstance(node, ast.BoolOp):
            values = []
            for n in node.values:
                value = child(n)
                if type(value) is not bool: raise ValueError("Boolean operators require booleans")
                values.append(value)
                if isinstance(node.op, ast.And) and not value: return False
                if isinstance(node.op, ast.Or) and value: return True
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp):
            value = child(node.operand)
            if isinstance(node.op, ast.Not):
                if type(value) is not bool: raise ValueError("not requires a boolean")
                return not value
            if type(value) not in (int,float): raise ValueError("Unary arithmetic requires a number")
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = child(node.left), child(node.right)
            if isinstance(node.op, ast.Add) and type(left) is type(right) and isinstance(left, (str,list)):
                if len(left)+len(right)>MAX_ITEMS: raise ValueError("Concatenation exceeds limit")
            elif type(left) not in (int,float) or type(right) not in (int,float):
                raise ValueError("Arithmetic requires numbers (or same-type concatenation)")
            return bounded(BINARY[type(node.op)](left,right))
        if isinstance(node, ast.Compare):
            left = child(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = child(right_node)
                if not COMPARE[type(op)](left,right): return False
                left = right
            return True
        if isinstance(node, ast.Call):
            args = [child(n) for n in node.args]
            if node.func.id in {"len", "length"}:
                if len(args)!=1 or not isinstance(args[0], (str,list,dict)): raise ValueError("len expects an array, string or object")
                return len(args[0])
            if not args or any(type(v) not in (int,float) for v in args): raise ValueError("Numeric function expects numbers")
            if node.func.id == "abs":
                if len(args)!=1: raise ValueError("abs expects one number")
                return abs(args[0])
            return min(args) if node.func.id == "min" else max(args)
        raise ValueError("Unsupported expression")
    try:
        return deepcopy(bounded(read(tree)))
    except (TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RecursionError) as error:
        raise ValueError(f"Expression failed: {type(error).__name__}") from error


def validate_variables(schema):
    if not isinstance(schema, dict) or schema.get("type") != "object" or not isinstance(schema.get("properties", {}), dict):
        raise ValueError("Variables must be an object schema")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ValueError("Invalid variable schema") from error
    properties = schema.get("properties", {})
    if len(properties)>64: raise ValueError("At most 64 variables are allowed")
    for name, prop in properties.items():
        if not NAME.fullmatch(name) or name.startswith("__"): raise ValueError("Invalid variable name")
        if not isinstance(prop, dict) or prop.get("type") not in {"string","number","integer","boolean","array","object","null"}:
            raise ValueError("Variable needs a JSON type")
        if "initial" in prop: validate_expression(prop["initial"], {})
        if "default" in prop: Draft202012Validator(prop).validate(bounded(prop["default"]))


def initialize_variables(schema, inputs):
    validate_variables(schema)
    defaults = {"string":"", "number":0, "integer":0, "boolean":False, "array":[], "object":{}, "null":None}
    result = {}
    for name, prop in schema.get("properties", {}).items():
        value = evaluate(prop["initial"], inputs, {}, {}) if "initial" in prop else deepcopy(prop.get("default", defaults[prop["type"]]))
        try: Draft202012Validator(prop).validate(value)
        except ValidationError as error: raise ValueError(f"Initial value of {name} does not match its type") from error
        result[name] = value
    return bounded(result)


def execute_local_step(step, inputs, variables, outputs, schema):
    """Assignments commit atomically; a false condition is distinct from failure."""
    current = deepcopy(variables)
    try:
        args = step.get("arguments", {})
        if step["operation"] == "condition":
            value = evaluate(args["expression"], inputs, current, outputs)
            if type(value) is not bool: raise ValueError("Condition must produce a boolean")
            return {"outcome":"true" if value else "false", "evidence":{"operation":"condition","result":{"value":value}}}, current
        if step["operation"] != "assign": raise ValueError("Not a local data step")
        changes = {}
        assignments = args.get("assignments", [])
        if not assignments or len(assignments)>32: raise ValueError("Assignment step needs 1–32 assignments")
        for assignment in assignments:
            name = assignment["variable"]
            prop = schema.get("properties", {}).get(name)
            if prop is None: raise ValueError(f"Undeclared variable: {name}")
            value = evaluate(assignment["expression"], inputs, current, outputs)
            try: Draft202012Validator(prop).validate(value)
            except ValidationError as error: raise ValueError(f"Assignment type mismatch: {name}") from error
            current[name] = value; changes[name] = value
        bounded(current)
        return {"outcome":"success", "evidence":{"operation":"assign", "result":{"assigned":changes}}}, current
    except (ValueError, KeyError, TypeError) as error:
        return {"outcome":"failed", "evidence":{"operation":step.get("operation"),"reason":"local_expression_failed", "detail":str(error)[:500]}}, deepcopy(variables)
