"""Shared primitive bounds for owner-declared browser preparation/read steps."""

def allowed_primitives(step):
    args=step.get('arguments') or {}
    if args.get('custom_search'):
        return ('inspect','scroll','hover','click','page_access','input')
    if args.get('read_only'):
        return ('inspect','extract_list','scroll','open','hover','click','page_access','input')
    if args.get('preparation_only'):
        return ('inspect','input','hover','click','scroll')
    return ('open','page_access','inspect','extract_list','click','input','hover','scroll')
