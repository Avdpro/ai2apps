"""Dependency graph and checker mutation tests; no application import or models."""
import json
from pathlib import Path
import pytest
from architecture.aaat_guard import Unit,check,source_units

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((Path(__file__).parent/'architecture/aaat_policy.json').read_text())


def test_shared_as_dependency_graph_respects_owner_boundaries():
    failures=check(source_units(ROOT),POLICY)
    assert not failures,'\n'.join(failures)


def policy():
    return {'agent_exclusions':{},'compatibility_shims':{},'service_roots':[],
            'shared_namespaces':{'ai2apps.agents':'Generic test infrastructure'},
            'shared_modules':{'ai2apps':'Version facade','ai2apps.core.helper':'Generic helper'}}


@pytest.mark.parametrize('source',[
    'from ai2apps.research import citations as hidden',
    'def later():\n from ..research.citations import bind_final',
    'import importlib as loader\nloader.import_module("ai2apps.research.citations")',
    'from importlib import import_module as load\nprefix="ai2apps."\nload(prefix+"research.citations")',
    'loader=__import__\nloader("ai2apps.research.citations")',
    '__import__("research.citations",level=2)',
    'import importlib\ngetattr(importlib,"import_module")("ai2apps.research.citations")',
])
def test_checker_rejects_aliased_local_and_dynamic_owner_dependencies(source):
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general',source),
           'ai2apps.research.citations':Unit('ai2apps.research.citations','')}
    assert any('crosses shared AS boundary' in error for error in check(units,policy()))


def test_checker_follows_shared_helper_and_fails_closed_for_unclassified_helper():
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general','from ai2apps.core.helper import f'),
           'ai2apps.core.helper':Unit('ai2apps.core.helper','from ai2apps.new_business import f')}
    failures=check(units,policy())
    assert any('ai2apps.agents.general -> ai2apps.core.helper -> ai2apps.new_business' in error for error in failures)


@pytest.mark.parametrize('source',['__import__(input())','exec(input())',
                                   'from importlib import import_module as load\nload(input())'])
def test_checker_rejects_uninspectable_dynamic_code_in_shared_closure(source):
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general','from ai2apps.core.helper import f'),
           'ai2apps.core.helper':Unit('ai2apps.core.helper',source)}
    assert any('dynamic' in error for error in check(units,policy()))


def test_business_words_in_data_do_not_trigger_dependency_violation():
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general','sample="Todo Search All Video Studio https://weibo.com"')}
    assert check(units,policy())==[]


def test_compatibility_reexport_cannot_hide_dispatch_or_be_used_by_core():
    rules=policy();rules['compatibility_shims']={'ai2apps.agents.old':'ai2apps.owner.adapter'}
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general',''),
           'ai2apps.agents.old':Unit('ai2apps.agents.old','from ai2apps.owner.adapter import *')}
    assert check(units,rules)==[]
    units['ai2apps.agents.old']=Unit('ai2apps.agents.old','from ai2apps.owner.adapter import *\ndef business_dispatch(): pass')
    assert any('inert re-export' in error for error in check(units,rules))
    units['ai2apps.agents.general']=Unit('ai2apps.agents.general','from .old import handler')
    assert any('crosses shared AS boundary' in error for error in check(units,rules))


@pytest.mark.parametrize('branch',[
    'if tool.app_id == "brand.never_seen_before": pass',
    'TARGET="brand."+"new"\nif tool.app_id == TARGET: pass',
    'if str(tool.app_id).casefold() == "brand.new": pass',
    'routes={"brand.new": handler}\nroutes[tool.app_id]()',
    'routes={"brand.new": handler}\nroutes.get(tool.app_id)()',
    'owner=tool.app_id\nif owner == "brand.never_seen_before": pass',
    'if step.tool_name.startswith("brand."): pass',
    'if "brand" in provider.app_id: pass',
    'if arguments.get("capability") in {"brand.one", "brand.two"}: pass',
    'match tool.mini_app_id:\n case "brand.entry": pass',
])
def test_inline_identity_special_cases_are_structural_violations(branch):
    from architecture.aaat_guard import identity_dispatch
    assert identity_dispatch(Unit('ai2apps.agents.general',branch),{'app.interact'})


def test_identity_checks_allow_protocol_controls_dynamic_comparisons_and_business_data():
    from architecture.aaat_guard import identity_dispatch
    unit=Unit('ai2apps.agents.general',
        'text="Search All Todo brand.entry"\n'
        'if tool.app_id == expected.app_id: pass\n'
        'if step.tool_name == "app.interact": pass\n'
        'if result["status"] == "partial": pass\n'
        'if "/" in descriptor.app_id: raise ValueError()')
    assert identity_dispatch(unit,{'app.interact'})==[]


def test_canonical_gate_is_wired_into_ci_and_selects_existing_contract_tests():
    import ast
    import shlex
    import yaml
    tree=ast.parse((Path(__file__).parent/'run_aaat_boundaries.py').read_text())
    tests=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
               and any(isinstance(target,ast.Name) and target.id=='TESTS' for target in node.targets))
    assert all((ROOT.parent/path).is_file() for path in tests)
    assert {'ai2apps/tests/test_aaat_architecture.py','ai2apps/tests/test_aaat_boundary_behavior.py',
            'ai2apps/tests/test_aaat_execution_flow.py'} <= set(tests)
    workflow=yaml.safe_load((ROOT.parent/'.github/workflows/ci.yml').read_text())
    commands=[step.get('run','') for job in workflow['jobs'].values() for step in job['steps']]
    assert any(shlex.split(command)==['python','ai2apps/tests/run_aaat_boundaries.py'] for command in commands)


def test_new_agent_module_is_protected_without_adding_it_to_an_allowlist():
    units={'ai2apps.agents.general':Unit('ai2apps.agents.general',''),
           'ai2apps.agents.new_helper':Unit('ai2apps.agents.new_helper','from ai2apps.new_owner import handler')}
    assert any('ai2apps.agents.new_helper' in error for error in check(units,policy()))
