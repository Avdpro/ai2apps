"""Source-only dependency architecture gate; never imports application modules.

Policy is a positive layer classification, not a list of business keywords.
Function-local, relative, aliased and literal dynamic imports form the same graph.
Unknown dependencies fail closed, including a business helper moved out of agents/.
"""
from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from importlib.util import resolve_name
import os
from pathlib import Path


@dataclass(frozen=True)
class Unit:
    name: str
    source: str
    package: bool = False


@dataclass(frozen=True)
class Edge:
    target: str
    line: int


def source_units(root: Path) -> dict[str, Unit]:
    units = {}
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in
                         {'tests', 'docs', 'node_modules', '__pycache__', 'venv', 'artifacts'})
        for filename in sorted(files):
            if not filename.endswith('.py'):
                continue
            path = Path(directory) / filename
            parts = path.relative_to(root).with_suffix('').parts
            package = filename == '__init__.py'
            if package:
                parts = parts[:-1]
            name = '.'.join(('ai2apps', *parts))
            units[name] = Unit(name, path.read_text(), package)
    return units


def imports(unit: Unit, known: set[str]) -> tuple[list[Edge], list[str]]:
    tree = ast.parse(unit.source, filename=unit.name)
    package = unit.name if unit.package else unit.name.rsplit('.', 1)[0]
    aliases = {}
    constants = {}
    edges = []
    violations = []

    def literal(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literal(node.left), literal(node.right)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        return None

    def dotted(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return dotted(node.value) + '.' + node.attr
        if (isinstance(node, ast.Call) and dotted(node.func) == 'getattr'
                and len(node.args) == 2 and isinstance(literal(node.args[1]), str)):
            return dotted(node.args[0]) + '.' + literal(node.args[1])
        return ''

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
                edges.append(Edge(item.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                base = resolve_name('.' * node.level + base, package)
            edges.append(Edge(base, node.lineno))
            for item in node.names:
                target = base + '.' + item.name
                aliases[item.asname or item.name] = target
                if target in known:
                    edges.append(Edge(target, node.lineno))
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            constants[node.targets[0].id] = literal(node.value)
            name = dotted(node.value)
            if name:
                aliases[node.targets[0].id] = name

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = dotted(node.func)
        if function in {'eval', 'exec', 'builtins.eval', 'builtins.exec'}:
            violations.append(f'{unit.name}:{node.lineno}: dynamic code execution cannot be dependency-audited')
        if function not in {'importlib.import_module', '__import__', 'builtins.__import__'}:
            continue
        target = literal(node.args[0]) if node.args else None
        if not isinstance(target, str):
            violations.append(f'{unit.name}:{node.lineno}: unresolved dynamic import requires a reviewed platform interface')
            continue
        level=next((literal(k.value) for k in node.keywords if k.arg=='level'),0)
        if function != 'importlib.import_module' and len(node.args)>4:
            level=literal(node.args[4])
        if function != 'importlib.import_module' and level:
            if not isinstance(level,int):
                violations.append(f'{unit.name}:{node.lineno}: unresolved dynamic import level')
                continue
            target=resolve_name('.'*level+target,package)
        if target.startswith('.'):
            pkg = next((literal(k.value) for k in node.keywords if k.arg == 'package'), None)
            if pkg is None and len(node.args) > 1:
                pkg = literal(node.args[1])
            if not isinstance(pkg, str):
                violations.append(f'{unit.name}:{node.lineno}: unresolved relative dynamic import')
                continue
            target = resolve_name(target, pkg)
        edges.append(Edge(target, node.lineno))
        for keyword in node.keywords:
            if keyword.arg == 'fromlist' and isinstance(keyword.value, (ast.List, ast.Tuple)):
                for item in keyword.value.elts:
                    child = literal(item)
                    if not isinstance(child,str):
                        violations.append(f'{unit.name}:{node.lineno}: unresolved dynamic import fromlist')
                    if isinstance(child, str) and target + '.' + child in known:
                        edges.append(Edge(target + '.' + child, node.lineno))
    return [edge for edge in edges if edge.target == 'ai2apps' or edge.target.startswith('ai2apps.')], violations


def check(units: dict[str, Unit], policy: dict) -> list[str]:
    excluded = set(policy['agent_exclusions']) | set(policy['compatibility_shims'])

    def shared(name):
        if name in excluded:
            return False
        return name in policy['shared_modules'] or any(
            name == prefix or name.startswith(prefix + '.') for prefix in policy['shared_namespaces'])

    roots = sorted({n for n in units if n.startswith('ai2apps.agents.') and n not in excluded}
                   | set(policy['service_roots']))
    failures = []
    graph = {name: imports(unit, set(units)) for name, unit in units.items()}
    visited = set()
    pending = deque((root, (root,)) for root in roots)
    while pending:
        name, route = pending.popleft()
        if name in visited:
            continue
        visited.add(name)
        if name not in units:
            failures.append('Missing protected module: ' + name)
            continue
        edges, dynamic = graph[name]
        failures.extend(dynamic)
        if name.startswith(('ai2apps.agents.', 'ai2apps.services.')):
            failures.extend(identity_dispatch(units[name], set(policy.get('platform_control_ids', {}))))
        for edge in edges:
            chain = ' -> '.join((*route, edge.target))
            if not shared(edge.target):
                failures.append(f'{name}:{edge.line}: dependency crosses shared AS boundary: {chain}')
            elif edge.target not in units:
                failures.append(f'{name}:{edge.line}: unresolved local dependency: {chain}')
            else:
                pending.append((edge.target, (*route, edge.target)))

    # Existing compatibility exports are allowed only as inert re-exports. They
    # may not become a hiding place for business dispatch and are never AS deps.
    for name, target in policy['compatibility_shims'].items():
        if name not in units:
            continue  # removing a compatibility shim is allowed
        body = ast.parse(units[name].source).body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        if not (len(body) == 1 and isinstance(body[0], ast.ImportFrom)
                and body[0].level == 0 and body[0].module == target
                and [alias.name for alias in body[0].names] == ['*']):
            failures.append(f'{name}: compatibility shim must remain an inert re-export of {target}')
    return failures


def identity_dispatch(unit: Unit, control_ids: set[str]) -> list[str]:
    """Find identity-driven literal branching, rather than matching business words.

    Simple assignment aliases are followed. Platform control operations are an
    explicit protocol exception; dynamic provider-to-provider comparisons are OK.
    This is deliberately not a general Python taint proof.
    """
    tree = ast.parse(unit.source, filename=unit.name)
    fields = {'qualified_name', 'tool_name', 'app_id', 'mini_app_id', 'capability',
              'provider', 'provider_id'}
    tainted = set(fields)

    def identity(node):
        if isinstance(node, ast.Name):
            return node.id in tainted
        if isinstance(node, ast.Attribute):
            return node.attr in fields
        if isinstance(node, ast.Subscript):
            return isinstance(node.slice, ast.Constant) and node.slice.value in fields
        if isinstance(node, ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='str' and node.args:
            return identity(node.args[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {'lower','upper','casefold','strip'}:return identity(node.func.value)
            return (node.func.attr == 'get' and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in fields)
        if isinstance(node, (ast.Tuple, ast.List)):
            return any(identity(element) for element in node.elts)
        return False

    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)]
    for _ in range(len(assignments)+1):
        previous=set(tainted)
        for node in assignments:
            if identity(node.value):
                tainted.update(target.id for target in node.targets if isinstance(target,ast.Name))
        if previous==tainted:break

    constant_values={}
    def literals(node):
        if isinstance(node,ast.Name):return constant_values.get(node.id,set())
        if isinstance(node,ast.Dict):return set().union(*(literals(item) for item in node.keys if item is not None))
        if isinstance(node,ast.Constant) and isinstance(node.value,str):return {node.value}
        if isinstance(node,(ast.Set,ast.Tuple,ast.List)):
            return set().union(*(literals(item) for item in node.elts))
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
            left,right=literals(node.left),literals(node.right)
            return {a+b for a in left for b in right}
        return set()

    for _ in range(len(assignments)+1):
        previous=dict(constant_values)
        for node in assignments:
            values=literals(node.value)
            if values:
                for target in node.targets:
                    if isinstance(target,ast.Name):constant_values[target.id]=values
        if constant_values==previous:break
    tables={target.id:literals(node.value) for node in assignments if isinstance(node.value,ast.Dict)
            for target in node.targets if isinstance(target,ast.Name)}
    failures=[]
    def reject(node,values):
        unexpected=values-control_ids-{''}
        if unexpected:
            failures.append(f'{unit.name}:{node.lineno}: literal identity dispatch bypasses owner declarations: {sorted(unexpected)!r}')
    for node in ast.walk(tree):
        if isinstance(node,ast.Compare):
            values=[node.left,*node.comparators]
            for left,operator,right in zip(values,node.ops,values[1:]):
                if identity(left):reject(node,literals(right))
                if identity(right):
                    # Rejecting invalid identifier delimiters is generic syntax
                    # validation, not selecting an owner by its business identity.
                    syntax_check=(isinstance(operator,(ast.In,ast.NotIn))
                                  and literals(left) <= {'/', '\\', '\0'})
                    if not syntax_check:reject(node,literals(left))
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
              and node.func.attr in {'startswith','endswith'} and identity(node.func.value)):
            for argument in node.args:reject(node,literals(argument))
        elif isinstance(node,ast.Subscript) and identity(node.slice):
            values=(tables.get(node.value.id,set()) if isinstance(node.value,ast.Name) else literals(node.value) if isinstance(node.value,ast.Dict) else set())
            reject(node,values)
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
              and node.func.attr in {'get','pop'} and node.args and identity(node.args[0])):
            table=node.func.value
            reject(node,tables.get(table.id,set()) if isinstance(table,ast.Name) else literals(table) if isinstance(table,ast.Dict) else set())
        elif isinstance(node,ast.Match) and identity(node.subject):
            for case in node.cases:
                for pattern in ast.walk(case.pattern):
                    if isinstance(pattern,ast.MatchValue):reject(pattern,literals(pattern.value))
    return failures
