import AI2AppsContracts
import AI2AppsSupervisorCore
import CryptoKit
import Foundation
import Testing

private func digest(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}

@Test func runtimeValidatorAcceptsMatchingArtifact() throws {
    let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: root) }
    let executable = root.appendingPathComponent("bin/omlx")
    try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
    let data = Data("runtime".utf8)
    try data.write(to: executable)
    try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
    let manifest = RuntimeManifest(
        schemaVersion: 1,
        runtimeVersion: "1.0.0",
        platform: "macos",
        architecture: "arm64",
        entrypoint: "bin/omlx",
        minimumShellProtocol: 1,
        minimumLocalAPIVersion: 1,
        artifacts: [RuntimeArtifact(relativePath: "bin/omlx", sha256: digest(data), size: UInt64(data.count))]
    )

    let validated = try RuntimeValidator().validate(manifest: manifest, root: root)
    #expect(validated.executable.path == executable.path)
}

@Test func runtimeValidatorRejectsTamperedArtifact() throws {
    let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: root) }
    let executable = root.appendingPathComponent("omlx")
    try Data("tampered".utf8).write(to: executable)
    try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: executable.path)
    let manifest = RuntimeManifest(
        schemaVersion: 1,
        runtimeVersion: "1.0.0",
        platform: "macos",
        architecture: "arm64",
        entrypoint: "omlx",
        minimumShellProtocol: 1,
        minimumLocalAPIVersion: 1,
        artifacts: [RuntimeArtifact(relativePath: "omlx", sha256: String(repeating: "0", count: 64), size: 8)]
    )

    #expect(throws: ContractError.self) {
        try RuntimeValidator().validate(manifest: manifest, root: root)
    }
}
