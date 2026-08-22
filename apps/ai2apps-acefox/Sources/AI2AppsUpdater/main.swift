import AI2AppsUpdateCore
import Darwin
import Foundation

private struct Configuration {
    let installedApp: URL
    let candidateApp: URL
    let backupApp: URL
    let pendingMarker: URL
    let waitPID: pid_t
    let waitTimeout: TimeInterval

    init(arguments: [String] = CommandLine.arguments) throws {
        var values: [String: String] = [:]
        var index = 1
        while index < arguments.count {
            let key = arguments[index]
            guard key.hasPrefix("--"), index + 1 < arguments.count else {
                throw UpdateError.invalidArguments
            }
            index += 1
            guard values.updateValue(arguments[index], forKey: key) == nil else {
                throw UpdateError.invalidArguments
            }
            index += 1
        }
        guard let installed = values["--installed-app"], installed.hasPrefix("/"),
              let candidate = values["--candidate-app"], candidate.hasPrefix("/"),
              let backup = values["--backup-app"], backup.hasPrefix("/"),
              let marker = values["--pending-marker"], marker.hasPrefix("/"),
              let pidText = values["--wait-pid"], let pid = pid_t(pidText), pid > 1,
              values.count == 5 else {
            throw UpdateError.invalidArguments
        }
        installedApp = URL(fileURLWithPath: installed).standardizedFileURL
        candidateApp = URL(fileURLWithPath: candidate).standardizedFileURL
        backupApp = URL(fileURLWithPath: backup).standardizedFileURL
        pendingMarker = URL(fileURLWithPath: marker).standardizedFileURL
        waitPID = pid
        waitTimeout = 60
        let expectedMarker = installedApp.deletingLastPathComponent().appendingPathComponent(
            ".\(installedApp.lastPathComponent).update.pending"
        ).standardizedFileURL
        guard pendingMarker == expectedMarker else {
            throw UpdateError.invalidPendingMarker
        }
    }
}

private enum UpdateError: Error, CustomStringConvertible {
    case invalidArguments
    case invalidInfo(String)
    case invalidSignature(String)
    case incompatibleCandidate(String)
    case waitTimedOut
    case updaterInsideInstalledApp
    case healthTimedOut
    case invalidPendingMarker

    var description: String {
        switch self {
        case .invalidArguments:
            return "expected absolute --installed-app, --candidate-app, --backup-app, --pending-marker, and positive --wait-pid"
        case .invalidInfo(let reason): return "invalid App identity: \(reason)"
        case .invalidSignature(let reason): return "invalid App signature: \(reason)"
        case .incompatibleCandidate(let reason): return "incompatible candidate: \(reason)"
        case .waitTimedOut: return "timed out waiting for the Shell to exit"
        case .updaterInsideInstalledApp: return "Updater must be copied outside the installed App before execution"
        case .healthTimedOut: return "updated Launcher health check timed out"
        case .invalidPendingMarker: return "pending marker must be the installed App sibling marker"
        }
    }
}

private struct Identity: Equatable {
    let bundleIdentifier: String
    let instanceID: String
    let build: Int
    let teamIdentifier: String
}

private func run(_ executable: String, _ arguments: [String], timeout: TimeInterval = 120) throws -> (Int32, String) {
    let process = Process()
    let pipe = Pipe()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    process.standardOutput = pipe
    process.standardError = pipe
    try process.run()
    let deadline = Date().addingTimeInterval(timeout)
    while process.isRunning && Date() < deadline { usleep(50_000) }
    if process.isRunning {
        process.terminate()
        process.waitUntilExit()
        throw UpdateError.healthTimedOut
    }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    return (process.terminationStatus, String(decoding: data, as: UTF8.self))
}

private func info(at app: URL) throws -> [String: Any] {
    let data = try Data(contentsOf: app.appendingPathComponent("Contents/Info.plist"))
    guard let value = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else {
        throw UpdateError.invalidInfo("Info.plist is not a dictionary")
    }
    return value
}

private func signedIdentity(at app: URL) throws -> Identity {
    let verified = try run("/usr/bin/codesign", ["--verify", "--deep", "--strict", app.path])
    guard verified.0 == 0 else {
        throw UpdateError.invalidSignature(String(verified.1.suffix(256)))
    }
    let details = try run("/usr/bin/codesign", ["-dvvv", app.path])
    guard details.0 == 0 else { throw UpdateError.invalidSignature("cannot inspect signature") }
    func value(_ name: String) -> String? {
        details.1.split(separator: "\n").first { $0.hasPrefix("\(name)=") }
            .map { String($0.dropFirst(name.count + 1)) }
    }
    guard let signatureIdentifier = value("Identifier"),
          let team = value("TeamIdentifier"), !team.isEmpty, team != "not set",
          details.1.split(separator: "\n").contains(where: {
              $0.hasPrefix("CodeDirectory ") && $0.contains("runtime")
          }) else {
        throw UpdateError.invalidSignature("Developer ID team or Hardened Runtime is missing")
    }
    let plist = try info(at: app)
    guard let bundle = plist["CFBundleIdentifier"] as? String, bundle == signatureIdentifier,
          let instance = plist["AI2AppsInstanceID"] as? String, !instance.isEmpty,
          let buildText = plist["CFBundleVersion"] as? String,
          buildText.allSatisfy({ $0.isASCII && $0.isNumber }),
          let build = Int(buildText), build > 0 else {
        throw UpdateError.invalidInfo("Bundle ID, instance ID, or positive Build Number is missing")
    }
    return Identity(bundleIdentifier: bundle, instanceID: instance, build: build, teamIdentifier: team)
}

private func waitForExit(of pid: pid_t, timeout: TimeInterval) throws {
    let deadline = Date().addingTimeInterval(timeout)
    while kill(pid, 0) == 0 || errno == EPERM {
        if Date() >= deadline { throw UpdateError.waitTimedOut }
        usleep(100_000)
    }
    guard errno == ESRCH else { throw UpdateError.waitTimedOut }
}

private func isDescendant(_ child: URL, of parent: URL) -> Bool {
    child.standardizedFileURL.path.hasPrefix(parent.standardizedFileURL.path + "/")
}

do {
    let configuration = try Configuration()
    defer { try? FileManager.default.removeItem(at: configuration.pendingMarker) }
    guard let updaterURL = Bundle.main.executableURL,
          !isDescendant(updaterURL.resolvingSymlinksInPath(), of: configuration.installedApp) else {
        throw UpdateError.updaterInsideInstalledApp
    }
    let installed = try signedIdentity(at: configuration.installedApp)
    let candidate = try signedIdentity(at: configuration.candidateApp)
    guard candidate.bundleIdentifier == installed.bundleIdentifier,
          candidate.instanceID == installed.instanceID,
          candidate.teamIdentifier == installed.teamIdentifier else {
        throw UpdateError.incompatibleCandidate("Bundle, instance, and Developer ID team must match")
    }
    guard candidate.build > installed.build else {
        throw UpdateError.incompatibleCandidate("Build Number must increase")
    }
    try waitForExit(of: configuration.waitPID, timeout: configuration.waitTimeout)

    let transaction = try AppUpdateTransaction(
        installedApp: configuration.installedApp,
        candidateApp: configuration.candidateApp,
        backupApp: configuration.backupApp
    )
    let result = try transaction.execute(
        installedValidator: { app in
            guard try signedIdentity(at: app) == installed else {
                throw UpdateError.invalidSignature("installed App changed during update")
            }
        },
        candidateValidator: { app in
            guard try signedIdentity(at: app) == candidate else {
                throw UpdateError.invalidSignature("candidate App changed during update")
            }
        },
        healthCheck: { app in
            let launcher = app.appendingPathComponent("Contents/MacOS/AI2Apps")
            let outcome = try run(launcher.path, ["--post-update-health-only"])
            return outcome.0 == 0
        }
    )
    print("updated \(installed.build) -> \(candidate.build); backup=\(result.backupApp.path)")
} catch {
    FileHandle.standardError.write(Data("AI2Apps Updater: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}
