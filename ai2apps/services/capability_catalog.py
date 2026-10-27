"""Read-only system inventory. Registration is not an execution permission grant."""
def capability_catalog(runtime, principal):
    router = getattr(runtime, 'app_capability_router', None)
    providers = router.inspect(principal.actor_user_id, principal.installation_id) if router else []
    tools = []
    for tool in runtime.services.list_tools(include_disabled=True):
        service = runtime.services.get_service(tool.service_id)
        tools.append(dict(name=tool.qualified_name, description=tool.description,
                          capabilities=list(tool.required_capabilities),
                          input_schema=tool.input_schema, output_schema=tool.output_schema,
                          effects=list(tool.effects), enabled=tool.enabled,
                          service=service.service_key, service_status=str(service.status)))
    return dict(tools=tools, providers=providers)
