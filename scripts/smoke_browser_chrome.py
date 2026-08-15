#!/usr/bin/env python3
"""Exercise the visible Chrome/BiDi runtime without using an AI model."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ai2apps.browser import (
    BrowserManager,
    BrowserRuntimeConfig,
    ChromeBrowserBackend,
)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/download":
            body = b"browser download fixture"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header(
                "Content-Disposition", 'attachment; filename="fixture.txt"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/login":
            body = b"<title>Authentication Handoff</title><input type=password>"
        elif self.path == "/login-frame":
            body = (
                b"<title>Framed Authentication Handoff</title>"
                b"<iframe src='/frame-login'></iframe>"
            )
        elif self.path == "/frame":
            body = (
                b"<title>Frame Fixture</title><label>Frame input "
                b"<input id='frame-input' aria-label='Frame input'></label>"
                b"<button id='frame-action'>Frame action</button>"
                b"<output id='frame-result'></output>"
                b"<script>document.querySelector('#frame-action').onclick=()=>"
                b"document.querySelector('#frame-result').textContent='frame clicked'</script>"
            )
        elif self.path == "/frame-login":
            body = b"<title>Frame Login</title><input type=password>"
        else:
            body = (
                b"<title>AI2Apps Browser Smoke</title>"
                b"<style>#hover-result{display:none}.hover-host:hover #hover-result{display:inline}</style>"
                b"<nav>Home Products Account Help</nav>"
                b"<article><h1>Browser runtime works</h1>"
                b"<p>Visible evidence introduces a substantial local article used to verify reader mode. "
                b"The managed browser extracts rendered content without modifying the page that the user sees.</p>"
                b"<p>Reader mode should retain paragraphs, links, headings, code examples, and useful tables. "
                b"It should discard navigation, forms, advertising, and unrelated recommendations around the story.</p>"
                b"<h2>Safe extraction</h2>"
                b"<p>Hidden page content is removed using computed browser styles before article scoring begins. "
                b"This matters because invisible text can waste context or attempt to influence an AI agent.</p>"
                b"<p><a href='/source'>Relative source link</a> becomes absolute, while unsafe active content is removed. "
                b"The result can be returned as semantic HTML or compact Markdown for model consumption.</p>"
                b"<pre><code class='language-python'>print('reader mode')</code></pre>"
                b"<p>The final paragraph makes the fixture long enough for strict Readability extraction. "
                b"Metadata and extraction diagnostics remain separate from the canonical article content.</p></article>"
                b"<p style='display:none'>HIDDEN-DISPLAY</p>"
                b"<p style='visibility:hidden'>HIDDEN-VISIBILITY</p>"
                b"<p style='opacity:0'>HIDDEN-OPACITY</p>"
                b"<div aria-hidden='true'>HIDDEN-ARIA</div>"
                b"<div id='hover-target' class='hover-host'>Hover target <span id='hover-result'>revealed</span></div>"
                b"<input id='typing-target' aria-label='Typing target'>"
                b"<input id='file-input' type='file'><output id='file-result'></output>"
                b"<a id='download-link' href='/download' download>Download fixture</a>"
                b"<output id='key-result'></output><output id='click-result'></output>"
                b"<button id='continue'>Continue</button>"
                b"<div id='shadow-host'></div><iframe id='fixture-frame' src='/frame'></iframe>"
                b"<script>const root=document.querySelector('#shadow-host').attachShadow({mode:'open'});root.innerHTML=`<label>Shadow input <input aria-label='Shadow input'></label><button>Shadow action</button><output></output>`;root.querySelector('button').onclick=()=>root.querySelector('output').textContent='shadow clicked';document.querySelector('#typing-target').addEventListener('keydown',e=>document.querySelector('#key-result').textContent=e.key);document.querySelector('#file-input').addEventListener('change',e=>document.querySelector('#file-result').textContent=e.target.files[0]?.name||'');document.addEventListener('click',e=>{if(e.target.id==='continue')document.querySelector('#click-result').textContent='clicked'});setTimeout(()=>{const o=document.createElement('output');o.id='async-result';o.textContent='async ready';document.body.appendChild(o)},250)</script>"
            )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


async def run(profile_path: str) -> dict:
    backend = ChromeBrowserBackend(BrowserRuntimeConfig(profile_path=profile_path))
    test_root = Path(profile_path).parent
    backend.set_download_directory(test_root / "downloads")
    upload_source = test_root / "upload-fixture.txt"
    upload_source.write_text("browser upload fixture", encoding="utf-8")
    manager = BrowserManager(backend)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        started = await manager.start(session_id="browser-smoke")
        await manager.navigate(base_url, session_id="browser-smoke")
        snapshot = await manager.snapshot(session_id="browser-smoke")
        repeated_snapshot = await manager.snapshot(session_id="browser-smoke")
        full_snapshot = await manager.snapshot(
            session_id="browser-smoke", html_mode="full"
        )
        shadow_input_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Shadow input"
        )
        shadow_action_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Shadow action"
        )
        frame_input_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Frame input"
        )
        frame_action_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Frame action"
        )
        await manager.type_text(
            shadow_input_ref,
            "inside shadow",
            session_id="browser-smoke",
            clear=True,
            input_mode="instant",
        )
        await manager.click(
            shadow_action_ref, session_id="browser-smoke", commit=False
        )
        await manager.type_text(
            frame_input_ref,
            "inside frame",
            session_id="browser-smoke",
            clear=True,
            input_mode="instant",
        )
        await manager.click(frame_action_ref, session_id="browser-smoke", commit=False)
        backend.driver.switch_to.frame(
            backend.driver.find_element("css selector", "#fixture-frame")
        )
        frame_state = backend.driver.execute_script(
            "return {value:document.querySelector('#frame-input').value,"
            "result:document.querySelector('#frame-result').textContent}"
        )
        backend.driver.switch_to.default_content()
        shadow_state = backend.driver.execute_script(
            "const r=document.querySelector('#shadow-host').shadowRoot;"
            "return {value:r.querySelector('input').value,"
            "result:r.querySelector('output').textContent}"
        )
        continue_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Continue"
        )
        backend.driver.execute_script(
            "document.querySelector('#continue').outerHTML='<button id=continue>Continue</button>'"
        )
        relocated_wait = await manager.wait_for(
            session_id="browser-smoke",
            condition="element",
            target=continue_ref,
            state="clickable",
            timeout_ms=2_000,
        )
        async_wait = await manager.wait_for(
            session_id="browser-smoke",
            condition="text",
            text="async ready",
            timeout_ms=2_000,
        )
        stable_wait = await manager.wait_for(
            session_id="browser-smoke",
            condition="page_stable",
            timeout_ms=2_000,
            stable_ms=200,
        )
        backend.upload_file("#file-input", upload_source)
        uploaded_name = backend.driver.execute_script(
            "return document.querySelector('#file-result').textContent"
        )
        download_ref = next(
            item["ref"]
            for item in snapshot["snapshot"]["items"]
            if item["text"] == "Download fixture"
        )
        await manager.click(
            download_ref, session_id="browser-smoke", commit=False, duration_ms=180
        )
        staged_downloads = backend.staged_downloads(wait_ms=3_000)
        original_tab = (await manager.list_tabs(session_id="browser-smoke"))["tabs"][0]["id"]
        opened_tab = await manager.open_tab(
            session_id="browser-smoke", url=base_url + "?tab=second"
        )
        tab_count = len((await manager.list_tabs(session_id="browser-smoke"))["tabs"])
        await manager.switch_tab(original_tab, session_id="browser-smoke")
        await manager.close_tab(opened_tab["opened_tab"], session_id="browser-smoke")
        article = await manager.read_article(
            session_id="browser-smoke", output_format="both"
        )
        hovered = await manager.hover(
            "#hover-target", session_id="browser-smoke", duration_ms=280
        )
        hover_visible = backend.driver.execute_script(
            "return getComputedStyle(document.querySelector('#hover-result')).display !== 'none'"
        )
        await manager.type_text(
            "#typing-target",
            "hello",
            session_id="browser-smoke",
            clear=True,
            input_mode="natural",
            delay_ms=2,
        )
        await manager.key_press(
            "ARROW_DOWN", session_id="browser-smoke", target="#typing-target"
        )
        await manager.click(
            continue_ref, session_id="browser-smoke", commit=False, duration_ms=220
        )
        interaction_state = backend.driver.execute_script(
            "return {value:document.querySelector('#typing-target').value,"
            "key:document.querySelector('#key-result').textContent,"
            "click:document.querySelector('#click-result').textContent}"
        )
        relocated_ref = backend.driver.execute_script(
            "return document.querySelector('#continue').getAttribute('data-ai2apps-ref')"
        )
        observation = await manager.observe_changes(session_id="browser-smoke")
        challenge = await manager.navigate(
            base_url + "/login-frame", session_id="browser-smoke"
        )
        return {
            "started": started,
            "snapshot_title": snapshot["snapshot"]["title"],
            "snapshot_items": snapshot["snapshot"]["items"],
            "snapshot_refs_stable": [
                item["ref"] for item in snapshot["snapshot"]["items"]
            ]
            == [item["ref"] for item in repeated_snapshot["snapshot"]["items"]],
            "snapshot_text": snapshot["snapshot"]["text"],
            "snapshot_html": snapshot["snapshot"]["html"],
            "snapshot_has_layout": "data-ai2apps-rect=" in snapshot["snapshot"]["html"],
            "hidden_text_removed": not any(
                marker in snapshot["snapshot"]["text"]
                for marker in (
                    "HIDDEN-DISPLAY",
                    "HIDDEN-VISIBILITY",
                    "HIDDEN-OPACITY",
                    "HIDDEN-ARIA",
                )
            ),
            "full_html_has_hidden": "HIDDEN-DISPLAY"
            in full_snapshot["snapshot"]["html"],
            "article": article["article"],
            "natural_interactions": {
                "hover": hovered,
                "hover_visible": hover_visible,
                "relocated_wait": relocated_wait["wait"],
                "relocated_ref": relocated_ref,
                "async_wait": async_wait["wait"],
                "stable_wait": stable_wait["wait"],
                "uploaded_name": uploaded_name,
                "staged_downloads": staged_downloads,
                "tab_count_during_test": tab_count,
                "observation": observation["observation"],
                **interaction_state,
            },
            "nested_contexts": {
                "frame_ref": frame_action_ref,
                "frame": frame_state,
                "shadow_ref": shadow_action_ref,
                "shadow": shadow_state,
                "shadow_serialized": "data-ai2apps-shadow-root"
                in snapshot["snapshot"]["html"],
                "frame_serialized": "data-ai2apps-frame-context"
                in snapshot["snapshot"]["html"],
            },
            "challenge": challenge,
        }
    finally:
        await manager.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def verify(result: dict) -> None:
    interactions = result["natural_interactions"]
    nested = result["nested_contexts"]
    checks = {
        "stable_refs": result["snapshot_refs_stable"],
        "hidden_content_filtered": result["hidden_text_removed"],
        "stale_ref_relocated": interactions["relocated_wait"]["satisfied"],
        "page_wait": interactions["stable_wait"]["satisfied"],
        "upload": interactions["uploaded_name"] == "upload-fixture.txt",
        "download": bool(interactions["staged_downloads"]["complete"]),
        "tabs": interactions["tab_count_during_test"] == 2,
        "shadow_input": nested["shadow"]["value"] == "inside shadow",
        "shadow_click": nested["shadow"]["result"] == "shadow clicked",
        "frame_input": nested["frame"]["value"] == "inside frame",
        "frame_click": nested["frame"]["result"] == "frame clicked",
        "nested_serialization": nested["shadow_serialized"]
        and nested["frame_serialized"],
        "framed_login_handoff": result["challenge"]["state"] == "user_required",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("Browser smoke checks failed: " + ", ".join(failed))
    result["checks"] = checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    args = parser.parse_args()
    if args.profile:
        result = asyncio.run(run(args.profile))
        verify(result)
        print(json.dumps(result, indent=2))
        return
    with tempfile.TemporaryDirectory(prefix="ai2apps-browser-smoke-") as temp:
        result = asyncio.run(run(str(Path(temp) / "profile")))
        verify(result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
