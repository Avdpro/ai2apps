import Testing
@testable import AI2AppsSupervisorCore

@Test func shellHostRenderingDoesNotDependOnLaunchOrder() {
    let inherited = ["AI2APPS_BACKGROUND_HOST": "0", "AI2APPS_BROWSER_ROLE": "browser", "UNCHANGED": "value"]
    let merged = inherited.merging(ShellHostEnvironment.required(token: "test-only-token")) { _, required in required }
    #expect(merged["AI2APPS_BACKGROUND_HOST"] == "1")
    #expect(merged["AI2APPS_BROWSER_ROLE"] == "shell")
    #expect(merged["AI2APPS_APP_SHELL"] == "1")
    #expect(merged["AI2APPS_DISABLE_REMOTE_SERVER"] == "1")
    #expect(merged["AI2APPS_REMOTE_AGENT_TOKEN"] == "test-only-token")
    #expect(merged["UNCHANGED"] == "value")
}

@Test func interactiveShellRetainsRenderingWithoutStartingHidden() {
    let environment = ShellHostEnvironment.required(token: "test", showShell: true)
    #expect(environment["AI2APPS_BACKGROUND_HOST"] == "1")
    #expect(environment["AI2APPS_SHOW_SHELL"] == "1")
    #expect(ShellHostEnvironment.required(token: "test")["AI2APPS_SHOW_SHELL"] == "0")
}
