"""Declaration validation only; no credential, execution or routing authority."""
def validate_owner_service(value, manifest_id, placements):
    if value != {'schema':'ai2apps.mini-app-owner-service/v1','host':manifest_id} or not any(
        p.get('studio')==manifest_id for p in placements
    ):
        raise ValueError('Owner service must belong to its declaring host App')
