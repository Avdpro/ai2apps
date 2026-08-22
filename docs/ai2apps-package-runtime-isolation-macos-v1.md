# AI2Apps Package Runtime Isolation on macOS v1

Status: Containment baseline and Python Model Worker v1 implemented; signed XPC phase pending
Audience: AI2Apps runtime developers and model Package developers
Scope: The first security boundary for every non-built-in Package and every
same-device Local Installation on macOS

Developer-facing current behavior, runtime-mode selection, manifest examples,
local testing, and troubleshooting are documented in
[Service/Package Sandbox Development Guide](service-package-sandbox-development-guide.md).
That guide distinguishes today's transitional Managed Service sandbox from the
future XPC/App Sandbox target specified here.

## 1. Review requested

This document proposes a first-stage security boundary for installable AI2Apps
Packages. Package developers should review whether their current model runtime
can operate inside this boundary and report the blockers listed in section 15.

The core rule is:

> Code that appears after the AI2Apps application was built must never be
> imported or executed by the AI2Apps host process.

An AI2Apps repository signature authenticates the publisher and artifact. It
does not make a separately downloaded Package built-in and does not grant host
process execution.

### 1.1 Implementation status (2026-08-17)

The application-layer security upgrade described in Phases 0–2 has now landed.
The production rule remains fail-closed wherever the signed Worker/XPC boundary
does not yet exist.

Implemented and release-gated:

- schema v35 creates one stable `local_security_identity` before optional Cloud
  enrollment; security namespaces no longer derive from a path, port, or PID;
- an atomic host-level identity claim rejects a copied data root that attempts
  to reuse another root's identity, while a non-blocking root lease rejects two
  live Hosts using the same canonical Platform root;
- Local and Cloud-browser cookies have Installation-specific names and Local
  Sessions are checked against the receiving Installation. Legacy admin
  cookies are deleted during migration/logout and no longer grant authority;
- first-run WebUI enrollment uses Cloud login/register, explicit Core binding,
  and then the same Core/Member Local Session flow used on later visits;
- Account logout revokes the Local Session and removes the scoped Local, Cloud,
  and legacy-admin cookies;
- the main API key is retired from WebUI login, query-string auto-login,
  templates, browser storage, diagnostics, and settings reads. It and sub-keys
  authenticate inference APIs only and cannot administer Platform, Packages,
  Secrets, Trust policy, or model lifecycle;
- the native Helper opens the account login URL without embedding the main API
  key. The legacy `skip_api_key_verification` inference option cannot bypass
  Core authorization for Web administration;
- cookie-authenticated Web writes require an exact scheme/host/port Origin;
  this closes the cross-port CSRF gap that `SameSite=Strict` alone leaves on
  loopback hosts;
- saved sub-key values are write-only after creation; settings list only a
  SHA-256 fingerprint and revoke by fingerprint;
- SecretBackend accounts use
  `ai2apps.v1.<local_security_identity>.<opaque_key>`, with verified safe legacy
  migration. Ambiguous legacy browser-Cloud sessions are never auto-claimed;
- Secret values are rejected from metadata, successful and denied injections
  are audited without the value, Trust Center shows the last Tool use, and
  installed external Services cannot receive Secret values because their
  loopback process identity is not authenticated;
- Package management, capability policy, remote control, Secret management,
  Service/Agent management, and Interactive Package control require Core
  system-management authority;
- Package publishing operations bind their Registry manager to the current
  browser-scoped Cloud session. Publisher discovery, key registration,
  submission, review, and publication fail closed when that browser session is
  absent or invalid; they never fall back to the installation-level Cloud
  client or another browser's session;
- Registry-published Model Worker Services use a signed outer
  `ai2apps.package-manifest.v1` plus the signed inner `service.yaml`. The outer
  manifest exposes the Cloud catalog identity and coarse permission summary;
  installation preserves the inner Service's exact structured sandbox policy,
  runtime identity, pinned weight grant, and Metal declaration instead of
  flattening or weakening them;
- installed Service endpoints are restricted to explicit loopback HTTP ports;
  managed Services receive a minimal environment, scoped filesystem roots, and
  no broad Mach lookup. Agent Process sandboxes likewise no longer grant every
  Mach service;
- installed `omlx.model_adapters` payloads are not added to Host `sys.path` and
  are not imported unless the explicit
  `AI2APPS_UNSAFE_IN_PROCESS_MODEL_ADAPTERS=1` development escape hatch is set;
- the release preflight fails when the adapter fail-closed rule, Mach boundary,
  inference/admin credential split, Core-only Web guard, cookie Origin check,
  native browser URL, or Web credential non-disclosure regresses.
- Model Worker v1 uses system-owned startup, an isolated Package import path,
  ephemeral Host authentication, serialized inference, lifecycle/cancellation
  handling, repository-scoped weight grants, and pinned Qwen3.8 Package
  declarations. Package code and MLX state remain outside the Host process.
- A selected Package model public ID is resolved by exact Package ownership
  before legacy local-model alias normalization. Provider-prefix stripping can
  therefore never redirect an explicit Package selection to a similarly named
  Host model directory and bypass its isolated Worker or Package-owned loader.

Not yet implemented, and therefore not claimed as complete isolation:

- the AI2Apps-signed XPC Package Runner that will replace the transitional
  Python Worker transport while retaining the Model Worker v1 Adapter contract;
- Host-brokered outbound networking for Workers (managed Service networking is
  still an explicit coarse Package permission rather than per-origin Broker
  grants);
- migration and real-checkpoint validation of the remaining DeepSeek/Qwen3.6
  installable model adapters (Qwen3.8 source migration is implemented);
- a separately signed Host-only Keychain access group and packaged-app
  entitlement audit.

Until those items land, installable model-adapter execution stays disabled in
normal builds. `sandbox-exec` containment for managed Services is a transitional
defense and must not be described as equivalent to the signed XPC boundary.

## 2. Baseline security assessment before this upgrade

This section records the vulnerable baseline that motivated the upgrade. The
evidence links point to the repository state originally reviewed on 2026-08-17
and are retained as threat-model history. Section 1.1 is authoritative for the
implemented containment state; line numbers may move as implementation changes.

### 2.1 Executive finding

Installable Service Packages are now denied `in_process` execution, but
installable model-adapter wheels use a separate loader that is not covered by
that protection. An installed model adapter is added to the Host's `sys.path`
and its Python entry point is imported by the oMLX Host after restart.

The practical security boundary is therefore inconsistent:

| Package/runtime class | Current execution boundary | Current assessment |
|---|---|---|
| Built-in service/code | AI2Apps Host | Expected trusted code |
| Installed Service Package | Managed process or external service | Host execution denied |
| Process-based model provider, such as `qwen35-provider` | Managed process | Not imported by Host |
| Installed `omlx.model_adapters` wheel | AI2Apps/oMLX Host | **Unisolated Host-code path** |

The highest-priority issue is the final row. The rest of this proposal closes
that path without weakening the existing Service Package rule.

### 2.2 Evidence: Service Packages are isolated, model adapters are not

The Service Package manager rejects every installable Service whose runtime
mode is `in_process`. This check is based on the fact that the code is
installable, not on whether the publisher is AI2Apps:

- [`ai2apps/packages/manager.py`, `_require_isolated_runtime`](../ai2apps/packages/manager.py#L74-L83)
- [`ai2apps/packages/manager.py`, installed Services use `source="installed"`](../ai2apps/packages/manager.py#L354-L378)

This is the intended rule. A repository signature verifies origin and
integrity; it does not change an installed Service into a built-in Service.

The independently packaged Qwen3.5 provider already follows this model: its
manifest declares `runtime.mode: process` and an OpenAI-compatible endpoint:

- [`packages/qwen35-provider/service.yaml`](../packages/qwen35-provider/service.yaml#L7-L18)

Model-adapter wheels do not pass through `ServicePackageManager`. They use
`ModelAdapterPackageManager` and a process-local entry-point registry, so the
Service isolation check is never reached.

### 2.3 Evidence: model-adapter code enters the Host process

The current load sequence is:

1. A model adapter wheel declares Python code in the
   `omlx.model_adapters` entry-point group. The reference packages all use this
   mechanism, for example:
   [`packages/omlx-model-qwen38/pyproject.toml`](../packages/omlx-model-qwen38/pyproject.toml#L17-L18).
2. During oMLX Host initialization, `configure_model_adapter_packages()` is
   called after global Host state and the Host API key have been assigned:
   [`omlx/server.py`](../omlx/server.py#L2042-L2048).
3. Every active adapter `site-packages` directory is inserted at index zero of
   the Host's `sys.path`:
   [`omlx/model_adapters/packages.py`](../omlx/model_adapters/packages.py#L337-L349).
4. Adapter discovery executes `entry_point.load()`, which imports and executes
   the Package module in the current Python interpreter:
   [`omlx/model_adapters/registry.py`](../omlx/model_adapters/registry.py#L86-L105).
5. The adapter's custom `load()` operation can construct and return the model
   object used by the Host loader:
   [`omlx/utils/model_loading.py`](../omlx/utils/model_loading.py#L1042-L1051).

Consequences:

- Adapter Python code has the Host's process identity, entitlements, imported
  modules, environment, open resources, and filesystem/network reachability.
- Python visibility conventions such as private attributes do not form a
  security boundary against code running in the same interpreter.
- An adapter can modify process-global state, monkey-patch Host modules, or
  interfere with another adapter.
- Prepending the Package directory to `sys.path` also creates module-shadowing
  risk for later imports.
- Catching an exception around `entry_point.load()` improves availability but
  does not undo code or side effects that ran during import.

This is direct source-code evidence of shared-process execution. It is not a
claim that a known published adapter is malicious or that a credential has
already been stolen.

### 2.4 Evidence: local wheel installation does not require an AI2Apps signature

The authenticated administrator endpoint accepts an absolute local wheel path
and calls `ModelAdapterPackageManager.install()` directly:

- [`omlx/admin/routes.py`](../omlx/admin/routes.py#L6345-L6369)

The local inspection path validates the wheel filename, platform tags, archive
paths, metadata, dependencies, size, digest, and presence of an adapter entry
point. It does not authenticate a publisher signature:

- [`omlx/model_adapters/packages.py`](../omlx/model_adapters/packages.py#L144-L224)
- [`omlx/model_adapters/packages.py`, extraction and activation](../omlx/model_adapters/packages.py#L226-L262)

Therefore an administrator can install an arbitrary structurally valid adapter
wheel. After the required restart, that wheel executes in the Host. Requiring
administrator action reduces the exposure but does not turn the imported code
into built-in code or provide containment after installation.

### 2.5 Evidence: the official catalog authenticates artifacts but does not sandbox them

The official catalog path is stronger than local installation. It verifies a
repository snapshot with the pinned AI2Apps fingerprint, binds the release
identity to the wheel name/version, and verifies the downloaded size and
SHA-256 digest:

- [`omlx/model_adapters/catalog.py`, trust root](../omlx/model_adapters/catalog.py#L36-L42)
- [`omlx/model_adapters/catalog.py`, signature verification](../omlx/model_adapters/catalog.py#L379-L404)
- [`omlx/model_adapters/catalog.py`, artifact verification](../omlx/model_adapters/catalog.py#L451-L528)

These controls provide provenance, integrity, rollback protection, and release
identity. They do not create a runtime sandbox. Once installed, an official
wheel follows the same Host `sys.path` and `entry_point.load()` path as a local
wheel.

For this reason, an official adapter should be classified as
`first-party signed`, not `built-in`. It may deserve a different installation
approval experience, but it must still run outside the Host.

### 2.6 Evidence: moving provider keys to Keychain does not protect them from Host code

The current macOS backend uses Security.framework Keychain calls and exposes a
Python `SecretBackend` interface with `store`, `load`, and `delete` operations:

- [`ai2apps/secrets/backends.py`](../ai2apps/secrets/backends.py#L25-L40)
- [`ai2apps/secrets/backends.py`, Keychain lookup and load](../ai2apps/secrets/backends.py#L80-L150)

Provider configuration stores an opaque credential reference in ordinary
configuration and resolves the actual key through the Host-bound
`SecretBackend`:

- [`ai2apps/model_manager.py`](../ai2apps/model_manager.py#L90-L125)
- [`ai2apps/model_manager.py`, internal credential resolution](../ai2apps/model_manager.py#L251-L263)

This is a material improvement over plaintext configuration at rest. However,
Keychain protects credentials from other identities and from offline file
reading; it cannot protect a key from arbitrary code already executing with the
authorized Host identity. The Host also exposes its initialized runtime and
SecretBackend-bound model manager to its own Python modules:

- [`omlx/server.py`](../omlx/server.py#L328-L344)

Accordingly, keeping Package code out of the Host is necessary for the Keychain
upgrade to provide the intended boundary. The target design also calls for an
explicit Host-only Data Protection Keychain access group rather than relying
only on the current legacy generic-password API behavior.

### 2.7 Current attack path and impact

No vulnerability in MLX or macOS is required. The present path is:

```text
Administrator installs a local adapter wheel
        or an official signed adapter is downloaded
                         |
                         v
Wheel is structurally checked and extracted immutably
                         |
                         v
Host restarts and prepends adapter path to sys.path
                         |
                         v
Host calls entry_point.load() and executes Package Python
                         |
                         v
Package code inherits Host process authority
```

Potential impact includes provider-key disclosure, Host configuration/database
access, prompt or output observation, modification of model routing, arbitrary
outbound requests, persistence through activated Package state, interference
with other models, and Host crash or resource exhaustion.

The issue is rated **High** for the current local product because installation
requires an authenticated administrator action. It would become more severe if
Package installation were delegated broadly, silently updated without strong
release controls, or exposed through a compromised Discover workflow.

### 2.8 Existing protections that remain valuable

The proposal does not replace these existing controls:

- Service Packages already reject `in_process` execution.
- Official repositories use pinned signatures and artifact digests.
- Local wheels receive archive traversal, symlink, size, compatibility,
  dependency, and entry-point validation.
- Package versions are stored in content-addressed immutable directories.
- Provider keys are no longer stored as plaintext in provider configuration.
- Administrative authentication protects Package-management endpoints.

These controls should remain. The missing control is runtime authority
separation after a model-adapter wheel has been accepted.

### 2.9 Required remediation derived from the evidence

The evidence leads to four immediate requirements:

1. Delete the Host `sys.path` insertion and Host entry-point import path for
   every installed model adapter.
2. Run the Package adapter, loader, MLX model, and generation loop in a
   Package-scoped Worker process.
3. Give that Worker no Host Keychain/SecretBackend authority and only explicit
   filesystem capabilities.
4. Deny direct Worker networking and mediate approved requests through a
   policy-enforcing Network Broker.

The remaining sections specify that target design.

### 2.10 Current same-device multi-instance isolation assessment

AI2Apps may run more than one Local instance on the same Mac. Each instance is
an independent **Installation**, even when the instances use the same macOS
login account, executable build, and Cloud account. An Installation is a
security tenant, not merely a port number or a different model configuration.

The current path layout provides useful logical separation. A distinct
`base_path` produces a distinct Platform database, artifacts directory,
Package and Sandbox roots, projects and documents roots, browser-profile root,
and encrypted-secret fallback directory:

- [`ai2apps/config.py`, `PlatformPaths.from_base_path`](../ai2apps/config.py#L45-L75)

Installation and Core-user bindings are also stored in the per-instance
Platform database. That database permits at most one Installation binding and
rejects an attempt to replace its Cloud authority with another one:

- [`ai2apps/identity.py`, one binding per database](../ai2apps/identity.py#L184-L208)
- [`ai2apps/identity.py`, bind-once authority check](../ai2apps/identity.py#L227-L252)

Consequently, two instances with different base paths can already retain
different Core users and membership projections. This is the correct logical
model, but it is not yet a complete security boundary.

The following gaps remain:

1. **The macOS Keychain backend is shared.** Every instance currently creates
   `MacOSKeychainBackend()` with the default service name
   `AI2Apps Secret Store`; the provider factory ignores the per-instance
   secrets path for this backend:
   [`ai2apps/secrets/backends.py`](../ai2apps/secrets/backends.py#L33-L40) and
   [`ai2apps/secrets/factory.py`](../ai2apps/secrets/factory.py#L19-L24).
2. **Provider-key namespacing is collision resistance, not authorization.**
   Provider keys include a hash of `base_path`, which helps prevent accidental
   reuse, but another process with the same Host identity can derive that name
   if it knows the path:
   [`ai2apps/model_manager.py`](../ai2apps/model_manager.py#L111-L120).
3. **Web cookies have process-global names.** The current local identity and
   legacy admin cookies are respectively `ai2apps_local_session` and
   `omlx_admin_session`:
   [`ai2apps/identity.py`](../ai2apps/identity.py#L19-L20) and
   [`omlx/admin/auth.py`](../omlx/admin/auth.py#L17-L20). Cookies are scoped by
   host and path, not TCP port. Instances at `127.0.0.1:8000` and
   `127.0.0.1:8100` can therefore receive the same cookie.
4. **A Unix file mode is not an instance boundary.** Different roots and mode
   `0600` protect data from other macOS users, but normally not from another
   process running as the same macOS user.
5. **A compromised Host can cross logical namespaces.** Merely adding an
   `installation_id` prefix does not stop arbitrary code executing as the Host
   from opening another known base path or querying another known Keychain
   item. This reinforces the requirement to keep installed Package code out of
   every Host process.

Current status must therefore be described as **per-base-path logical
separation**, not strong same-user multi-instance isolation.

## 3. Definitions

- **Built-in**: Code included in the signed AI2Apps application build, bound to
  that application release, and not replaceable through Package installation.
- **First-party signed Package**: A separately released Package authenticated by
  the pinned AI2Apps repository trust root.
- **Third-party Package**: A Package signed by another publisher.
- **Local development Package**: An unsigned or locally signed Package accepted
  only while explicit developer mode is enabled.
- **Host**: The trusted AI2Apps/oMLX control process that owns configuration,
  credentials, Package policy, routing, and user interaction.
- **Package Worker**: A sandboxed process that executes one installed Package.
- **Network Broker**: A trusted host service that performs approved network
  requests for Package Workers.
- **Installation**: One independently initialized AI2Apps Local instance with
  an immutable `installation_id`, one data root, one Core-user binding, its own
  sessions, policies, Packages, and credentials.
- **Secret Broker**: A trusted Host-owned service that resolves secrets only
  after checking the authenticated caller, Installation, capability, and
  operation. Package Workers never receive its Keychain authority.

The first-party, third-party, and local-development classes have different
installation trust, but all are non-built-in and therefore use Package Workers.

## 4. Security goals

For a compromised or malicious Package, the v1 boundary must prevent it from:

1. executing Python or native Package code in the Host;
2. reading AI provider keys from Keychain or `SecretBackend`;
3. reading other Packages, Host databases, user documents, or arbitrary files;
4. making arbitrary local or Internet connections;
5. impersonating another Package when requesting Host capabilities;
6. keeping Host privileges after uninstall, upgrade, or Worker termination.

The boundary should also contain ordinary crashes and make CPU, memory, disk,
network, and request activity attributable to a Package identity.

For two Local Installations on the same device, the v1 application boundary
must additionally prevent accidental or unauthorized reuse of:

1. Core-user and Member sessions;
2. provider credentials, API client tokens, and federation credentials;
3. Package grants, Trust Center decisions, and audit records;
4. browser profiles, documents, projects, and Package-private data;
5. localhost service authority and remote-access identity.

## 5. Non-goals for v1

The first stage does not promise:

- complete protection against GPU denial of service;
- confidential model weights against a Package explicitly authorized to read
  those weights;
- isolation between multiple models intentionally shipped in the same Package;
- support for arbitrary subprocess trees, debuggers, JIT runtimes, kernel
  extensions, or unrestricted native plugins;
- a general-purpose virtual machine or Linux-compatible container environment.

V1 does not claim that one fully compromised AI2Apps **Host** can be contained
from another Host running under the same macOS user. That stronger boundary
requires separate macOS users, separately entitled App Containers, or virtual
machines. The product boundary assumes that signed AI2Apps Host and Broker
components are trusted while installed Package, Agent, Tool, Service, and
model-adapter code is untrusted. The architecture must nevertheless avoid
giving one healthy instance's ordinary sessions or API tokens validity in
another instance.

Resource limits, covert channels, and stronger per-model isolation can be
added after the Host execution boundary is closed.

## 6. Required architecture

```text
+-------------------------- AI2Apps Host --------------------------+
| Package verification and policy                                  |
| Model admission and routing                                      |
| Keychain / SecretBackend                                         |
| Model downloader and cache manager                               |
| Network Broker                                                   |
| Package Worker supervisor                                        |
+-----------------------------+------------------------------------+
                              | authenticated XPC/RPC
                              v
+---------------------- Package Worker A --------------------------+
| One package_id + package_version                                 |
| Package adapter code                                             |
| oMLX/MLX model engine and model state                             |
| Read-only Package payload                                        |
| Read-only selected model weights                                 |
| Read/write Package-private data                                  |
| No Host secrets; no direct network                               |
+------------------------------------------------------------------+
```

The model object cannot safely be created in a Worker and returned to the Host
as a Python object. For a Package-supplied model, the adapter, model loader,
MLX model, tokenizer/processor, inference loop, and Package-owned patches must
remain inside the same Worker. The Host sends structured inference requests and
receives streamed structured results.

The default isolation unit is `package_id + package_version`. Multiple models
from the same immutable Package may share that Worker. Different Packages must
not share a Python interpreter or address space.

## 7. macOS enforcement mechanism

The production boundary should use an AI2Apps-signed XPC Service or dedicated
helper application with App Sandbox enabled and minimal entitlements. Apple
recommends XPC Services for privilege separation because a normal child process
launched with `Process`, `NSTask`, or `posix_spawn` generally inherits the
parent's sandbox rights.

The design must not depend on `sandbox-exec` or undocumented Seatbelt profiles
as a production security contract.

Relevant Apple documentation:

- [Creating XPC Services](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingXPCServices.html)
- [Discovering and diagnosing App Sandbox violations](https://developer.apple.com/documentation/security/discovering-and-diagnosing-app-sandbox-violations)
- [Configuring the macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox)

Before implementation, the desktop packaging team must verify that the chosen
signed Runner can load the supported Python, MLX, Metal, and native-extension
artifacts without granting broad Hardened Runtime exceptions to the Host.

## 8. Keychain and SecretBackend policy

### 8.1 OS-enforced boundary

The Worker executable must have a distinct signing identifier and must not join
the Host's Keychain access group. AI provider credentials must be stored in the
Data Protection Keychain under an explicit Host-only access group.

The Worker must not receive:

- Host Keychain access-group entitlements;
- a shared App Group that also acts as the Host credential group;
- secret values in environment variables, command-line arguments, temporary
  files, logs, or crash metadata;
- direct access to the Host database or credential store.

See [Sharing access to keychain items among a collection of apps](https://developer.apple.com/documentation/security/sharing-access-to-keychain-items-among-a-collection-of-apps).

### 8.2 Application-enforced boundary

macOS does not understand the AI2Apps `SecretBackend` Python abstraction. The
Host must therefore omit secret-management methods from the Package RPC
protocol and authenticate every connection as one Package identity.

If a future Package legitimately requires a credential, it must use a separate
capability design. The preferred design is for the Host to perform the remote
request without disclosing the credential. Passing a long-lived provider key
to a Worker is out of scope for v1 and should remain prohibited.

## 9. Filesystem policy

The Worker begins with its App Sandbox container and no general access to the
user's home directory. The Host grants only the following paths using
security-scoped URLs/bookmarks or an equivalent OS-enforced mechanism:

| Resource | Default access | Notes |
|---|---:|---|
| Immutable Package payload | Read only | Exactly one package digest/version |
| Package-private data | Read/write | Must not contain another Package's data |
| Selected model weights | Read only | Limited to models assigned to the Worker |
| Package temporary directory | Read/write | Removed after termination when safe |
| Host database/configuration | None | Never granted |
| Other Package directories | None | Never granted |
| User documents | None | Future explicit capability only |

The Host model downloader should own downloading, verification, conversion,
deletion, and upgrade of model weights. A Worker should normally receive a
read-only prepared checkpoint.

The Python Model Worker v1 implementation enforces this as follows: each model
declares a Hugging Face repository and an immutable commit revision; trusted
Host code resolves the matching snapshot and passes that exact path to the
Adapter. The sandbox grants read access only to that repository cache root
(rather than the complete Hugging Face cache), because snapshot files may be
links into the same repository's `blobs/` directory. Missing snapshots are
represented as unavailable and are not converted into broader filesystem
access. Package-supplied absolute paths and mutable branch/tag names are
rejected as authority.

Before issuing the grant, the Host also requires a checkpoint config and a
complete safetensors set (all files named by the shard index, or at least one
unsharded safetensors file). Partial downloads remain unavailable instead of
being exposed to a Worker as loadable checkpoints.

Security-scoped access must be released when the model unloads or the Worker
terminates. The supervisor must not place sensitive data from different
Packages in a common directory that every Runner instance can access.

See [Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox).

## 10. Network policy

App Sandbox can allow or deny outbound networking, but its entitlement does not
express a runtime domain allowlist. Therefore Package Workers must not receive
the `com.apple.security.network.client` entitlement in v1.

Workers make network requests through an authenticated Network Broker RPC. The
Broker applies policy using the caller's immutable Package identity.

Default policy:

- deny all direct Internet and local-network access;
- allow only reviewed HTTPS origins required by the Package;
- access AI2Apps local services by logical service identity through XPC/RPC,
  not by scanning or connecting to arbitrary localhost ports;
- require an explicit user/admin grant before adding any other origin;
- make grants revocable and scoped to Package ID, publisher, operation, origin,
  and optional expiry.

The Broker must validate more than the original URL:

1. normalize the scheme, host, internationalized domain name, and port;
2. reject embedded credentials and ambiguous URL forms;
3. reject raw IP destinations unless an exact reviewed rule permits them;
4. resolve DNS and defend against DNS rebinding to loopback, link-local, private,
   multicast, metadata, and other prohibited ranges;
5. revalidate every redirect destination;
6. require valid TLS for Internet origins;
7. enforce request and response size, duration, concurrency, and method limits;
8. strip unapproved headers and never attach Host credentials automatically;
9. record a redacted audit event without logging secrets or prompt bodies.

Package manifests may declare requested origins, but declarations are requests,
not permissions. Wildcards should be rejected by default. If subdomains are
required, the policy must define suffix matching precisely and prevent values
such as `allowed.example.evil.test` from matching.

Large model artifacts should be downloaded by the trusted Host downloader from
signed, pinned release metadata rather than proxied through arbitrary Package
code.

## 11. Worker RPC contract

The initial protocol should remain small, versioned, and data-only. A possible
minimum surface is:

```text
handshake(protocol_version, package_identity, launch_nonce)
discover_models()
load_model(model_id, granted_resource_handles, runtime_options)
generate(request_id, model_id, normalized_request) -> event stream
cancel(request_id)
health()
runtime_metrics()
unload_model(model_id)
shutdown()
```

Protocol requirements:

- no Python object serialization such as `pickle`;
- bounded JSON, protobuf, or another schema-validated representation;
- bounded message size and nesting depth;
- Package identity established by the Host/XPC connection, never trusted from
  a caller-supplied field;
- launch nonce and protocol version checked before resource grants;
- unknown methods and fields rejected;
- cancellation, Worker death, timeout, and partial stream behavior defined;
- prompt and output content excluded from logs by default.

Tool execution, SecretBackend access, arbitrary Host imports, and general file
or socket handles are not part of this protocol.

## 12. Package manifest additions

A future manifest may describe requested resources explicitly:

```yaml
runtime:
  mode: package-worker
  protocol: ai2apps.model-worker/v1

permissions:
  model_weights:
    - model_id: example/model
      access: read
  package_data:
    access: read-write
  network:
    origins:
      - https://huggingface.co:443
    reason: Fetch reviewed metadata only
  accelerator:
    metal: true
```

The installer must reject `in_process` for every non-built-in Package. A signed
manifest cannot override this invariant. Installation approval and runtime
capability approval are separate decisions.

## 13. Required changes for model Packages

Package developers should assume the following changes from the current
`omlx.model_adapters` entry-point model:

1. Package entry points are discovered and imported only inside the Worker.
2. `match`, `prepare`, and `load` run inside the Worker.
3. Package code cannot monkey-patch Host modules or process-global Host state.
4. Any process-global MLX/oMLX patch applies only to that Package Worker.
5. The loaded model and tokenizer/processor remain in the Worker.
6. Inference is invoked through the model-worker protocol rather than a Host
   Python method call.
7. Package code must not call Hugging Face or arbitrary HTTP clients directly.
8. Package code receives authorized filesystem handles/paths rather than
   discovering the user's home directory.
9. Spawning child processes is prohibited unless a future reviewed capability
   explicitly permits it.
10. Native libraries must be compatible with the signed Worker, Hardened
    Runtime, App Sandbox, Python ABI, MLX ABI, and Apple Silicon architecture.

Static catalog metadata and checkpoint recipes should be moved out of
executable entry points where practical, so the Host can display and validate
them without executing Package code.

## 14. Lifecycle, updates, and failure handling

- Verify Package signature/digest before launch.
- Pin each launch to one immutable package digest and version.
- Create a fresh authenticated Worker session for that identity.
- Grant only the resources selected for that session.
- Do not hot-swap Package code inside a running Worker.
- Start the new version in a new Worker and drain or terminate the old version.
- Revoke resource grants and network grants when appropriate on uninstall.
- Kill only the affected Worker on crash, protocol violation, timeout, or
  repeated health-check failure.
- Attribute logs, metrics, memory, requests, and crashes to Package digest.
- Never include Host secrets in Worker crash reports.

The supervisor should enforce request concurrency, wall-clock time, disk quota,
and CPU/RSS limits where macOS APIs permit. GPU/unified-memory accounting must
be measured and enforced by the Host admission controller; App Sandbox alone
does not provide a complete per-Worker Metal memory quota.

## 15. Questions for model Package developers

Please answer these for every existing Package:

1. Does the adapter modify oMLX/MLX process-global state? List every patch,
   registry mutation, environment variable, and global flag.
2. Can the entire model load and generation loop run in a dedicated process?
3. Which Host Python objects are currently passed into or returned from
   `match`, `prepare`, and `load`?
4. What must replace those objects in a data-only RPC schema?
5. Does the Package need direct access to Hugging Face, another Internet host,
   or localhost? Why can the Host downloader/Broker not perform that operation?
6. Which exact directories are read and written during discovery, preparation,
   load, inference, cache replacement, and unload?
7. Does it create files next to model weights, or can all mutable state move to
   Package-private data/cache?
8. Does it spawn subprocesses, use shared memory, open sockets, or use memory-
   mapped files?
9. Which native libraries, MLX features, Metal capabilities, JIT behavior, or
   Hardened Runtime exceptions are required?
10. What startup latency and steady-state throughput regression results from
    Worker startup and RPC streaming?
11. Can cancellation and Worker termination leave model/cache files corrupt?
12. Does the Package require sharing one loaded model with another Package?
    If so, describe the requirement without assuming a shared interpreter.

Any requested exception must identify the minimum capability, justification,
affected model, expected duration, and a safer alternative that was evaluated.

## 16. Feasibility and performance validation

Each reference model Package should report the following comparison using
identical prompts and generated tokens:

- model discovery result and selected adapter;
- output parity appropriate to the model and sampler configuration;
- cold Worker launch time;
- cold model load time;
- first-token latency;
- steady-state tokens per second;
- Host RSS and Worker RSS;
- total physical/unified memory;
- IPC CPU overhead and bytes per generated token;
- cancellation latency;
- behavior after Worker crash and restart;
- model Cache read/write behavior under the proposed filesystem grants.

The first implementation should validate at least one standard dense model,
one VLM, one custom-quantized model, and one Cached-MoE model before removing
the legacy in-process adapter path.

## 17. Security acceptance tests

A non-built-in test Package must be unable to:

1. import or execute code in the Host process;
2. query, update, or delete Host Keychain items;
3. invoke `SecretBackend` or obtain provider keys through RPC;
4. read the Host database, configuration, logs, or another Package directory;
5. write its immutable payload or read an unassigned model checkpoint;
6. connect directly to the Internet, LAN, loopback TCP service, or Unix socket;
7. bypass the Broker through DNS rebinding, redirects, alternate IP formats, or
   an unapproved port;
8. retain file or network access after its capability is revoked;
9. impersonate another Package over RPC;
10. crash or monkey-patch the Host when its own process fails.

Positive tests must also prove that an authorized Package can read its payload,
read its selected model, write its private cache, use Metal, stream generation,
cancel a request, and perform an explicitly approved Broker request.

## 18. Same-device Local Installation isolation design

### 18.1 Installation identity is the primary tenant key

Every initialized instance receives one immutable, non-secret Local security
identity before Cloud enrollment. The implementation stores it as
`local_security_identity.security_instance_id`; it is the namespace and Cookie
audience even while the instance is unbound. Cloud enrollment later binds one
Cloud `installation_id` and Core authority to that Local identity. Neither ID
is derived from a filesystem path, TCP port, process ID, model ID, or
user-visible label, and rebinding must not silently replace either authority.

The following objects are Installation-scoped:

- Core binding, Member projection, membership epoch, and local login sessions;
- provider credentials and SecretBackend references;
- API client credentials and refresh tokens;
- Package installations, grants, Sandboxes, and private data;
- Agent, Tool, Service, browser, project, and document capabilities;
- Trust Center decisions and audit events;
- upstream, downstream, remote-access, and federation credentials;
- model configuration and runtime state where sharing was not explicitly
  authorized.

Database queries for these records must either include `installation_id` in
their key or operate on a database that is itself opened only for one immutable
Installation. Request-context identity still carries `installation_id` so a
misrouted request fails closed rather than relying only on the selected file.

### 18.2 Core user, enrollment, login, and logout

Core ownership belongs to an Installation, not automatically to a physical
device. Each instance follows this flow independently:

1. If the instance has no Core binding, its WebUI presents first-run setup and
   requires the user to log in or register with AI2Apps Cloud.
2. After authentication, the user explicitly confirms binding that Cloud
   account and device instance as the Installation's Core user.
3. Once bound, ordinary visits present the same login flow to Core and Member
   users; authorization after login determines the visible Apps and actions.
4. Logging out of the Account App revokes the current instance's local session
   immediately and redirects that WebUI to its login entry.
5. Login or logout in Installation A does not create, revoke, or refresh a
   session in Installation B.

The same Cloud user may explicitly become Core of several Installations, but
Core status and policy are not inherited between them. V1 does not include a
fully offline Core-enrollment path.

### 18.3 Browser origin and cookie isolation

Using different loopback ports is insufficient because HTTP cookies are not
port-scoped. The minimum compatible change is:

- derive an instance-specific cookie name such as
  `ai2apps_session_<installation_short_id>`;
- include `installation_id`, session ID, and session epoch in the signed or
  server-side session state;
- reject a validly signed session whose Installation audience differs from the
  receiving Host;
- use host-only, `HttpOnly`, `SameSite=Strict`, and `Secure` cookies whenever
  the local transport supports HTTPS;
- never set a broad `Domain=.localhost` cookie.

The preferred product origin is a stable per-instance loopback hostname such
as `<instance-short-id>.localhost`, optionally behind one trusted local gateway.
Unique cookie names remain defense in depth. `localStorage`, IndexedDB, service
workers, CSRF origin checks, OAuth callbacks, and WebAuthn relying-party IDs
must be reviewed against the selected origin scheme.

Legacy `omlx_admin_session` authentication must be removed from user-facing
flows after migration rather than operating as a second, instance-agnostic
login system.

### 18.4 Secret and Keychain isolation

Every secret reference must be based on the stable Installation identity, for
example:

```text
ai2apps.v1.<installation_id>.<secret_kind>.<opaque_secret_id>
```

This namespace prevents collisions and supports audit and migration, but is
not by itself an authorization boundary. Production secret access follows
these rules:

1. Only the trusted Host/Secret Broker receives the Host Keychain access group.
2. Package Workers and other untrusted runtime processes cannot link to or call
   the Python `SecretBackend` implementation.
3. Broker requests are authenticated by the IPC connection and carry the
   Installation context established at launch; a caller-supplied
   `installation_id` is not trusted.
4. Broker ACLs bind secret ID, Installation, caller class/identity, operation,
   optional provider/origin, and expiry.
5. Prefer credential use without disclosure: the Broker or trusted provider
   service performs the authorized remote operation instead of returning the
   long-lived OpenAI or other provider key to a Worker.
6. Secret values never enter command-line arguments, environment variables,
   logs, trace events, crash metadata, browser storage, or Package-readable
   temporary files.
7. Cross-instance credential sharing is off by default. A future share action
   is an explicit Core-approved grant or secret copy, with independent
   revocation and an audit event.

Because arbitrary instances of the same signed app cannot practically receive
dynamically unique Keychain access groups, a shared trusted Broker is the
recommended application architecture. If the threat model requires protection
after one entire Host is compromised, deploy the instances under separate
macOS users, App Containers with separately designed entitlements, or virtual
machines.

### 18.5 API, IPC, localhost, and remote identity

An API token that is valid in one instance must fail in another. Tokens and
capabilities include at least:

- `iss` identifying the issuing component;
- `aud` equal to the target `installation_id` and service;
- actor or Package identity;
- scopes/capabilities;
- issued, expiry, and revocation epochs;
- a nonce or token identifier where replay protection is required.

Each Host uses unique listen endpoints. Possession of an open localhost port is
not authorization. Package Workers cannot scan or call loopback services
directly; they use authenticated IPC or the Network Broker. Remote access,
federation, and Cloud callbacks verify the target Installation on every hop.

The legacy main API key must not be the WebUI login credential. If retained for
OpenAI-compatible automation during migration, it is generated independently
per Installation, audience-bound at verification, revocable, and stored like
another privileged client credential rather than embedded in frontend state.

### 18.6 Files, browser profiles, and runtime resources

Every instance must have a distinct canonical data root. Startup fails closed
if two concurrently active instances resolve to the same root, database, or
browser profile. Symlinks and aliases are resolved before the ownership check.

Package Workers receive only resource handles belonging to their Installation
and Package. A raw path supplied by a Package is never sufficient authority.
Browser-control sessions, downloads, screenshots, attachment extraction,
generated documents, model conversion scratch space, and logs follow the same
rule.

The Host may support an explicit read-only shared model-weight cache because
model artifacts are large. Such a cache contains only verified non-secret
artifacts; mutable model state, scope/cache policy, conversation state, and
credentials remain per Installation. Writes and conversion are performed by a
trusted cache manager using immutable digest-addressed outputs.

For Model Worker v1, sharing means repository-scoped read grants selected from
Host-validated static declarations. It does not mean that a Worker receives a
read grant for the shared cache root. Preparation recipes are data interpreted
by trusted Host code; importing Package preparation code into the Host remains
forbidden.

Cached-MoE preparation follows this rule as well. The active signed Worker
manifest declares the pinned source, storage policies, conversion identifier,
memory tiers, and Package-relative Scope Pack assets. The Host resolves and
checks those assets inside the immutable Package payload before its built-in
converter runs. Installing, upgrading, disabling, or removing the Package
immediately changes the available recipe set; no Package `prepare()` or Python
entry point is imported by the Host.

Per-model execution mode and memory tier remain Host-owned settings. The Host
overwrites a reserved field on its authenticated loopback request, and the
Worker uses it only to select an engine for the next serialized request. A
public API caller cannot use that field to bypass Model Config policy.

### 18.7 Multi-instance security acceptance tests

The release gate starts Installation A and Installation B under the same macOS
user with different roots, ports, Core bindings, provider keys, Packages, and
browser profiles. It must prove that:

1. A's browser session is rejected by B and B's session is rejected by A;
2. logging out of A does not revoke B, while A immediately returns to login;
3. an API client token issued by A receives an authorization failure from B;
4. A cannot load, update, use, or delete B's provider and federation secrets;
5. a Package Worker in A cannot read B's database, files, Package data,
   browser profile, Unix sockets, or localhost API;
6. Trust grants in A have no effect in B;
7. the same provider ID configured in both instances resolves to different
   credentials;
8. Core and Member policy changes in A do not alter B's local projection;
9. remote and Cloud callbacks addressed to A cannot be replayed against B;
10. shared model artifacts, when enabled, expose no secret or mutable
    instance-owned data.

Negative tests should know the other instance's path, port, Installation ID,
and Keychain account names. Security must not depend on those values remaining
hidden.

## 19. System security upgrade development plan

The upgrade is staged so that identity and secret semantics are established
before Package Workers depend on them. Each phase has a feature flag, schema
migration, downgrade policy, and release-gate tests. Security migrations must
be restart-safe and must never delete the old credential until the new record
has been written and read back successfully.

Current phase tracking:

| Phase | State | Notes |
|---|---|---|
| 0 | Implemented | Stable identity, root lease/clone claim, redaction and fail-closed installed adapters |
| 1 | Implemented | Core/Member account login, scoped cookies, logout, no Web API-key login |
| 2 | Partially implemented | Namespaced backend, provider migration, injection audit and Trust visibility; signed Host-only Broker/access group remains |
| 3 | Python Worker baseline implemented | System-owned Model Worker v1, Adapter lifecycle, sandbox, ephemeral authentication and routing exist; signed XPC transport remains pending |
| 4 | Partially implemented | Scoped roots, repository-scoped Model Worker weight grants, managed Service/Process sandbox and isolated browser profiles exist; per-origin Network Broker remains |
| 5 | Pending | Worker model ports, packaged entitlement audit, malicious-Package suite and performance evidence |

### Phase 0 - inventory and immediate containment

1. Introduce one immutable `installation_id` service at the composition root
   and remove path-, port-, and process-derived security identities.
2. Inventory every credential, cookie, token, database table, local endpoint,
   browser profile, Package path, and RPC message that requires Installation
   scope.
3. Reject concurrent startup with the same canonical data root or browser
   profile; allocate unique ports/endpoints.
4. Keep installable Services denied from `in_process` execution and mark the
   model-adapter Host-import path as an explicit temporary high-risk legacy
   mode.
5. Add redaction tests so no provider key, session token, or main API key is
   emitted through logs, diagnostics, Tool output, or crash reports.

Exit criterion: the inventory is complete, two instances can run without
sharing directories, and known legacy risks are visible in Trust Center.

### Phase 1 - instance-aware identity and Web authentication

1. Implement first-run Core enrollment and the unified Core/Member login flow.
2. Replace fixed cookie names with instance-specific names and bind every
   session to `installation_id` and revocation epochs.
3. Make Account logout revoke the current instance and force its WebUI to the
   login entry without affecting other instances.
4. Add `aud=installation_id` validation to API client tokens, Cloud callbacks,
   upstream/downstream links, and remote access.
5. Remove the main API key from WebUI authentication and frontend storage;
   retain a compatibility path only for explicitly created API clients.

Exit criterion: all multi-instance session and token acceptance tests pass,
and no user-facing WebUI flow depends on the legacy main API key.

### Phase 2 - Secret Broker and credential migration

1. Add versioned, Installation-scoped secret references based on
   `installation_id` rather than `base_path` hashes.
2. Build the authenticated Host-only Secret Broker and define its minimal ACL
   and audit schema.
3. Migrate provider, Cloud session, upstream/downstream, remote, and federation
   credentials using copy, read-back verification, reference swap, and delayed
   cleanup.
4. Route authorized provider use through a trusted provider/Broker operation so
   Workers do not receive long-lived keys.
5. Add a Trust Center view showing secret owner Installation, consumer,
   purpose, last use, and revocation without revealing the value.

Exit criterion: no untrusted process can call Keychain/SecretBackend directly,
and the adversarial cross-instance secret tests pass.

### Phase 3 - Package Worker and model-worker boundary

1. Define and enforce the built-in versus installed-Package invariant.
2. Build and sign the minimal Package Runner/XPC target with no Keychain or
   direct-network entitlement.
3. Define the model-worker protocol and move one small reference model into it. The Python Worker v1 protocol and reference Package are implemented; migration of a production model remains.
4. Move adapter discovery, import, model loading, tokenizer/processor, MLX
   state, and inference into the Worker.
5. Delete Host `sys.path` insertion and installed entry-point import after the
   supported Packages have migrated.

Exit criterion: an installed wheel cannot execute code in the Host, and Host
restart no longer imports installed adapter modules.

### Phase 4 - resource and network capabilities

1. Add Installation- and Package-scoped filesystem/resource grants.
2. Add the deny-by-default Network Broker and audited origin grants.
3. Move model download, verification, conversion, and shared-artifact cache
   ownership into trusted Host services.
4. Isolate browser profiles and browser-control sessions; mediate user document
   and attachment access through explicit capabilities.
5. Add cancellation, quotas, crash containment, grant revocation, and Worker
   lifecycle accounting.

Exit criterion: the negative Package tests in section 17 and the multi-instance
tests in section 18.7 pass under the packaged macOS application.

### Phase 5 - model migration and release hardening

1. Port Qwen3.8, DeepSeek V4 Flash, DeepSeek V4 Flash 2-bit, Qwen3.6 Cached-MoE,
   one VLM, and one dense reference model.
2. Record output parity, launch/load time, TTFT, steady TPS, Host/Worker RSS,
   total unified memory, IPC overhead, cancellation, and recovery behavior.
3. Add malicious reference Packages that probe Keychain, filesystem, loopback,
   Broker redirects/DNS rebinding, RPC impersonation, and resource cleanup.
4. Test clean install, upgrade from the current release, interrupted migration,
   rollback before credential cleanup, Package upgrade, and uninstall.
5. Make the security suite, entitlements audit, dependency/SBOM scan, and
   multi-instance suite mandatory release checks.

Exit criterion: the legacy in-process adapter mode and instance-agnostic
authentication are disabled in production builds. Until then, the product must
not describe installed model adapters as sandboxed or same-user Local instances
as strongly isolated.

## 20. Migration and compatibility rules

- Existing single-instance roots receive an `installation_id` before any
  credential, cookie, or database migration begins.
- Old and new credential references may be read during a bounded migration
  window, but all new writes use the new versioned namespace.
- A migration journal records prepare, copy, verify, switch, and cleanup states
  without storing secret values.
- Cleanup of legacy Keychain items occurs only after a successful release soak
  period and must be separately reversible from database rollback.
- Old cookies are never reinterpreted as another instance's authenticated
  session. They may only initiate a fresh login or a tightly bounded migration
  exchange in the same Installation.
- API compatibility clients must explicitly select one Installation endpoint;
  no token is silently accepted across instances.
- Shared model files are optional optimizations and must not become a channel
  for sharing credentials, mutable cache policy, conversation state, or Core
  identity.
- Development mode may relax publisher-signature requirements, but it does not
  relax Host-process, secret, cross-instance, or network isolation invariants.
