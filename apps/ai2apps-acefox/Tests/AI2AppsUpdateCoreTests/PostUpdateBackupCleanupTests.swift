import AI2AppsUpdateCore
import Foundation
import Testing

private func withCleanupFixture(_ body: (URL) throws -> Void) throws {
    let root = FileManager.default.temporaryDirectory.appendingPathComponent(
        "ai2apps-backup-cleanup-tests-\(UUID().uuidString)",
        isDirectory: true
    )
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: root) }
    try body(root)
}

@Test func postUpdateCleanupRemovesDerivedBackup() throws {
    try withCleanupFixture { root in
        let installed = root.appendingPathComponent("AI2Apps.app", isDirectory: true)
        let backup = root.appendingPathComponent("AI2Apps.previous.app", isDirectory: true)
        try FileManager.default.createDirectory(at: installed, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: backup, withIntermediateDirectories: true)

        let cleanup = try PostUpdateBackupCleanup(installedApp: installed)
        #expect(cleanup.backupApp == backup)
        #expect(try cleanup.removeIfPresent())
        #expect(!FileManager.default.fileExists(atPath: backup.path))
    }
}

@Test func postUpdateCleanupIsNoOpWithoutBackup() throws {
    try withCleanupFixture { root in
        let installed = root.appendingPathComponent("Renamed AI2Apps.app", isDirectory: true)
        try FileManager.default.createDirectory(at: installed, withIntermediateDirectories: true)

        let cleanup = try PostUpdateBackupCleanup(installedApp: installed)
        #expect(cleanup.backupApp.lastPathComponent == "Renamed AI2Apps.previous.app")
        #expect(try !cleanup.removeIfPresent())
    }
}

@Test func postUpdateCleanupRejectsSymbolicLink() throws {
    try withCleanupFixture { root in
        let installed = root.appendingPathComponent("AI2Apps.app", isDirectory: true)
        let unrelated = root.appendingPathComponent("unrelated", isDirectory: true)
        let backup = root.appendingPathComponent("AI2Apps.previous.app", isDirectory: true)
        try FileManager.default.createDirectory(at: installed, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: unrelated, withIntermediateDirectories: true)
        try FileManager.default.createSymbolicLink(at: backup, withDestinationURL: unrelated)

        let cleanup = try PostUpdateBackupCleanup(installedApp: installed)
        #expect(throws: PostUpdateBackupCleanupError.invalidBackup) {
            try cleanup.removeIfPresent()
        }
        #expect(FileManager.default.fileExists(atPath: unrelated.path))
    }
}

@Test func postUpdateCleanupRejectsNonAppPath() throws {
    #expect(throws: PostUpdateBackupCleanupError.invalidInstalledApp) {
        try PostUpdateBackupCleanup(installedApp: URL(fileURLWithPath: "/Applications/AI2Apps"))
    }
}
