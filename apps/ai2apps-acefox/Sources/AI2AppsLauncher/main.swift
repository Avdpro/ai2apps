import AI2AppsContracts
import AI2AppsSupervisorCore
import AppKit
import Darwin
import Foundation
import ServiceManagement

private struct LauncherConfiguration {
    let instanceID: InstanceID
    let paths: InstancePaths
    let helperExecutable: URL
    let helperBundleIdentifier: String
    let localExecutable: URL
    let aceFoxExecutable: URL
    let applicationGroupIdentifier: String?

    init(arguments: [String] = CommandLine.arguments) throws {
        var instance: String?
        var index = 1
        while index < arguments.count {
            if arguments[index] == "--instance", index + 1 < arguments.count {
                index += 1
                instance = arguments[index]
            }
            index += 1
        }
        let packagedInstance = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsInstanceID"
        ) as? String
        instanceID = try InstanceID(
            rawValue: instance ?? packagedInstance ?? "default"
        )
        paths = try InstancePaths.packaged(instanceID: instanceID)
        applicationGroupIdentifier = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsApplicationGroupIdentifier"
        ) as? String

        let environment = ProcessInfo.processInfo.environment
        let contents = Bundle.main.bundleURL.appendingPathComponent("Contents", isDirectory: true)
        helperExecutable = try Self.executableURL(
            environment["AI2APPS_HELPER_EXECUTABLE"],
            fallback: contents.appendingPathComponent(
                "Library/LoginItems/AI2AppsHelper.app/Contents/MacOS/AI2AppsHelper"
            ),
            field: "helper_executable"
        )
        let helperBundleURL = helperExecutable
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        guard let helperBundleIdentifier = Bundle(url: helperBundleURL)?.bundleIdentifier,
              let appBundleIdentifier = Bundle.main.bundleIdentifier,
              helperBundleIdentifier == "\(appBundleIdentifier).helper" else {
            throw ContractError.invalidField(
                field: "helper_bundle_identifier",
                reason: "must match the signed containing App identity"
            )
        }
        self.helperBundleIdentifier = helperBundleIdentifier
        localExecutable = try Self.executableURL(
            environment["AI2APPS_LOCAL_EXECUTABLE"],
            fallback: contents.appendingPathComponent(
                "Library/LoginItems/AI2AppsHelper.app/Contents/Resources/AI2AppsLocal/bin/omlx"
            ),
            field: "local_executable"
        )
        try Self.validatePackagedRuntimeIfRequired(localExecutable: localExecutable)
        aceFoxExecutable = try Self.executableURL(
            environment["AI2APPS_ACEFOX_EXECUTABLE"],
            fallback: contents.appendingPathComponent(
                "Applications/AI2AppsShell.app/Contents/MacOS/acefox-bin"
            ),
            field: "acefox_executable"
        )
    }

    private static func executableURL(_ override: String?, fallback: URL, field: String) throws -> URL {
        let url: URL
        if let override, override.hasPrefix("/") {
            url = URL(fileURLWithPath: override)
        } else {
            url = fallback
        }
        guard FileManager.default.isExecutableFile(atPath: url.path) else {
            throw ContractError.invalidField(field: field, reason: "executable not found at \(url.path)")
        }
        return url
    }

    private static func validatePackagedRuntimeIfRequired(localExecutable: URL) throws {
        if ProcessInfo.processInfo.environment["AI2APPS_LOCAL_EXECUTABLE"] != nil {
            return
        }
        let runtimeRoot = localExecutable
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let manifestURL = runtimeRoot.appendingPathComponent("runtime-manifest.json")
        if FileManager.default.fileExists(atPath: manifestURL.path) {
            let manifest = try ContractCodec.load(RuntimeManifest.self, from: manifestURL)
            _ = try RuntimeValidator().validate(manifest: manifest, root: runtimeRoot)
            return
        }
        let development = Bundle.main.object(forInfoDictionaryKey: "AI2AppsDevelopment") as? Bool
        guard development == true else {
            throw ContractError.invalidField(field: "runtime-manifest", reason: "is required in production bundles")
        }
    }
}

private func loginItemPhase(for status: SMAppService.Status) -> LoginItemPhase {
    switch status {
    case .enabled:
        return .enabled
    case .requiresApproval:
        return .requiresApproval
    case .notRegistered:
        return .notRegistered
    case .notFound:
        return .notFound
    @unknown default:
        return .notFound
    }
}

private func updateLoginItemRegistration(
    configuration: LauncherConfiguration
) throws -> LoginItemPhase {
    let development = Bundle.main.object(forInfoDictionaryKey: "AI2AppsDevelopment") as? Bool
    guard development != true else { return .skippedDevelopment }
    let resourceValues = try Bundle.main.bundleURL.resourceValues(
        forKeys: [.volumeIsReadOnlyKey]
    )
    // Never persist a Login Item that points at a transient mounted DMG.
    guard resourceValues.volumeIsReadOnly != true else { return .skippedReadOnly }

    let paths = configuration.paths
    let configURL = paths.configDirectory.appendingPathComponent("local.json")
    let localConfiguration = (
        try? ContractCodec.load(LocalConfiguration.self, from: configURL)
    ) ?? LocalConfiguration()
    let service = SMAppService.loginItem(
        identifier: configuration.helperBundleIdentifier
    )
    if localConfiguration.startAtLogin {
        if service.status == .notRegistered || service.status == .notFound {
            try service.register()
        }
    } else if service.status != .notRegistered && service.status != .notFound {
        try service.unregister()
    }
    return loginItemPhase(for: service.status)
}

private func publishLoginItemStatus(
    configuration: LauncherConfiguration,
    phase: LoginItemPhase,
    errorCode: String? = nil
) throws {
    let paths = configuration.paths
    try paths.preparePrivateDirectories()
    try ContractCodec.save(
        LoginItemStatus(
            instanceID: configuration.instanceID,
            phase: phase,
            errorCode: errorCode
        ),
        to: paths.runDirectory.appendingPathComponent("login-item.json")
    )
}

private final class ApplicationOpenState: @unchecked Sendable {
    private let lock = NSLock()
    private var result: Result<NSRunningApplication, Error>?

    func store(_ result: Result<NSRunningApplication, Error>) {
        lock.withLock { self.result = result }
    }

    func load() -> Result<NSRunningApplication, Error>? {
        lock.withLock { result }
    }
}

private func openApplication(
    at bundleURL: URL,
    configuration: NSWorkspace.OpenConfiguration,
    field: String
) throws -> NSRunningApplication {
    let state = ApplicationOpenState()
    NSWorkspace.shared.openApplication(
        at: bundleURL,
        configuration: configuration
    ) { application, error in
        if let application {
            state.store(.success(application))
        } else {
            state.store(.failure(error ?? ContractError.invalidField(
                field: field,
                reason: "LaunchServices did not return an application"
            )))
        }
    }
    let deadline = Date().addingTimeInterval(10)
    while state.load() == nil, Date() < deadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
    }
    guard let result = state.load() else {
        throw ContractError.invalidField(field: field, reason: "LaunchServices timed out")
    }
    return try result.get()
}

private func launchHelper(configuration: LauncherConfiguration) throws {
    let helperBundle = configuration.helperExecutable
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let workspaceConfiguration = NSWorkspace.OpenConfiguration()
    workspaceConfiguration.activates = false
    workspaceConfiguration.addsToRecentItems = false
    _ = try openApplication(
        at: helperBundle,
        configuration: workspaceConfiguration,
        field: "helper_launch"
    )
}

private func launchAceFox(configuration: LauncherConfiguration) throws {
    let paths = configuration.paths
    let profile = paths.browserProfilesDirectory.appendingPathComponent(
        "app-shell",
        isDirectory: true
    )
    try FileManager.default.createDirectory(
        at: profile,
        withIntermediateDirectories: true,
        attributes: [.posixPermissions: 0o700]
    )
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o700],
        ofItemAtPath: profile.path
    )
    let shellPreferences = """
    user_pref("signon.rememberSignons", false);
    user_pref("browser.formfill.enable", false);
    user_pref("browser.sessionstore.resume_from_crash", false);
    user_pref("browser.shell.checkDefaultBrowser", false);
    user_pref("browser.tabs.warnOnClose", false);
    user_pref("permissions.default.microphone", 1);
    user_pref("media.navigator.permission.disabled", true);
    """
    let preferencesURL = profile.appendingPathComponent("user.js")
    try Data(shellPreferences.utf8).write(to: preferencesURL, options: .atomic)
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o600],
        ofItemAtPath: preferencesURL.path
    )
    let shellBundle = configuration.aceFoxExecutable
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let workspaceConfiguration = NSWorkspace.OpenConfiguration()
    workspaceConfiguration.activates = true
    workspaceConfiguration.addsToRecentItems = false
    // The signed Shell launcher derives its profile and Gecko arguments from
    // its own Info.plist and App Group. LaunchServices only selects the
    // independent application identity; no security boundary depends on
    // cross-application argument or environment delivery.
    workspaceConfiguration.createsNewApplicationInstance = true
    let application = try openApplication(
        at: shellBundle,
        configuration: workspaceConfiguration,
        field: "acefox_launch"
    )
    try ContractCodec.save(
        ShellRunDescriptor(
            instanceID: configuration.instanceID,
            processID: application.processIdentifier,
            appBundlePath: Bundle.main.bundleURL.standardizedFileURL.path,
            executablePath: configuration.aceFoxExecutable.resolvingSymlinksInPath().path
        ),
        to: paths.runDirectory.appendingPathComponent("shell.json")
    )
}

private func rejectOrdinaryLaunchDuringUpdate(arguments: [String]) throws {
    if arguments.dropFirst().contains("--post-update-health-only") { return }
    let app = Bundle.main.bundleURL.standardizedFileURL
    let marker = app.deletingLastPathComponent().appendingPathComponent(
        ".\(app.lastPathComponent).update.pending"
    )
    if FileManager.default.fileExists(atPath: marker.path) {
        throw ContractError.invalidField(
            field: "update",
            reason: "this App is being updated"
        )
    }
}

do {
    try rejectOrdinaryLaunchDuringUpdate(arguments: CommandLine.arguments)
    let configuration = try LauncherConfiguration()
    if CommandLine.arguments.dropFirst().contains("--post-update-health-only") {
        // Constructing the packaged configuration above verifies the nested
        // Helper identity and the complete embedded Runtime manifest. This
        // mode deliberately performs no login-item, Helper, Local, or UI work.
        exit(EXIT_SUCCESS)
    }
    let loginItemUpdateOnly = CommandLine.arguments.dropFirst().contains(
        "--update-login-item-only"
    )
    var loginItemUpdateSucceeded = true
    do {
        let phase = try updateLoginItemRegistration(configuration: configuration)
        try publishLoginItemStatus(configuration: configuration, phase: phase)
    } catch {
        loginItemUpdateSucceeded = false
        try? publishLoginItemStatus(
            configuration: configuration,
            phase: .failed,
            errorCode: "registration_failed"
        )
        FileHandle.standardError.write(
            Data("AI2Apps Launcher login item: \(error)\n".utf8)
        )
    }
    if loginItemUpdateOnly {
        exit(loginItemUpdateSucceeded ? EXIT_SUCCESS : EXIT_FAILURE)
    }
    try launchHelper(configuration: configuration)
    try launchAceFox(configuration: configuration)
} catch {
    FileHandle.standardError.write(Data("AI2Apps Launcher: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}
