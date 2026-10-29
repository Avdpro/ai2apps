# Web Reader

AI Browser Mini-App source Package with two independent capabilities: extract SJX links and read an SJX article.
The fixed UI submits durable background Tasks through the host-owned SDK.

See [the contract](../../docs/ai2apps-web-agent-mini-app-package-contract-v1.md).
Develop using the fixed App-Dev source mount; source is not a published signed Package.


## AaAT ownership (0.1.2)

This release owns its executable AaAT declarations and parameter schemas in signed `app.yaml.mini_apps[].aaat`. It requires the versioned native Host SDK protocol declared by each export (`ai2apps.mini-app-host-exports/v1`). The matching Desktop host registers exports only while this exact Package is installed, enabled, and compatible. The capability catalog alone never enables execution. Older Desktop hosts must be upgraded for this ownership contract. Existing native queues, original material references, and shared Studio Output are reused.
