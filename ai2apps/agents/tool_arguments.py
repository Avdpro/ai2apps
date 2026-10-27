"""Conservative preparation against each Tool's actual registered schema."""
from copy import deepcopy
from jsonschema import Draft202012Validator

def prepare_arguments(schema, arguments):
    values = deepcopy(arguments)
    validator = Draft202012Validator(schema)
    # Use actual validation errors, including resolved references and nested
    # object/array paths. Do not guess between failing oneOf/anyOf branches.
    while True:
        removed = False
        for error in list(validator.iter_errors(values)):
            if (error.validator != 'additionalProperties'
                    or error.validator_value is not False
                    or not isinstance(error.instance, dict)):
                continue
            import re
            declared = error.schema.get('properties', {})
            patterns = error.schema.get('patternProperties', {})
            required = error.schema.get('required', [])
            for key in list(error.instance):
                if (key not in declared and key not in required
                        and not any(re.search(pattern, key) for pattern in patterns)):
                    del error.instance[key]
                    removed = True
        if not removed:
            break
    error = next(validator.iter_errors(values), None)
    if error is None:
        return values, None
    # Do not echo possibly sensitive argument values into the recovery prompt.
    path = '.'.join(str(x) for x in error.absolute_path)[:200] or '<root>'
    fields = ', '.join(str(k) for k in schema.get('properties', {}))[:1200]
    required = ', '.join(str(k) for k in schema.get('required', []))[:400]
    return values, (f'Tool arguments failed {error.validator} validation at {path}. '
                    f'Allowed root fields: {fields}. Required root fields: {required}. '
                    'Correct the call using the supplied Tool schema. The Tool has not executed; '
                    'do not invent IDs or silently change requested model, size or other user constraints.')
