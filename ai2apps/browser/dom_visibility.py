"""One shared page visibility policy, evaluated inside native BiDi scripts."""
from pathlib import Path

DOM_VISIBILITY_SOURCE = (Path(__file__).resolve().parents[1] / 'web/static/js/browser_dom_visibility.js').read_text()


def page_function(source, serialized_args):
    # Function-local binding: no page globals, browser endpoint or credentials.
    return (f'async function(){{const ai2appsDOMVisible=({DOM_VISIBILITY_SOURCE});'
            f'const fn=({source});return JSON.stringify(await fn(...{serialized_args}));}}')
