import Foundation

public struct RuntimeArtifact: Codable, Equatable, Sendable {
    public var relativePath: String
    public var sha256: String
    public var size: UInt64

    enum CodingKeys: String, CodingKey {
        case relativePath = "relative_path"
        case sha256
        case size
    }

    public init(relativePath: String, sha256: String, size: UInt64) {
        self.relativePath = relativePath
        self.sha256 = sha256
        self.size = size
    }

    public func validate() throws {
        guard !relativePath.isEmpty,
              !relativePath.hasPrefix("/"),
              !relativePath.split(separator: "/").contains("..") else {
            throw ContractError.invalidField(field: "artifacts.relative_path", reason: "must be a safe relative path")
        }
        guard sha256.count == 64,
              sha256.unicodeScalars.allSatisfy({ scalar in
                  (scalar.value >= 48 && scalar.value <= 57) ||
                      (scalar.value >= 97 && scalar.value <= 102)
              }) else {
            throw ContractError.invalidField(field: "artifacts.sha256", reason: "must be a lowercase SHA-256 digest")
        }
        guard size > 0 else {
            throw ContractError.invalidField(field: "artifacts.size", reason: "must be positive")
        }
    }
}

public struct RuntimeManifest: ValidatedContract, Equatable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var runtimeVersion: String
    public var platform: String
    public var architecture: String
    public var entrypoint: String
    public var minimumShellProtocol: Int
    public var minimumLocalAPIVersion: Int
    public var artifacts: [RuntimeArtifact]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case runtimeVersion = "runtime_version"
        case platform
        case architecture
        case entrypoint
        case minimumShellProtocol = "minimum_shell_protocol"
        case minimumLocalAPIVersion = "minimum_local_api_version"
        case artifacts
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        runtimeVersion: String,
        platform: String,
        architecture: String,
        entrypoint: String,
        minimumShellProtocol: Int,
        minimumLocalAPIVersion: Int,
        artifacts: [RuntimeArtifact]
    ) {
        self.schemaVersion = schemaVersion
        self.runtimeVersion = runtimeVersion
        self.platform = platform
        self.architecture = architecture
        self.entrypoint = entrypoint
        self.minimumShellProtocol = minimumShellProtocol
        self.minimumLocalAPIVersion = minimumLocalAPIVersion
        self.artifacts = artifacts
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(contract: "runtime-manifest", version: schemaVersion)
        }
        guard !runtimeVersion.isEmpty else {
            throw ContractError.invalidField(field: "runtime_version", reason: "must not be empty")
        }
        guard platform == "macos", architecture == "arm64" else {
            throw ContractError.invalidField(field: "platform", reason: "v1 supports macos arm64")
        }
        guard !entrypoint.isEmpty, !entrypoint.hasPrefix("/"), !entrypoint.contains("..") else {
            throw ContractError.invalidField(field: "entrypoint", reason: "must be a safe relative path")
        }
        guard minimumShellProtocol > 0, minimumLocalAPIVersion > 0 else {
            throw ContractError.invalidField(field: "protocol", reason: "minimum protocol versions must be positive")
        }
        guard !artifacts.isEmpty else {
            throw ContractError.invalidField(field: "artifacts", reason: "must not be empty")
        }
        var paths = Set<String>()
        for artifact in artifacts {
            try artifact.validate()
            guard paths.insert(artifact.relativePath).inserted else {
                throw ContractError.invalidField(field: "artifacts.relative_path", reason: "must be unique")
            }
        }
        guard paths.contains(entrypoint) else {
            throw ContractError.invalidField(field: "entrypoint", reason: "must reference an artifact")
        }
    }
}
