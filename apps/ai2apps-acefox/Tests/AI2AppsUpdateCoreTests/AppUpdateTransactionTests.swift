import AI2AppsUpdateCore
import Foundation
import Testing

private func makeApp(_ url: URL, marker: String) throws {
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    try Data(marker.utf8).write(to: url.appendingPathComponent("marker"))
}

private func marker(_ app: URL) throws -> String {
    try String(contentsOf: app.appendingPathComponent("marker"), encoding: .utf8)
}

private func requireMarker(_ expected: String, at app: URL) throws {
    guard try marker(app) == expected else { throw CocoaError(.fileReadCorruptFile) }
}

private func withFixture(_ body: (URL, URL, URL) throws -> Void) throws {
    let root = FileManager.default.temporaryDirectory
        .appendingPathComponent("ai2apps-update-tests-\(UUID().uuidString)", isDirectory: true)
    defer { try? FileManager.default.removeItem(at: root) }
    let installed = root.appendingPathComponent("AI2Apps.app")
    let candidate = root.appendingPathComponent("download/AI2Apps.app")
    let backup = root.appendingPathComponent("AI2Apps.previous.app")
    try makeApp(installed, marker: "old")
    try makeApp(candidate, marker: "new")
    try body(installed, candidate, backup)
}

@Test func successfulUpdatePreservesVerifiedBackup() throws {
    try withFixture { installed, candidate, backup in
        let transaction = try AppUpdateTransaction(
            installedApp: installed,
            candidateApp: candidate,
            backupApp: backup
        )
        let result = try transaction.execute(
            installedValidator: { try requireMarker("old", at: $0) },
            candidateValidator: { try requireMarker("new", at: $0) },
            healthCheck: { try marker($0) == "new" }
        )
        #expect(result.backupApp == backup)
        #expect(try marker(installed) == "new")
        #expect(try marker(backup) == "old")
        #expect(try marker(candidate) == "new")
    }
}

@Test func failedHealthCheckRestoresPreviousApp() throws {
    try withFixture { installed, candidate, backup in
        let transaction = try AppUpdateTransaction(
            installedApp: installed,
            candidateApp: candidate,
            backupApp: backup
        )
        #expect(throws: AppUpdateTransactionError.self) {
            try transaction.execute(
                installedValidator: { try requireMarker("old", at: $0) },
                candidateValidator: { try requireMarker("new", at: $0) },
                healthCheck: { _ in false }
            )
        }
        #expect(try marker(installed) == "old")
        #expect(!FileManager.default.fileExists(atPath: backup.path))
    }
}

@Test func invalidStagedCopyDoesNotMoveInstalledApp() throws {
    try withFixture { installed, candidate, backup in
        let transaction = try AppUpdateTransaction(
            installedApp: installed,
            candidateApp: candidate,
            backupApp: backup
        )
        #expect(throws: Error.self) {
            try transaction.execute(
                installedValidator: { _ in },
                candidateValidator: { app in
                    if try marker(app) == "new" { throw CocoaError(.fileReadCorruptFile) }
                },
                healthCheck: { _ in true }
            )
        }
        #expect(try marker(installed) == "old")
        #expect(!FileManager.default.fileExists(atPath: backup.path))
    }
}

@Test func existingBackupAndConcurrentLockFailClosed() throws {
    try withFixture { installed, candidate, backup in
        try makeApp(backup, marker: "preserved")
        let transaction = try AppUpdateTransaction(
            installedApp: installed,
            candidateApp: candidate,
            backupApp: backup
        )
        #expect(throws: AppUpdateTransactionError.backupAlreadyExists) {
            try transaction.execute(
                installedValidator: { _ in },
                candidateValidator: { _ in },
                healthCheck: { _ in true }
            )
        }
        #expect(try marker(backup) == "preserved")
    }

    try withFixture { installed, candidate, backup in
        let lock = installed.deletingLastPathComponent().appendingPathComponent(
            ".AI2Apps.app.update.lock"
        )
        FileManager.default.createFile(atPath: lock.path, contents: Data(), attributes: nil)
        let transaction = try AppUpdateTransaction(
            installedApp: installed,
            candidateApp: candidate,
            backupApp: backup
        )
        #expect(throws: AppUpdateTransactionError.updateInProgress) {
            try transaction.execute(
                installedValidator: { _ in },
                candidateValidator: { _ in },
                healthCheck: { _ in true }
            )
        }
        #expect(try marker(installed) == "old")
    }
}
