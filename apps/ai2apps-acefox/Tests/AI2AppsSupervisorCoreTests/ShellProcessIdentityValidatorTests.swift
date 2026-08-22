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
