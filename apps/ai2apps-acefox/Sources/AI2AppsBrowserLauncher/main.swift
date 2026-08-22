import AI2AppsContracts
import Foundation

private func requireInfoString(_ key: String) throws -> String {
    guard let value = Bundle.main.object(forInfoDictionaryKey: key) as? String,
          !value.isEmpty else {
        throw ContractError.invalidField(field: key, reason: "is required")
    }
    return value
}

private func writeShellPreferences(to profile: URL) throws {
    try FileManager.default.createDirectory(
        at: profile,
        withIntermediateDirectories: true,
        attributes: [.posixPermissions: 0o700]
    )
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o700],
        ofItemAtPath: profile.path
    )
    let preferences = """
    user_pref("signon.rememberSignons", false);
    user_pref("browser.formfill.enable", false);
    user_pref("browser.sessionstore.resume_from_crash", false);
    user_pref("browser.shell.checkDefaultBrowser", false);
    user_pref("browser.tabs.warnOnClose", false);
    user_pref("permissions.default.microphone", 1);
    user_pref("media.navigator.permission.disabled", true);
    """
    let destination = profile.appendingPathComponent("user.js")
    try Data(preferences.utf8).write(to: destination, options: .atomic)
    try FileManager.default.setAttributes(
        [.posixPermissions: 0o600],
        ofItemAtPath: destination.path
    )
}

private func launchBrowserChild(
    executable: URL,
    arguments: [String],
    environment: [String: String],
    descriptorURL: URL,
    instanceID: InstanceID
) throws -> Never {
    let process = Process()
    process.executableURL = executable
    process.arguments = arguments
    process.environment = environment
    try process.run()

    let outerApp = Bundle.main.bundleURL
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    try ContractCodec.save(
        ShellRunDescriptor(
            instanceID: instanceID,
            processID: process.processIdentifier,
            appBundlePath: outerApp.standardizedFileURL.path,
            executablePath: executable.resolvingSymlinksInPath().path
        ),
        to: descriptorURL
    )
    process.waitUntilExit()
    exit(process.terminationStatus)
}

do {
    let instanceID = try InstanceID(rawValue: requireInfoString("AI2AppsInstanceID"))
    let role = try requireInfoString("AI2AppsBrowserRole")
    guard role == "shell" else {
        throw ContractError.invalidField(
            field: "AI2AppsBrowserRole",
            reason: "unsupported browser role"
        )
    }
    let applicationGroup = try requireInfoString("AI2AppsApplicationGroupIdentifier")
    let paths = try InstancePaths.packaged(instanceID: instanceID)
    guard let storageRoot = paths.storageContainerDirectory else {
        throw ContractError.invalidField(
            field: "application_group",
            reason: "Shell requires an App Group container"
        )
    }
    try paths.preparePrivateDirectories()
    let profile = paths.browserProfilesDirectory.appendingPathComponent(
        "app-shell",
        isDirectory: true
    )
    try writeShellPreferences(to: profile)

    let engine = Bundle.main.bundleURL.appendingPathComponent(
        "Contents/MacOS/acefox-bin"
    )
    guard FileManager.default.isExecutableFile(atPath: engine.path) else {
        throw ContractError.invalidField(
            field: "acefox-bin",
            reason: "signed browser engine is unavailable"
        )
    }
    let environment = ProcessInfo.processInfo.environment.merging([
        "AI2APPS_APP_SHELL": "1",
        "AI2APPS_DISABLE_REMOTE_SERVER": "1",
        "AI2APPS_APPLICATION_GROUP": applicationGroup,
    ]) { _, required in required }
    try launchBrowserChild(
        executable: engine,
        arguments: [
            "-new-instance",
            "-profile", profile.path,
            "--ai2apps-shell",
            "--ai2apps-instance", instanceID.rawValue,
            "--ai2apps-storage-root", storageRoot.path,
        ],
        environment: environment,
        descriptorURL: paths.runDirectory.appendingPathComponent("shell.json"),
        instanceID: instanceID
    )
} catch {
    FileHandle.standardError.write(Data("AI2Apps browser launcher: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}
