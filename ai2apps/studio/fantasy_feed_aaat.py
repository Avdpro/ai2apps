"""Imagine owner for profile resolution and scripted conversation exports."""

import asyncio
import hashlib
import json
import logging
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for

from .package_generation_aaat import owner, receipt, reserve
from .repository import StudioRepository
from .visual_sequence import CAPABILITY, MAX_BYTES, render_visual_sequence

STUDIO = "ai2apps.imagine-studio"
MINI = "ai2apps.imagine.fantasy-feed"
PACKAGE = "ai2apps.fantasy-feed"
# Executing the Package renderer via the native browser is allowed only for the
# owner-reviewed bytes. UI and Agent generation use that same renderer file.
RENDERER_SHA256 = "995204e11af853ac26f98acfb2b73531bdfa0149e6ce66c9db790121e43f496d"
SIZES = {"9:16": [720, 1280], "3:4": [720, 960], "16:9": [1280, 720]}
log = logging.getLogger(__name__)


def normalized(value):
    return unicodedata.normalize("NFKC", value).strip().casefold()


def match_profile(query, profiles):
    key = normalized(query)
    is_self = key in {"我", "自己", "me", "myself", "self"}
    matches = [row for row in profiles if row.get("isSelf") is True] if is_self else []
    if not matches:
        matches = [row for row in profiles if normalized(row["name"]) == key]
    if not matches:
        matches = [row for row in profiles if key in {normalized(alias) for alias in row["aliases"]}]
    if len(matches) != 1:
        reason = "ambiguous" if matches else "not found"
        raise ToolProviderError(f"Participant profile {query!r} is {reason}. Ask the user to clarify or save the profile.")
    return matches[0]


def profile_rows(draft):
    raw = (draft or {}).get("draft", {}).get("participantProfiles", [])
    if not isinstance(raw, list) or len(raw) > 20:
        raise ToolProviderError("Participant profile library is invalid")
    result = []
    for row in raw:
        if not isinstance(row, dict):
            raise ToolProviderError("Participant profile is invalid")
        name, avatar, aliases = row.get("name"), row.get("avatar"), row.get("aliases", [])
        if not isinstance(name, str) or not name.strip() or len(name) > 30:
            raise ToolProviderError("Participant profile nickname is invalid")
        if not isinstance(aliases, list) or len(aliases) > 8 or any(
            not isinstance(alias, str) or not alias.strip() or len(alias) > 30 for alias in aliases
        ):
            raise ToolProviderError("Participant profile aliases are invalid")
        if avatar is not None and (
            not isinstance(avatar, str) or len(avatar) > 150000
            or not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/]+={0,2}", avatar)
        ):
            raise ToolProviderError("Participant profile avatar is invalid")
        result.append({"name": name, "avatar": avatar, "aliases": aliases, "isSelf": row.get("isSelf") is True})
    return result


def build_scene(args, profiles, now):
    people, by_key, matched, used_profiles = [], {}, {}, set()
    for entry in args["participants"]:
        key = entry["key"]
        if key in by_key:
            raise ToolProviderError("Participant keys must be unique")
        if "profile" in entry:
            profile = match_profile(entry["profile"], profiles)
            identity = id(profile)
            if identity in used_profiles:
                raise ToolProviderError("The same saved profile cannot play two roles")
            used_profiles.add(identity)
            matched[key] = profile["name"]
        else:
            profile = {"name": entry["name"], "avatar": None}
        person = {"id": str(len(people) + 1), "name": profile["name"], "avatar": profile["avatar"],
                  "own": entry.get("self") is True}
        if not person["name"].strip():
            raise ToolProviderError("Participant names cannot be blank")
        people.append(person)
        by_key[key] = person
    if sum(person["own"] for person in people) != 1:
        raise ToolProviderError("Choose exactly one participant as the right-hand speaker (self)")
    people.sort(key=lambda person: not person["own"])
    try:
        start = (datetime.fromisoformat(args["start"]) if "start" in args
                 else now.replace(second=0, microsecond=0, tzinfo=None))
        if not 1900 <= start.year <= 9998:
            raise ValueError("start year")
        current = start
        messages = []
        for line in args["messages"]:
            speaker = by_key.get(line["speaker"])
            if speaker is None or not line["text"].strip():
                raise ToolProviderError("Every message needs a declared speaker and nonblank text")
            current += timedelta(seconds=line.get("offset_seconds", 25 if messages else 0))
            messages.append({"person": speaker["id"], "own": speaker["own"], "kind": "text",
                             "text": line["text"], "time": int(current.replace(tzinfo=timezone.utc).timestamp() * 1000)})
    except (ValueError, OverflowError) as error:
        raise ToolProviderError("Use a valid local conversation start time") from error
    scene = {"title": args["title"], "theme": args.get("theme", "wechat"), "people": people,
             "group": len(people) > 2, "messages": messages, "size": SIZES[args.get("ratio", "9:16")],
             "start": int(start.replace(tzinfo=timezone.utc).timestamp() * 1000),
             "captureTime": messages[-1]["time"], "clock": now.strftime("%H:%M")}
    return scene, matched


# A new native user context has no actor cookies or history. The only code
# evaluated is the owner-reviewed renderer and this fixed wrapper; all script
# text and PNG avatars are structured arguments, not executable source.
async def render_frames(runtime, principal, script, scene, mode, locale):
    from ai2apps.browser.background_bidi import BackgroundBiDi
    from ai2apps.browser.background_page import BackgroundPage
    from ai2apps.helper_control import HelperControlClient

    helper = HelperControlClient.from_environment()
    if helper is None:
        raise ToolProviderError("Open AI2Apps Desktop to make the local renderer available")
    await asyncio.to_thread(helper.ensure_browser_host, actor_user_id=principal.actor_user_id)
    connection = BackgroundBiDi()
    user_context = None
    try:
        await connection.connect()
        result = await connection.command("browser.createUserContext", {}, timeout=10)
        user_context = result["userContext"]
        tab = await connection.command("browsingContext.create",
            {"type": "window", "userContext": user_context, "background": True}, timeout=10)
        page = BackgroundPage(connection, tab["context"])
        return await page.call_json("""async (scene, mode, locale) => {
            """ + script + """
            const people = new Map();
            for (const person of scene.people) {
                if (person.avatar) {
                    const image = new Image();
                    image.src = person.avatar;
                    await image.decode();
                    if (image.naturalWidth > 160 || image.naturalHeight > 160)
                        throw Error('Avatar exceeds 160 pixels');
                    person.avatar = {image};
                }
                people.set(person.id, person);
            }
            for (const item of scene.messages) item.person = people.get(item.person);
            const canvas = document.createElement('canvas');
            const paint = window.FantasyFeedRenderer(canvas, (en, zh) => locale === 'zh' ? zh : en);
            const frames = [];
            let bytes = 0;
            for (let i = mode === 'png' ? scene.messages.length : 1; i <= scene.messages.length; i++) {
                paint(scene, i);
                const frame = canvas.toDataURL(mode === 'png' ? 'image/png' : 'image/jpeg', 0.85).split(',')[1];
                bytes += frame.length;
                if (bytes > 8000000) throw Error('Visual sequence exceeds the export size limit');
                frames.push(frame);
            }
            return frames;
        }""", (scene, mode, locale), timeout=45)
    finally:
        try:
            if user_context:
                await connection.command("browser.removeUserContext", {"userContext": user_context}, timeout=10)
        except Exception:
            log.warning("Could not confirm cleanup of an isolated conversation renderer")
        finally:
            await connection.close()


async def execute(runtime, args, context, mini, spec):
    if mini["id"] != MINI or spec["host"] != STUDIO or not context.invocation_id:
        raise ToolProviderError("Fictional conversation export requires its owned Studio binding")
    principal = principal_for(runtime, context)
    host, mounted, broker = owner(runtime, principal, STUDIO, MINI)
    if CAPABILITY not in mounted.capabilities or not runtime.studio_jobs:
        raise ToolProviderError("Studio output is unavailable")
    scope = {"actor_id": principal.actor_user_id, "installation_id": principal.installation_id,
             "app_instance_id": host.id, "studio_id": STUDIO}
    repo = StudioRepository(runtime.database)
    profiles = profile_rows(repo.get_draft(**scope, mini_app_id=MINI))
    old = reserve(runtime, context, args, check_only=True)
    if old:
        return old
    scene, matched = build_scene(args, profiles, datetime.now().astimezone())
    package_instance = mounted.mount["app_instance_id"]
    entry = runtime.extension_manager.instance_entry(package_instance, principal=principal)
    if entry["app_key"] != PACKAGE:
        raise ToolProviderError("Unexpected conversation renderer owner")
    resource = runtime.extension_manager.resolve_app_resource(package_instance, "web/render.js", principal=principal)
    script = resource.read_bytes()
    if hashlib.sha256(script).hexdigest() != RENDERER_SHA256:
        raise ToolProviderError("Conversation renderer version needs a matching Desktop SDK update")
    mode = args.get("format", "png")
    await context.report_progress("Rendering fictional conversation")
    frames = await render_frames(runtime, principal, script.decode(), scene, mode, args.get("locale", "zh"))
    data = json.dumps({"format": mode, "frames": frames, "seconds": args.get("interval", 1.5),
                       "encoding": "jpeg" if mode == "mp4" else "png"}).encode()
    if len(data) > MAX_BYTES:
        raise ToolProviderError("Visual sequence exceeds the export size limit")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        metadata = await asyncio.to_thread(render_visual_sequence, data, directory / "output")
        broker.mounted_mini_app(STUDIO, "aaat", principal=principal)
        old = reserve(runtime, context, args)
        if old:
            return old
        run = repo.create_run(**scope, mini_app_id=MINI, mini_app_version=mini["version"], placement="inline",
                             title=args["title"], input_data={"format": mode}, step_label="Export fictional chat")
        repo.update_run(run["id"], status="running", progress=90, **scope)
        cancelled = False
        try:
            metadata["filename"] = f"fictional-chat-{run['id'][-8:]}.{mode}"
            (directory / "result.json").write_text(json.dumps(metadata))
            publication = asyncio.create_task(asyncio.to_thread(runtime.studio_jobs.publish, {
                **scope, "id": run["id"], "run_id": run["id"], "kind": "visual-sequence", "mini_app_id": MINI,
            }, directory))
            try:
                result = await asyncio.shield(publication)
            except asyncio.CancelledError:
                # Let an admitted publication settle before removing its files.
                cancelled = True
                result = await publication
        except Exception:
            repo.update_run(run["id"], status="failed", progress=90, detail="Could not save output", **scope)
            raise
        response = {"status": "completed", "shared_output": True, "studio_run_id": run["id"],
                    "profiles": matched, "artifact": {"download_url": result["downloadUrl"],
                        "filename": metadata["filename"], "media_type": metadata["media_type"]}}
        receipt(runtime, context, response)
        if cancelled:
            raise asyncio.CancelledError
        return response
