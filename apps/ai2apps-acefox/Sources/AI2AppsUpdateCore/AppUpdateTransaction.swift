import Darwin
import Foundation

public enum AppUpdateTransactionError: Error, Equatable, CustomStringConvertible {
    case invalidPath(String)
    case missingApp(String)
    case backupAlreadyExists
    case updateInProgress
    case healthCheckFailed
    case rolledBack(String)
    case rollbackFailed(String)

    public var description: String {
        switch self {
        case .invalidPath(let reason): return "invalid update path: \(reason)"
        case .missingApp(let name): return "missing \(name) App"
        case .backupAlreadyExists: return "backup App already exists"
        case .updateInProgress: return "another update transaction is in progress"
        case .healthCheckFailed: return "updated App failed its health check"
        case .rolledBack(let reason): return "update rolled back: \(reason)"
        case .rollbackFailed(let reason): return "update rollback failed: \(reason)"
        }
    }
}

public struct AppUpdateResult: Equatable, Sendable {
    public let installedApp: URL
    public let backupApp: URL

    public init(installedApp: URL, backupApp: URL) {
        self.installedApp = installedApp
        self.backupApp = backupApp
    }
}

/// Performs only the same-volume filesystem transaction. Signature, release
/// metadata, and product identity policy remain mandatory validator concerns.
public struct AppUpdateTransaction: Sendable {
    public typealias Validator = @Sendable (URL) throws -> Void
    public typealias HealthCheck = @Sendable (URL) throws -> Bool

    public let installedApp: URL
    public let candidateApp: URL
    public let backupApp: URL

    public init(installedApp: URL, candidateApp: URL, backupApp: URL) throws {
        let installed = installedApp.standardizedFileURL
        let candidate = candidateApp.standardizedFileURL
        let backup = backupApp.standardizedFileURL
        guard installed.pathExtension == "app", candidate.pathExtension == "app",
              backup.pathExtension == "app" else {
            throw AppUpdateTransactionError.invalidPath("all artifacts must use the .app extension")
        }
        guard installed != candidate, installed != backup, candidate != backup else {
            throw AppUpdateTransactionError.invalidPath("installed, candidate, and backup paths must differ")
        }
        guard installed.deletingLastPathComponent() == backup.deletingLastPathComponent() else {
            throw AppUpdateTransactionError.invalidPath("backup must be a sibling of the installed App")
        }
        self.installedApp = installed
        self.candidateApp = candidate
        self.backupApp = backup
    }

    public func execute(
        fileManager: FileManager = .default,
        installedValidator: Validator,
        candidateValidator: Validator,
        healthCheck: HealthCheck
    ) throws -> AppUpdateResult {
        guard fileManager.fileExists(atPath: installedApp.path) else {
            throw AppUpdateTransactionError.missingApp("installed")
        }
        guard fileManager.fileExists(atPath: candidateApp.path) else {
            throw AppUpdateTransactionError.missingApp("candidate")
        }
        guard !fileManager.fileExists(atPath: backupApp.path) else {
            throw AppUpdateTransactionError.backupAlreadyExists
        }
        try rejectSymbolicLink(installedApp)
        try rejectSymbolicLink(candidateApp)

        let parent = installedApp.deletingLastPathComponent()
        let lock = parent.appendingPathComponent(
            ".\(installedApp.lastPathComponent).update.lock"
        )
        let descriptor = open(lock.path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0o600)
        guard descriptor >= 0 else {
            if errno == EEXIST { throw AppUpdateTransactionError.updateInProgress }
            throw AppUpdateTransactionError.invalidPath("cannot create update lock: \(String(cString: strerror(errno)))")
        }
        defer {
            close(descriptor)
            try? fileManager.removeItem(at: lock)
        }

        let staged = parent.appendingPathComponent(
            ".AI2Apps.update-\(UUID().uuidString).app",
            isDirectory: true
        )
        defer { try? fileManager.removeItem(at: staged) }
        try fileManager.copyItem(at: candidateApp, to: staged)
        try candidateValidator(staged)
        try installedValidator(installedApp)

        try fileManager.moveItem(at: installedApp, to: backupApp)
        do {
            try fileManager.moveItem(at: staged, to: installedApp)
            try candidateValidator(installedApp)
            guard try healthCheck(installedApp) else {
                throw AppUpdateTransactionError.healthCheckFailed
            }
            return AppUpdateResult(installedApp: installedApp, backupApp: backupApp)
        } catch {
            do {
                let failed = parent.appendingPathComponent(
                    ".AI2Apps.failed-\(UUID().uuidString).app",
                    isDirectory: true
                )
                if fileManager.fileExists(atPath: installedApp.path) {
                    try fileManager.moveItem(at: installedApp, to: failed)
                }
                try fileManager.moveItem(at: backupApp, to: installedApp)
                try installedValidator(installedApp)
                try? fileManager.removeItem(at: failed)
            } catch let rollbackError {
                throw AppUpdateTransactionError.rollbackFailed(String(describing: rollbackError))
            }
            throw AppUpdateTransactionError.rolledBack(String(describing: error))
        }
    }

    private func rejectSymbolicLink(_ url: URL) throws {
        let values = try url.resourceValues(forKeys: [.isSymbolicLinkKey, .isDirectoryKey])
        guard values.isSymbolicLink != true, values.isDirectory == true else {
            throw AppUpdateTransactionError.invalidPath("App roots must be real directories")
        }
    }
}
