"""Model-facing questions and Run-owned plans using existing durable state."""

from jsonschema import Draft202012Validator

from ai2apps.core import ResourceConflictError
from ai2apps.services import ToolProviderError

from .models import InteractionAction, InteractionKind, InteractionStatus

ASK_USER = "agent.ask_user"
PLAN_READ = "agent.read_plan"
PLAN_UPDATE = "agent.update_plan"

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "question": {"type": "string", "minLength": 1, "maxLength": 2000},
        "options": {
            "type": "array",
            "minItems": 2,
            "maxItems": 8,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 200},
        },
    },
    "required": ["question_id", "question"],
    "additionalProperties": False,
}
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "expected_revision": {"type": "integer", "minimum": 0},
        "items": {
            "type": "array",
            "maxItems": 50,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1, "maxLength": 64},
                    "title": {"type": "string", "minLength": 1, "maxLength": 300},
                    "status": {"enum": ["pending", "in_progress", "completed"]},
                },
                "required": ["id", "title", "status"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["expected_revision", "items"],
    "additionalProperties": False,
}


def question_action(context, arguments):
    Draft202012Validator(QUESTION_SCHEMA).validate(arguments)
    key = "question:" + arguments["question_id"]
    interaction = context.interaction(key)
    if interaction is not None:
        if interaction.request != arguments:
            raise ValueError("question_id was already used for a different question")
        if interaction.status is InteractionStatus.SUBMITTED:
            return None
        if interaction.status is not InteractionStatus.PENDING:
            raise ValueError("Question is no longer open")
    options = arguments.get("options")
    return InteractionAction(
        request_key=key,
        kind=InteractionKind.MENU if options else InteractionKind.TEXT,
        prompt=arguments["question"],
        response_schema={
            "type": "object",
            "properties": {
                "answer": {"type": "string", "minLength": 1, "maxLength": 8000}
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
        ui_hints={
            "control": "menu" if options else "text",
            "options": options or [],
            "allow_other": bool(options),
        },
        request=arguments,
    )


def install_control_tools(agents, services, registry, *, service_id, provider_key):
    def run_for(context):
        if not context.trace_id or not context.session_id:
            raise ToolProviderError("This Tool requires an Agent Run")
        run = agents.get_run(context.trace_id)
        if run.session_id != context.session_id:
            raise ToolProviderError("Run is not available in this Session")
        return run

    def answer(arguments, context):
        run = run_for(context)
        interaction = next(
            (
                item
                for item in agents.list_interactions(run.id)
                if item.request_key == "question:" + arguments["question_id"]
            ),
            None,
        )
        if (
            interaction is None
            or interaction.status is not InteractionStatus.SUBMITTED
            or interaction.request != arguments
        ):
            raise ToolProviderError(
                "Question must be answered through its user interaction"
            )
        return {
            "question_id": arguments["question_id"],
            "answer": interaction.response["answer"],
        }

    def read_plan(arguments, context):
        return agents.get_plan(run_for(context).id)

    def update_plan(arguments, context):
        try:
            return agents.update_plan(run_for(context).id, **arguments)
        except (ValueError, ResourceConflictError) as error:
            raise ToolProviderError(str(error)) from error

    for name, description, schema, handler in (
        (
            ASK_USER,
            "Ask the user for missing information or a choice, then wait durably. Use a unique question_id. Options are suggestions; free text is allowed. Answers never grant Tool permissions.",
            QUESTION_SCHEMA,
            answer,
        ),
        (
            PLAN_READ,
            "Read this Run's current plan and revision. Separate from the user's Todo projects.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            read_plan,
        ),
        (
            PLAN_UPDATE,
            "Replace this Run's plan with the complete list and expected revision (initially 0). Keep stable item IDs and at most one in_progress item. Update as work progresses; plan completion does not complete the Run or user Todo.",
            PLAN_SCHEMA,
            update_plan,
        ),
    ):
        services.ensure_tool(
            service_id=service_id,
            qualified_name=name,
            display_name=name,
            description=description,
            input_schema=schema,
            output_schema={"type": "object"},
            effects=(),
            timeout_ms=10_000,
        )
        registry.bind_tool(name, provider_key=provider_key, handler=handler)
