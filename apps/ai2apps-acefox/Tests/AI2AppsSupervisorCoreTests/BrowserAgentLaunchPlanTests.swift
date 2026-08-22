import AI2AppsContracts
import AI2AppsSupervisorCore
import Foundation
import Testing

@Test func browserAgentProfileIsStableAndSeparatedFromShell() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let paths = InstancePaths(instanceID: instanceID, homeDirectory: URL(fileURLWithPath: "/Users/test"))
    let first = try BrowserAgentLaunchPlan(
        executable: URL(fileURLWithPath: "/Applications/Acefox.app/Contents/MacOS/firefox"),
        instanceID: instanceID,
        actorUserID: "user-123",
        paths: paths
    )
    let second = try BrowserAgentLaunchPlan(
        executable: first.executable,
        instanceID: instanceID,
        actorUserID: "user-123",
        paths: paths
    )

    #expect(first.profileDirectory == second.profileDirectory)
    #expect(first.profileDirectory.path.contains("/browser-profiles/agents/"))
    #expect(!first.profileDirectory.path.hasSuffix("/app-shell"))
    #expect(first.environment["AI2APPS_BROWSER_ROLE"] == "agent")
    #expect(first.environment["MOZ_APP_NO_DOCK"] == "1")
}

@Test func browserAgentProfilesDifferAcrossUsersAndInstances() throws {
    let firstInstance = try InstanceID(rawValue: "customer-a")
    let secondInstance = try InstanceID(rawValue: "customer-b")
    let first = try BrowserAgentProfileID.derive(instanceID: firstInstance, actorUserID: "user-123")
    let otherUser = try BrowserAgentProfileID.derive(instanceID: firstInstance, actorUserID: "user-456")
    let otherInstance = try BrowserAgentProfileID.derive(instanceID: secondInstance, actorUserID: "user-123")

    #expect(first != otherUser)
    #expect(first != otherInstance)
}

@Test func browserAgentAutomationIsLoopbackAndAuthenticated() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let paths = InstancePaths(
        instanceID: instanceID,
        homeDirectory: URL(fileURLWithPath: "/Users/test")
    )
    let token = String(repeating: "a", count: 64)
    let plan = try BrowserAgentLaunchPlan(
        executable: URL(fileURLWithPath: "/Applications/Acefox.app/Contents/MacOS/firefox"),
        instanceID: instanceID,
        actorUserID: "user-123",
        paths: paths,
        automation: BrowserAgentAutomation(port: 49152, token: token)
    )

    #expect(plan.arguments.contains("--remote-debugging-port"))
    #expect(plan.arguments.contains("49152"))
    #expect(plan.arguments.contains("--remote-allow-hosts"))
    #expect(plan.environment["AI2APPS_REMOTE_AGENT_TOKEN"] == token)
}

@Test func browserAgentAutomationRejectsWeakCredentials() throws {
    #expect(throws: ContractError.self) {
        try BrowserAgentAutomation(port: 80, token: "weak").validate()
    }
}

@Test func browserAgentDoesNotInheritHelperOrModelCredentials() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let paths = InstancePaths(
        instanceID: instanceID,
        homeDirectory: URL(fileURLWithPath: "/Users/test")
    )
    let plan = try BrowserAgentLaunchPlan(
        executable: URL(fileURLWithPath: "/Applications/Acefox.app/Contents/MacOS/firefox"),
        instanceID: instanceID,
        actorUserID: "user-123",
        paths: paths,
        inheritedEnvironment: [
            "HOME": "/Users/test",
            "PATH": "/usr/bin:/bin",
            "AI2APPS_HELPER_TOKEN": "helper-secret",
            "HF_TOKEN": "model-secret",
            "OPENAI_API_KEY": "provider-secret",
        ]
    )

    #expect(plan.environment["HOME"] == "/Users/test")
    #expect(plan.environment["PATH"] == "/usr/bin:/bin")
    #expect(plan.environment["AI2APPS_HELPER_TOKEN"] == nil)
    #expect(plan.environment["HF_TOKEN"] == nil)
    #expect(plan.environment["OPENAI_API_KEY"] == nil)
}
