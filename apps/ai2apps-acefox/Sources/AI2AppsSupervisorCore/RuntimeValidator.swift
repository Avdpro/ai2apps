import AI2AppsContracts
import CryptoKit
import Foundation

public struct ValidatedRuntime: Equatable, Sendable {
    public let root: URL
    public let executable: URL
    public let version: String

    public init(root: URL, executable: URL, version: String) {
        self.root = root
        self.executable = executable
        self.version = version
    }
}

public struct RuntimeValidationPolicy: Equatable, Sendable {
    public var shellProtocolVersion: Int
    public var localAPIVersion: Int

    public init(shellProtocolVersion: Int = 1, localAPIVersion: Int = 1) {
        self.shellProtocolVersion = shellProtocolVersion
        self.localAPIVersion = localAPIVersion
    }
}

public struct RuntimeValidator: Sendable {
    public init() {}

    public func validate(
        manifest: RuntimeManifest,
        root: URL,
        policy: RuntimeValidationPolicy = RuntimeValidationPolicy()
    ) throws -> ValidatedRuntime {
        try manifest.validate()
        guard manifest.minimumShellProtocol <= policy.shellProtocolVersion else {
            throw ContractError.invalidField(field: "minimum_shell_protocol", reason: "requires a newer shell")
        }
        guard manifest.minimumLocalAPIVersion <= policy.localAPIVersion else {
            throw ContractError.invalidField(field: "minimum_local_api_version", reason: "requires a newer Local API")
        }

        let canonicalRoot = root.standardizedFileURL.resolvingSymlinksInPath()
        for artifact in manifest.artifacts {
            let url = root.appendingPathComponent(artifact.relativePath)
            let canonicalURL = url.standardizedFileURL.resolvingSymlinksInPath()
            guard canonicalURL.path.hasPrefix(canonicalRoot.path + "/") else {
                throw ContractError.invalidField(field: "artifacts.relative_path", reason: "escapes the runtime root")
            }
            let attributes = try FileManager.default.attributesOfItem(atPath: canonicalURL.path)
            guard let type = attributes[.type] as? FileAttributeType, type == .typeRegular else {
                throw ContractError.invalidField(field: artifact.relativePath, reason: "must be a regular file")
            }
            let size = (attributes[.size] as? NSNumber)?.uint64Value
            guard size == artifact.size else {
                throw ContractError.invalidField(field: artifact.relativePath, reason: "size does not match manifest")
            }
            guard try sha256(of: canonicalURL) == artifact.sha256 else {
                throw ContractError.invalidField(field: artifact.relativePath, reason: "SHA-256 does not match manifest")
            }
        }

        let executable = root.appendingPathComponent(manifest.entrypoint)
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw ContractError.invalidField(field: "entrypoint", reason: "is not executable")
        }
        return ValidatedRuntime(root: canonicalRoot, executable: executable, version: manifest.runtimeVersion)
    }

    private func sha256(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
