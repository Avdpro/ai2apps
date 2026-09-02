import Foundation
import Testing
@testable import AI2AppsContracts

@Test func automaticPortConfigurationIsValid() throws {
    let config = LocalConfiguration()
    try config.validate()
    #expect(config.launchPort == 0)
}

@Test func fixedPortConfigurationIsValid() throws {
    let config = LocalConfiguration(portMode: .fixed, configuredPort: 18_431)
    try config.validate()
    #expect(config.launchPort == 18_431)
}

@Test func automaticModeRejectsConfiguredPort() {
    let config = LocalConfiguration(portMode: .automatic, configuredPort: 18_431)
    #expect(throws: ContractError.self) { try config.validate() }
}

@Test func fixedModeRejectsPrivilegedPort() {
    let config = LocalConfiguration(portMode: .fixed, configuredPort: 443)
    #expect(throws: ContractError.self) { try config.validate() }
}

@Test func wildcardBindingIsRejected() {
    let config = LocalConfiguration(bindAddress: "0.0.0.0")
    #expect(throws: ContractError.self) { try config.validate() }
}

@Test func instanceIDRejectsPathTraversalAndUppercase() {
    #expect(throws: ContractError.self) { try InstanceID(rawValue: "../customer") }
    #expect(throws: ContractError.self) { try InstanceID(rawValue: "Customer-A") }
    #expect(throws: ContractError.self) { try InstanceID(rawValue: "customer/a") }
}

@Test func instancePathsStayWithinInstanceRoot() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let home = URL(fileURLWithPath: "/Users/test", isDirectory: true)
    let paths = InstancePaths(instanceID: instanceID, homeDirectory: home)
    #expect(paths.runDirectory.path == "/Users/test/Library/Application Support/AI2Apps/instances/customer-a/run")
    #expect(paths.browserProfilesDirectory.path.hasPrefix(paths.supportRoot.path))
    #expect(paths.instanceHuggingFaceHubDirectory.path == "/Users/test/Library/Caches/AI2Apps/instances/customer-a/model-weights/huggingface/hub")
}

@Test func instancesNeverShareModelStoragePaths() throws {
    let home = URL(fileURLWithPath: "/Users/test", isDirectory: true)
    let first = InstancePaths(instanceID: try InstanceID(rawValue: "customer-a"), homeDirectory: home)
    let second = InstancePaths(instanceID: try InstanceID(rawValue: "customer-b"), homeDirectory: home)

    #expect(first.instanceModelWeightsDirectory != second.instanceModelWeightsDirectory)
    #expect(first.instanceHuggingFaceHubDirectory != second.instanceHuggingFaceHubDirectory)
    #expect(first.instanceHuggingFaceHomeDirectory != second.instanceHuggingFaceHomeDirectory)
    #expect(first.dataDirectory != second.dataDirectory)
    #expect(first.cacheRoot != second.cacheRoot)
    #expect(first.browserProfilesDirectory != second.browserProfilesDirectory)
}

@Test func sandboxContainersRelocateEveryInstancePath() throws {
    let container = URL(fileURLWithPath: "/Users/test/Library/Group Containers/team.instance")
    let paths = InstancePaths(
        instanceID: try InstanceID(rawValue: "customer-a"),
        homeDirectory: URL(fileURLWithPath: "/Users/test"),
        containerDirectory: container
    )

    #expect(paths.isContainerBacked)
    #expect(paths.supportRoot.path.hasPrefix(container.path + "/"))
    #expect(paths.cacheRoot.path.hasPrefix(container.path + "/"))
    #expect(!paths.supportRoot.path.contains("/Users/test/Library/Application Support/"))
}

@Test func localConfigurationHasNoFilesystemSharingMode() throws {
    let legacy = Data("""
    {
      "auto_restart": true,
      "bind_address": "127.0.0.1",
      "port_mode": "automatic",
      "schema_version": 1,
      "start_at_login": true,
      "model_cache_mode": "shared"
    }
    """.utf8)
    let configuration = try JSONDecoder().decode(LocalConfiguration.self, from: legacy)

    try configuration.validate()
    let encoded = String(decoding: try JSONEncoder().encode(configuration), as: UTF8.self)
    #expect(!encoded.contains("model_cache_mode"))
}

@Test func instanceDirectoriesAreOwnerOnly() throws {
    let instanceID = try InstanceID(rawValue: "private-instance")
    let home = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    let paths = InstancePaths(instanceID: instanceID, homeDirectory: home)

    try paths.preparePrivateDirectories()
    for directory in paths.privateDirectories {
        let attributes = try FileManager.default.attributesOfItem(
            atPath: directory.path
        )
        let permissions = attributes[.posixPermissions] as? NSNumber
        #expect(permissions?.intValue == 0o700)
    }

    try? FileManager.default.removeItem(at: home)
}

@Test func diagnosticSnapshotContainsOnlyBoundedOperationalMetadata() throws {
    let snapshot = DiagnosticSnapshot(
        generatedAt: Date(timeIntervalSince1970: 1_234),
        instanceID: try InstanceID(rawValue: "customer-a"),
        productVersion: "153.0.4",
        runtimeVersion: "0.1.0.dev3",
        operatingSystem: "macOS 26.0",
        architecture: "arm64",
        helperPhase: .ready,
        helperProcessID: 42,
        localProcessID: 43,
        localBootID: UUID(uuidString: "00000000-0000-0000-0000-000000000001"),
        portMode: .automatic,
        configuredPort: nil,
        actualPort: 18_431,
        browserAgentCount: 2
    )

    try snapshot.validate()
    let data = try ContractCodec.encoder().encode(snapshot)
    let json = String(decoding: data, as: UTF8.self)
    #expect(!json.contains("token"))
    #expect(!json.contains("cookie"))
    #expect(!json.contains("authorization"))
    #expect(!json.contains("prompt"))
    #expect(!json.contains("actor"))
    let decoded = try ContractCodec.decoder().decode(DiagnosticSnapshot.self, from: data)
    #expect(decoded == snapshot)

    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    let destination = directory.appendingPathComponent("diagnostic.json")
    try ContractCodec.save(snapshot, to: destination)
    let attributes = try FileManager.default.attributesOfItem(atPath: destination.path)
    let permissions = attributes[.posixPermissions] as? NSNumber
    #expect(permissions?.intValue == 0o600)
    try? FileManager.default.removeItem(at: directory)
}

@Test func runDescriptorRequiresExpectedIdentity() throws {
    let actual = try InstanceID(rawValue: "customer-a")
    let expected = try InstanceID(rawValue: "customer-b")
    let descriptor = LocalRunDescriptor(
        instanceID: actual,
        processID: 100,
        configuredPort: 18_431,
        actualPort: 18_431,
        bootID: UUID(),
        runtimeVersion: "1.0.0",
        startedAt: Date()
    )
    #expect(throws: ContractError.self) { try descriptor.validate(expectedInstanceID: expected) }
}

@Test func helperStatusRoundTripsAndRejectsUnsafeDiagnostics() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let status = HelperStatus(
        instanceID: instanceID,
        helperProcessID: 42,
        phase: .ready,
        message: "Local 已就绪",
        actualPort: 18_431,
        updatedAt: Date(timeIntervalSince1970: 1_234)
    )
    try status.validate()
    let data = try ContractCodec.encoder().encode(status)
    let decoded = try ContractCodec.decoder().decode(HelperStatus.self, from: data)
    #expect(decoded == status)

    let unsafe = HelperStatus(
        instanceID: instanceID,
        helperProcessID: 42,
        phase: .failed,
        message: "failed\nsecret",
        errorCode: "Local Failed"
    )
    #expect(throws: ContractError.self) { try unsafe.validate() }
}

@Test func instanceManifestSeparatesAppAndHelperIdentity() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let manifest = InstanceManifest(
        instanceID: instanceID,
        displayName: "AI2Apps Customer A",
        bundleIdentifier: "com.ai2apps.customer-a",
        helperBundleIdentifier: "com.ai2apps.customer-a.helper",
        helperServiceName: "com.ai2apps.customer-a.helper-service"
    )
    try manifest.validate()
}

@Test func contractCodecRoundTripsWithOwnerOnlyPermissions() throws {
    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    let url = directory.appendingPathComponent("local.json")
    let original = LocalConfiguration(portMode: .fixed, configuredPort: 18_431)

    try ContractCodec.save(original, to: url)
    let loaded = try ContractCodec.load(LocalConfiguration.self, from: url)
    let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
    let permissions = attributes[.posixPermissions] as? NSNumber

    #expect(loaded == original)
    #expect(permissions?.intValue == 0o600)
    try? FileManager.default.removeItem(at: directory)
}

@Test func contractDecoderAcceptsPythonFractionalISO8601Dates() throws {
    let data = Data(
        #"{"schema_version":1,"instance_id":"main","pid":1234,"configured_port":null,"actual_port":8000,"boot_id":"630e3197-abd7-4411-a052-30041fa08090","runtime_version":"0.1.0","started_at":"2026-08-19T04:12:06.703221Z"}"#.utf8
    )

    let descriptor = try ContractCodec.decoder().decode(
        LocalRunDescriptor.self,
        from: data
    )

    #expect(descriptor.instanceID.rawValue == "main")
    #expect(descriptor.processID == 1234)
    #expect(descriptor.actualPort == 8000)
}

@Test func contractDecoderContinuesToAcceptWholeSecondISO8601Dates() throws {
    let data = Data(
        #"{"schema_version":1,"instance_id":"main","pid":1234,"configured_port":null,"actual_port":8000,"boot_id":"630e3197-abd7-4411-a052-30041fa08090","runtime_version":"0.1.0","started_at":"2026-08-19T04:12:06Z"}"#.utf8
    )

    let descriptor = try ContractCodec.decoder().decode(
        LocalRunDescriptor.self,
        from: data
    )

    #expect(descriptor.startedAt.timeIntervalSince1970 > 0)
}

@Test func runtimeManifestRejectsTraversal() {
    let digest = String(repeating: "a", count: 64)
    let manifest = RuntimeManifest(
        schemaVersion: 1,
        runtimeVersion: "1.0.0",
        platform: "macos",
        architecture: "arm64",
        entrypoint: "../bin/ai2apps",
        minimumShellProtocol: 1,
        minimumLocalAPIVersion: 1,
        artifacts: [.init(relativePath: "../bin/ai2apps", sha256: digest, size: 100)]
    )
    #expect(throws: ContractError.self) { try manifest.validate() }
}

private func makePackagedHelperFixture(
    instanceID: String = "login-test"
) throws -> (root: URL, app: URL, helper: URL, runtime: URL, aceFox: URL) {
    let fileManager = FileManager.default
    let root = fileManager.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    let app = root.appendingPathComponent("AI2Apps.app", isDirectory: true)
    let contents = app.appendingPathComponent("Contents", isDirectory: true)
    let helper = contents.appendingPathComponent(
        "Library/LoginItems/AI2AppsHelper.app",
        isDirectory: true
    )
    let helperContents = helper.appendingPathComponent("Contents", isDirectory: true)
    let runtime = helperContents.appendingPathComponent(
        "Resources/AI2AppsLocal/bin/omlx"
    )
    let aceFox = contents.appendingPathComponent(
        "Applications/AI2AppsShell.app/Contents/MacOS/acefox-bin"
    )
    try fileManager.createDirectory(
        at: helper.appendingPathComponent("Contents", isDirectory: true),
        withIntermediateDirectories: true
    )
    try fileManager.createDirectory(
        at: runtime.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try fileManager.createDirectory(
        at: aceFox.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    let info = try PropertyListSerialization.data(
        fromPropertyList: ["AI2AppsInstanceID": instanceID],
        format: .xml,
        options: 0
    )
    try info.write(to: helperContents.appendingPathComponent("Info.plist"))
    let shellInfo = try PropertyListSerialization.data(
        fromPropertyList: ["AI2AppsSharedBrowserBundle": true],
        format: .xml,
        options: 0
    )
    try shellInfo.write(
        to: aceFox
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Info.plist")
    )
    for executable in [runtime, aceFox] {
        try Data("#!/bin/sh\nexit 0\n".utf8).write(to: executable)
        try fileManager.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: executable.path
        )
    }
    return (root, app, helper, runtime, aceFox)
}

@Test func packagedHelperDerivesSignedAppConfigurationWithoutArguments() throws {
    let fixture = try makePackagedHelperFixture()
    defer { try? FileManager.default.removeItem(at: fixture.root) }

    let configuration = try HelperLaunchConfiguration(
        arguments: ["AI2AppsHelper"],
        environment: [:],
        helperBundleURL: fixture.helper
    )

    #expect(configuration.isPackaged)
    #expect(configuration.instanceID.rawValue == "login-test")
    #expect(configuration.appBundleURL == fixture.app.resolvingSymlinksInPath())
    #expect(configuration.runtimeExecutable == fixture.runtime.resolvingSymlinksInPath())
    #expect(
        configuration.runtimePythonExecutable
            == fixture.runtime
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("Python/cpython-3.11/bin/python3.11")
    )
    #expect(configuration.aceFoxExecutable == fixture.aceFox.resolvingSymlinksInPath())
}

@Test func packagedHelperRejectsCommandLineAndEnvironmentOverrides() throws {
    let fixture = try makePackagedHelperFixture()
    defer { try? FileManager.default.removeItem(at: fixture.root) }

    #expect(throws: ContractError.self) {
        try HelperLaunchConfiguration(
            arguments: ["AI2AppsHelper", "--runtime", "/usr/bin/false"],
            environment: [:],
            helperBundleURL: fixture.helper
        )
    }
    #expect(throws: ContractError.self) {
        try HelperLaunchConfiguration(
            arguments: ["AI2AppsHelper"],
            environment: ["AI2APPS_ACEFOX_EXECUTABLE": "/usr/bin/false"],
            helperBundleURL: fixture.helper
        )
    }
}

@Test func developmentHelperStillAcceptsExplicitExecutable() throws {
    let configuration = try HelperLaunchConfiguration(
        arguments: [
            "AI2AppsHelper",
            "--instance", "development-instance",
            "--runtime", "/usr/bin/true",
        ],
        environment: [:],
        helperBundleURL: URL(fileURLWithPath: "/tmp/AI2AppsHelper")
    )

    #expect(!configuration.isPackaged)
    #expect(configuration.instanceID.rawValue == "development-instance")
    #expect(configuration.runtimeExecutable.path == "/usr/bin/true")
}

@Test func loginItemStatusIsBoundedAndOwnerOnly() throws {
    let status = LoginItemStatus(
        instanceID: try InstanceID(rawValue: "customer-a"),
        phase: .requiresApproval,
        updatedAt: Date(timeIntervalSince1970: 1_234)
    )
    try status.validate()

    let directory = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    let destination = directory.appendingPathComponent("login-item.json")
    try ContractCodec.save(status, to: destination)
    let decoded = try ContractCodec.load(LoginItemStatus.self, from: destination)
    let attributes = try FileManager.default.attributesOfItem(atPath: destination.path)
    let permissions = attributes[.posixPermissions] as? NSNumber
    #expect(decoded == status)
    #expect(permissions?.intValue == 0o600)

    let unsafe = LoginItemStatus(
        instanceID: try InstanceID(rawValue: "customer-a"),
        phase: .failed,
        errorCode: "Failed with a user path"
    )
    #expect(throws: ContractError.self) { try unsafe.validate() }
    try? FileManager.default.removeItem(at: directory)
}
