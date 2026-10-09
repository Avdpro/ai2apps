import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def test_committed_recipe_retains_review_approval():
    tree = ast.parse((Path(__file__).parents[1] / 'api/agent_platform.py').read_text())
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_recipe_review')
    compiled = SimpleNamespace(valid=True, source_digest='digest', ir={'steps':[]}, report={})
    namespace = {'Any':Any, 'compile_source':lambda _:compiled}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'review', 'exec'), namespace)
    for status, expected in [('draft','awaiting_review'),('tested','approved'),('committed','approved')]:
        recipe = SimpleNamespace(id='recipe',revision=3,status=status,source={})
        result = namespace['_recipe_review'](recipe)
        assert result['status'] == expected
        assert result['recipe_status'] == status
