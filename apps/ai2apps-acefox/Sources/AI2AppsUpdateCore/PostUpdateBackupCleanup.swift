import Foundation

public enum PostUpdateBackupCleanupError: Error, Equatable, CustomStringConvertible {
    case invalidInstalledApp
    case invalidBackup

    public var description: String {
        switch self {
        case .invalidInstalledApp:
            return "installed App must be an absolute, real .app directory"
        case .invalidBackup:
            return "previous App must be a real directory, not a symbolic link"
        }
    }
}

/// Removes the one-update rollback copy only after the replacement App has
/// completed its normal launch handoff. The backup name is derived rather than
/// accepted from input so cleanup cannot escape the installed App's directory.
public struct PostUpdateBackupCleanup: Sendable {
    public let installedApp: URL
    public let backupApp: URL

    public init(installedApp: URL) throws {
        let installed = installedApp.standardizedFileURL
        guard installed.isFileURL, installed.path.hasPrefix("/"),
              installed.pathExtension == "app" else {
            throw PostUpdateBackupCleanupError.invalidInstalledApp
        }
        self.installedApp = installed
        self.backupApp = installed.deletingLastPathComponent().appendingPathComponent(
            "\(installed.deletingPathExtension().lastPathComponent).previous.app",
            isDirectory: true
        )
    }

    @discardableResult
    public func removeIfPresent(fileManager: FileManager = .default) throws -> Bool {
        guard fileManager.fileExists(atPath: backupApp.path) else { return false }
        let values = try backupApp.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey])
        guard values.isDirectory == true, values.isSymbolicLink != true else {
            throw PostUpdateBackupCleanupError.invalidBackup
        }
        try fileManager.removeItem(at: backupApp)
        return true
    }
}
