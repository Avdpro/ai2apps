import AI2AppsContracts
import Foundation

public struct ShellProcessIdentityValidator: Sendable {
    public init() {}

    public func validate(
        _ descriptor: ShellRunDescriptor,
        expectedInstanceID: InstanceID,
        expectedAppBundle: URL,
        expectedExecutable: URL,
        liveExecutablePath: (Int32) -> String?
    ) -> Bool {
        guard (try? descriptor.validate()) != nil,
              descriptor.instanceID == expectedInstanceID,
              descriptor.appBundlePath == expectedAppBundle.standardizedFileURL.path,
              descriptor.executablePath == expectedExecutable.resolvingSymlinksInPath().path,
              liveExecutablePath(descriptor.processID) == descriptor.executablePath else {
            return false
        }
        return true
    }

    public func validateForActivation(
        _ descriptor: ShellRunDescriptor,
        expectedInstanceID: InstanceID,
        expectedShellBundleIdentifier: String,
        expectedMainBundleIdentifier: String,
        liveShellBundleIdentifier: String?,
        liveMainBundleIdentifier: String?,
        liveInstanceID: InstanceID?,
        liveExecutablePath: String?,
        liveBundleExecutablePath: String?
    ) -> Bool {
        guard (try? descriptor.validate()) != nil,
              descriptor.instanceID == expectedInstanceID,
              liveShellBundleIdentifier == expectedShellBundleIdentifier,
              liveMainBundleIdentifier == expectedMainBundleIdentifier,
              liveInstanceID == expectedInstanceID,
              let liveExecutablePath,
              let liveBundleExecutablePath,
              liveExecutablePath == liveBundleExecutablePath,
              URL(fileURLWithPath: descriptor.executablePath).lastPathComponent
                == URL(fileURLWithPath: liveExecutablePath).lastPathComponent else {
            return false
        }
        return true
    }
}
