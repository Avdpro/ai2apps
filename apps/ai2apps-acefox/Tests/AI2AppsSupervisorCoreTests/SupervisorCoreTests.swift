import AI2AppsContracts
import Foundation
import Testing
@testable import AI2AppsSupervisorCore

private func instanceID(_ value: String = "default") throws -> InstanceID {
    try InstanceID(rawValue: value)
}

@Test func launchPlanUsesZeroForAutomaticPort() throws {
    let id = try instanceID()
    let paths = InstancePaths(instanceID: id, homeDirectory: URL(fileURLWithPath: "/Users/test"))
    let plan = try LocalLaunchPlan(
        executable: URL(fileURLWithPath: "/Applications/AI2Apps.app/Contents/Library/Helpers/AI2AppsHost"),
        instanceID: id,
        configuration: LocalConfiguration(),
        paths: paths,
        bootID: UUID(uuidString: "F1C8724A-38E7-49D5-9F08-D46FF4D890A9")!
    )

    #expect(plan.arguments.contains("0"))
    #expect(plan.environment["AI2APPS_INSTANCE_ID"] == "default")
    #expect(plan.environment["AI2APPS_SUPERVISED"] == "helper")
    #expect(plan.environment["HF_HUB_CACHE"] == "/Users/test/Library/Caches/AI2Apps/instances/default/model-weights/huggingface/hub")
    #expect(plan.environment["AI2APPS_MODEL_CACHE_ROOT"] == "/Users/test/Library/Caches/AI2Apps/instances/default/model-weights")
    #expect(plan.environment["AI2APPS_MODEL_CACHE_MODE"] == "isolated")
    #expect(plan.runDescriptorURL.path.hasSuffix("/run/local.json"))
}

@Test func launchPlanOverridesInheritedHubCacheWithoutSharingHome() throws {
    let id = try instanceID("customer-a")
    let paths = InstancePaths(instanceID: id, homeDirectory: URL(fileURLWithPath: "/Users/test"))
    let plan = try LocalLaunchPlan(
        executable: URL(fileURLWithPath: "/usr/bin/true"),
        instanceID: id,
        configuration: LocalConfiguration(),
        paths: paths,
        inheritedEnvironment: [
            "HF_HOME": "/Users/test/.cache/huggingface",
            "HF_HUB_CACHE": "/tmp/untrusted-hub",
            "HF_TOKEN": "must-not-leak",
            "HUGGING_FACE_HUB_TOKEN": "must-not-leak-either",
            "TRANSFORMERS_CACHE": "/tmp/untrusted-transformers",
            "HOME": "/Users/test",
        ]
    )

    #expect(plan.environment["HF_HOME"] == paths.instanceHuggingFaceHomeDirectory.path)
    #expect(plan.environment["HF_TOKEN_PATH"] == paths.instanceHuggingFaceHomeDirectory.appendingPathComponent("token").path)
    #expect(plan.environment["HF_HUB_CACHE"] == paths.instanceHuggingFaceHubDirectory.path)
    #expect(plan.environment["HF_TOKEN"] == nil)
    #expect(plan.environment["HUGGING_FACE_HUB_TOKEN"] == nil)
    #expect(plan.environment["TRANSFORMERS_CACHE"] == nil)
    #expect(plan.environment["HOME"] == "/Users/test")
    #expect(plan.arguments.contains(paths.dataDirectory.path))
}

@Test func twoInstancesKeepAllRuntimeAndModelStorageSeparate() throws {
    let home = URL(fileURLWithPath: "/Users/test")
    let firstID = try instanceID("customer-a")
    let secondID = try instanceID("customer-b")
    let firstPaths = InstancePaths(instanceID: firstID, homeDirectory: home)
    let secondPaths = InstancePaths(instanceID: secondID, homeDirectory: home)
    let configuration = LocalConfiguration()
    let executable = URL(fileURLWithPath: "/usr/bin/true")
    let first = try LocalLaunchPlan(
        executable: executable,
        instanceID: firstID,
        configuration: configuration,
        paths: firstPaths
    )
    let second = try LocalLaunchPlan(
        executable: executable,
        instanceID: secondID,
        configuration: configuration,
        paths: secondPaths
    )

    #expect(first.environment["AI2APPS_INSTANCE_ID"] == "customer-a")
    #expect(second.environment["AI2APPS_INSTANCE_ID"] == "customer-b")
    #expect(first.environment["AI2APPS_RUN_DESCRIPTOR_PATH"] != second.environment["AI2APPS_RUN_DESCRIPTOR_PATH"])
    #expect(first.environment["HF_HOME"] != second.environment["HF_HOME"])
    #expect(first.environment["HF_TOKEN_PATH"] != second.environment["HF_TOKEN_PATH"])
    #expect(first.environment["HF_HUB_CACHE"] != second.environment["HF_HUB_CACHE"])
    #expect(first.environment["AI2APPS_MODEL_CACHE_ROOT"] != second.environment["AI2APPS_MODEL_CACHE_ROOT"])
    #expect(first.environment["AI2APPS_MODEL_CACHE_MODE"] == "isolated")
    #expect(second.environment["AI2APPS_MODEL_CACHE_MODE"] == "isolated")
    #expect(first.arguments.contains(firstPaths.dataDirectory.path))
    #expect(!first.arguments.contains(secondPaths.dataDirectory.path))
    #expect(second.arguments.contains(secondPaths.dataDirectory.path))
    #expect(!second.arguments.contains(firstPaths.dataDirectory.path))
    #expect(first.arguments.suffix(6).contains("0"))
    #expect(second.arguments.suffix(6).contains("0"))
}

@Test func launchPlanUsesConfiguredFixedPort() throws {
    let id = try instanceID()
    let paths = InstancePaths(instanceID: id, homeDirectory: URL(fileURLWithPath: "/Users/test"))
    let plan = try LocalLaunchPlan(
        executable: URL(fileURLWithPath: "/usr/bin/true"),
        instanceID: id,
        configuration: LocalConfiguration(portMode: .fixed, configuredPort: 18_431),
        paths: paths
    )
    let portIndex = try #require(plan.arguments.firstIndex(of: "--port"))
    #expect(plan.arguments[plan.arguments.index(after: portIndex)] == "18431")
}

@Test func automaticModeDoesNotProbeOrReserveAPort() throws {
    let conflict = try LoopbackPortInspector().conflict(for: LocalConfiguration())
    #expect(conflict == nil)
}

@Test func lifecycleReachesReadyForMatchingInstanceAndBoot() throws {
    let id = try instanceID()
    let bootID = UUID()
    var state: SupervisorState = .stopped
    state = try SupervisorReducer.reduce(state: state, event: .requestStart(bootID: bootID), expectedInstanceID: id)
    state = try SupervisorReducer.reduce(state: state, event: .runtimeValidated(bootID: bootID), expectedInstanceID: id)
    state = try SupervisorReducer.reduce(state: state, event: .processSpawned(processID: 42, bootID: bootID), expectedInstanceID: id)
    let descriptor = LocalRunDescriptor(
        instanceID: id,
        processID: 42,
        configuredPort: 18_431,
        actualPort: 18_431,
        bootID: bootID,
        runtimeVersion: "1.0.0",
        startedAt: Date()
    )
    state = try SupervisorReducer.reduce(state: state, event: .localReady(descriptor), expectedInstanceID: id)

    guard case .ready(let local) = state else {
        Issue.record("expected ready state")
        return
    }
    #expect(local.origin.absoluteString == "http://127.0.0.1:18431")
}

@Test func lifecycleRejectsStaleBootID() throws {
    let id = try instanceID()
    let state: SupervisorState = .validatingRuntime(bootID: UUID())
    #expect(throws: SupervisorTransitionError.staleBootID) {
        try SupervisorReducer.reduce(
            state: state,
            event: .runtimeValidated(bootID: UUID()),
            expectedInstanceID: id
        )
    }
}

@Test func lifecycleRejectsAnotherInstanceDescriptor() throws {
    let expected = try instanceID("customer-a")
    let actual = try instanceID("customer-b")
    let bootID = UUID()
    let state: SupervisorState = .migrating(processID: 42, bootID: bootID)
    let descriptor = LocalRunDescriptor(
        instanceID: actual,
        processID: 42,
        configuredPort: nil,
        actualPort: 49_152,
        bootID: bootID,
        runtimeVersion: "1.0.0",
        startedAt: Date()
    )
    #expect(throws: ContractError.self) {
        try SupervisorReducer.reduce(
            state: state,
            event: .localReady(descriptor),
            expectedInstanceID: expected
        )
    }
}

@Test func explicitStopDoesNotEnterRestartFailure() throws {
    let id = try instanceID()
    let bootID = UUID()
    let descriptor = LocalRunDescriptor(
        instanceID: id,
        processID: 42,
        configuredPort: 18_431,
        actualPort: 18_431,
        bootID: bootID,
        runtimeVersion: "1.0.0",
        startedAt: Date()
    )
    let ready: SupervisorState = .ready(ReadyLocal(descriptor: descriptor))
    let stopping = try SupervisorReducer.reduce(state: ready, event: .requestStop, expectedInstanceID: id)
    let stopped = try SupervisorReducer.reduce(state: stopping, event: .stopCompleted, expectedInstanceID: id)
    #expect(stopped == .stopped)
}
