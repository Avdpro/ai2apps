import AI2AppsContracts
import AI2AppsSupervisorCore
import Foundation
import Testing

@Test func shellProcessIdentityRequiresEveryInstanceBoundary() throws {
    let expectedInstance = try InstanceID(rawValue: "customer-a")
    let otherInstance = try InstanceID(rawValue: "customer-b")
    let app = URL(fileURLWithPath: "/Applications/AI2Apps A.app")
    let executable = app.appendingPathComponent("Contents/MacOS/acefox-bin")
    let descriptor = ShellRunDescriptor(
        instanceID: expectedInstance,
        processID: 123,
        appBundlePath: app.path,
        executablePath: executable.path
    )
    let validator = ShellProcessIdentityValidator()

    #expect(validator.validate(
        descriptor,
        expectedInstanceID: expectedInstance,
        expectedAppBundle: app,
        expectedExecutable: executable,
        liveExecutablePath: { _ in executable.path }
    ))
    #expect(!validator.validate(
        descriptor,
        expectedInstanceID: otherInstance,
        expectedAppBundle: app,
        expectedExecutable: executable,
        liveExecutablePath: { _ in executable.path }
    ))
    #expect(!validator.validate(
        descriptor,
        expectedInstanceID: expectedInstance,
        expectedAppBundle: URL(fileURLWithPath: "/Applications/AI2Apps B.app"),
        expectedExecutable: executable,
        liveExecutablePath: { _ in executable.path }
    ))
    #expect(!validator.validate(
        descriptor,
        expectedInstanceID: expectedInstance,
        expectedAppBundle: app,
        expectedExecutable: executable,
        liveExecutablePath: { _ in "/Applications/Other.app/Contents/MacOS/acefox-bin" }
    ))
}

@Test func shellProcessActivationIdentityAllowsRelocatedMatchingBundle() throws {
    let instanceID = try InstanceID(rawValue: "dev")
    let descriptor = ShellRunDescriptor(
        instanceID: instanceID,
        processID: 42,
        appBundlePath: "/Applications/AI2Apps-dev.app",
        executablePath: "/Applications/AI2Apps-dev.app/Contents/Applications/AI2Apps.app/Contents/MacOS/acefox-bin"
    )
    let relocatedExecutable = "/tmp/archive/AI2Apps-dev.app/Contents/Applications/AI2Apps.app/Contents/MacOS/acefox-bin"

    #expect(ShellProcessIdentityValidator().validateForActivation(
        descriptor,
        expectedInstanceID: instanceID,
        expectedShellBundleIdentifier: "com.ai2apps.desktop.dev.shell",
        expectedMainBundleIdentifier: "com.ai2apps.desktop.dev",
        liveShellBundleIdentifier: "com.ai2apps.desktop.dev.shell",
        liveMainBundleIdentifier: "com.ai2apps.desktop.dev",
        liveInstanceID: instanceID,
        liveExecutablePath: relocatedExecutable,
        liveBundleExecutablePath: relocatedExecutable
    ))
}

@Test func shellProcessActivationIdentityRejectsAnotherInstance() throws {
    let instanceID = try InstanceID(rawValue: "dev")
    let otherInstanceID = try InstanceID(rawValue: "other")
    let descriptor = ShellRunDescriptor(
        instanceID: instanceID,
        processID: 42,
        appBundlePath: "/Applications/AI2Apps-dev.app",
        executablePath: "/Applications/AI2Apps-dev.app/Contents/Applications/AI2Apps.app/Contents/MacOS/acefox-bin"
    )
    let relocatedExecutable = "/tmp/archive/AI2Apps-dev.app/Contents/Applications/AI2Apps.app/Contents/MacOS/acefox-bin"

    #expect(!ShellProcessIdentityValidator().validateForActivation(
        descriptor,
        expectedInstanceID: instanceID,
        expectedShellBundleIdentifier: "com.ai2apps.desktop.dev.shell",
        expectedMainBundleIdentifier: "com.ai2apps.desktop.dev",
        liveShellBundleIdentifier: "com.ai2apps.desktop.dev.shell",
        liveMainBundleIdentifier: "com.ai2apps.desktop.dev",
        liveInstanceID: otherInstanceID,
        liveExecutablePath: relocatedExecutable,
        liveBundleExecutablePath: relocatedExecutable
    ))
}
