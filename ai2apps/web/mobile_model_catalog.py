"""Public display projection of the desktop model catalog; never export settings."""
FIELDS = ('id', 'model_type', 'capabilities', 'source_type', 'is_hidden',
          'is_favorite', 'load_failed', 'checkpoint_ready', 'owned_by')


def merge_catalog(public, managed):
    aliases = {}
    by_id = {}
    for row in managed:
        alias = (row.get('settings') or {}).get('model_alias') or row.get('model_alias')
        if alias:
            aliases[alias] = row['id']
        by_id[row['id']] = row
    rows = list(public)
    ids = {aliases.get(row['id'], row['id']) for row in rows}
    rows += [row for row in managed if row.get('source_type') in ('cloud', 'fusion') and row['id'] not in ids]
    result = {}
    for row in rows:
        key = aliases.get(row['id'], row['id'])
        admin = by_id.get(key, {})
        combined = {**row, **admin}
        item = {field: combined[field] for field in FIELDS if field in combined}
        item['id'] = key
        item['display_name'] = ((admin.get('identity') or {}).get('displayName') or admin.get('display_name')
            or (row.get('identity') or {}).get('displayName') or row.get('display_name') or row.get('name') or row['id'])
        result[key] = item
    return list(result.values())


async def desktop_catalog_projection(public):
    # Server-side read only. The management route is never exposed or proxied;
    # only explicitly allowlisted display fields leave this function.
    from omlx.admin.routes import list_models
    from fastapi import HTTPException
    try:
        managed = await list_models(request=None, is_admin=True)
    except HTTPException as error:
        if error.status_code != 503:
            raise
        return merge_catalog(public, [])
    return merge_catalog(public, managed.get('models', []))
