# Trip Planner

Single-destination, round-trip research for AI Browser Desktop/Mobile. Owner contract: ai2apps/docs/trip-planner-mini-app.md. All work uses existing Browser Tasks and shared task model routing. No reservations or payments.


## AaAT ownership (0.1.2)

This release owns its executable AaAT declarations and parameter schemas in signed `app.yaml.mini_apps[].aaat`. It requires the versioned native Host SDK protocol declared by each export (`ai2apps.mini-app-host-exports/v1`). The matching Desktop host registers exports only while this exact Package is installed, enabled, and compatible. The capability catalog alone never enables execution. Older Desktop hosts must be upgraded for this ownership contract. Existing native queues, original material references, and shared Studio Output are reused.
