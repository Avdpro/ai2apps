# Mobile Chat Markdown rendering

Mobile ordinary Chat and Agent final messages used `textContent`, so headings,
tables and Markdown links appeared verbatim. Both standalone Chat and the inline
Mobile Shell now load the existing bundled marked and DOMPurify libraries before
the Chat client. Restored assistant messages and streaming updates share the same
renderer; user inputs and error messages remain literal text.

GFM tables, headings, emphasis, lists, quotes and code blocks are sanitized with
an explicit tag/attribute allowlist. Only HTTP/HTTPS links are activated, with
noopener/noreferrer. Script, event-handler, embedded-frame and image markup is
excluded. Markdown does not fetch remote images automatically; existing explicit
attachment/result-image handling remains independent. Tables scroll within the
message area and code preserves whitespace without widening the page.

Seventeen Node/Chrome tests passed, covering existing timeline/form recovery,
normal streaming, tables, links, code, headings, lists, literal user input,
390-pixel page layout, reload and malicious markup/remote image exclusion. The
Markdown-specific test uses the full mobile template and bundled parser and
sanitizer. Both entry templates were rendered to verify dependency order.

Dev PID13997 / port54871 provides the changed JS/CSS and bundled Markdown
dependencies byte-for-byte from the live checkout. App/Helper source roots were
verified. This is a static/template change and requires refreshing the phone page,
without restarting Local. Phone-device screenshot acceptance is still pending.

All 252 mandatory AaAT boundary tests passed, exit 0. The existing headless
Metal atexit warning did not affect successful completion.

## Assistant content and actions

Assistant replies now use full-width, borderless content (15px/1.65 line height),
with accessible copy and read-aloud buttons below each reply. User bubbles stay
compact/right-aligned; Agent execution cards and forms retain their own controls.
Copy uses the current source Markdown, including streamed updates; clipboard
failure falls back to a user-initiated selection/copy and then a clear error.

Read-aloud now calls Desktop TTS (the initial device-voice implementation has
been removed). It reads sanitized visible content, excludes code blocks and
splits long text into bounded Unicode chunks. Stop/switch/page-exit aborts pending
requests and releases local audio URLs. If WebKit blocks automatic playback, the
returned audio has controls and an explicit tap-to-play prompt. There is no
phone system-voice fallback. Real iPhone playback still needs device acceptance.

The exact POST `/chat/threads/{id}/speech` checks the current actor/client-scope
and active Session, accepts only bounded text (no model IDs, voices, endpoints or
filesystem references), and invokes installed ready Desktop `audio_tts` providers
through the existing ModelInvocation and shared speech adapter. Selection uses
the Desktop Package catalog's first ready TTS and its declared default voice;
it does not read the Desktop browser's private localStorage voice settings.
No ready provider means an explicit instruction to install/configure TTS on
Desktop. Provider failure also reports a Desktop configuration/service error.

Signed Agent/unified Owner-Agent use the existing exact signed Chat transport;
ordinary Owner Mobile exports only this bounded Chat speech operation through
the lease/Origin/App-enabled gateway. The route never forwards arbitrary model
requests or uses browser Cookie credentials for inference. Session ACLs,
ModelInvocation resource/identity checks and mobile connection revocation remain.

Sixteen distinct Node/Chrome tests passed, including 390px standalone/inline
toolbar presentation, both clipboard paths, no business calls, playback stop and
switch cleanup, existing user bubbles, Markdown, forms, timeline, notifications
and reconnect. Screenshot visually reviewed. App-Dev port62859 serves the exact
changed JS/CSS from this checkout; both templates have new cache versions.
Refresh/reopen Mobile Chat to apply. No Local restart, Runtime/model Package
upgrade or additional static-file allowlist is required. Desktop-backed TTS adds
the explicit speech route above and needs a standard Local restart, not an App
or Runtime rebuild. Both Mobile entry templates have a fresh desktop-tts cache
version. Desktop browser speech settings are otherwise unchanged.

### Desktop TTS verification

The current Desktop-backed implementation passed 35 distinct backend tests
(owned Session access, ready/missing providers, binary audio, bounded input,
Owner lease/App gate and signed dispatch), 9 Node/Chrome regressions, and all
255 mandatory AaAT boundary tests. Audio and provider calls use fixtures; no
real worker synthesis or iPhone playback acceptance is claimed. Missing TTS
instructions remain visible beneath the reply, not only in a transient toast.

App-Dev Local was restarted through its own Helper to PID66969/port65185.
Both App/Helper source-root metadata and the running Chat API import match
the live checkout. Refresh Mobile after this backend activation. No Runtime,
model Package or native App rebuild is necessary; Dev/Test/production were
not restarted.
## Mobile 会话操作兼容性修复（2026-10-26）

列表右侧菜单使用页面内的改名/删除确认对话框，不依赖 window.prompt/confirm。
iOS WKWebView 的现有 UIDelegate 没有实现这两种原生对话框；Chrome 支持它们的
fixture 不能证明手机可用。新回归明确令原生调用抛错，仍验证确认、取消、改名和删除。

独立签名 JS transport 与原生 MobileAgentKey 只允许 GET/POST/PUT。
会话操作改走 POST /chat/threads/{id}/manage，接受 rename/delete、expected_revision
及改名时的 bounded title；服务端严格验证后委托原 PATCH/DELETE handler，保持原
actor/client-scope、权限、乐观版本及软删除语义。不扩大原生 HTTP 方法授权，不需要
升级 iOS。旧 canonical 方法继续兼容。Owner/统一 Owner-Agent/独立签名与旧 Shell
仅开放精确路径，不是任意 API 代理。重复或越权请求仍由原仓储拒绝。

手机使用前需要对应 Desktop Local 加载新 API；旧 Shell 入口需要采用含新路由的
标准 Desktop/App-Dev 构建。刷新模板带新的 session-dialog-20261026 缓存版本。
测试不删除用户真实会话。
