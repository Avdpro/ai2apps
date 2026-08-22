import Foundation

public struct InstanceID: Codable, Hashable, Sendable, CustomStringConvertible {
    public let rawValue: String

    public init(rawValue: String) throws {
        guard (1...64).contains(rawValue.utf8.count) else {
            throw ContractError.invalidField(field: "instance_id", reason: "must contain 1 to 64 ASCII characters")
        }
        guard rawValue.unicodeScalars.allSatisfy({ scalar in
            (scalar.value >= 97 && scalar.value <= 122) ||
                (scalar.value >= 48 && scalar.value <= 57) ||
                scalar == "-" || scalar == "."
        }) else {
            throw ContractError.invalidField(field: "instance_id", reason: "must use lowercase ASCII letters, digits, dots, or hyphens")
        }
        guard let first = rawValue.unicodeScalars.first,
              let last = rawValue.unicodeScalars.last,
              Self.isAlphaNumeric(first),
              Self.isAlphaNumeric(last) else {
            throw ContractError.invalidField(field: "instance_id", reason: "must begin and end with a letter or digit")
        }
        guard !rawValue.contains("..") else {
            throw ContractError.invalidField(field: "instance_id", reason: "must not contain consecutive dots")
        }
        self.rawValue = rawValue
    }

    public init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer().decode(String.self)
        try self.init(rawValue: value)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    public var description: String { rawValue }

    private static func isAlphaNumeric(_ scalar: UnicodeScalar) -> Bool {
        (scalar.value >= 97 && scalar.value <= 122) ||
            (scalar.value >= 48 && scalar.value <= 57)
    }
}

public struct InstancePaths: Equatable, Sendable {
    public let supportRoot: URL
    public let cacheRoot: URL
    public let storageContainerDirectory: URL?

    public init(
        instanceID: InstanceID,
        homeDirectory: URL = FileManager.default.homeDirectoryForCurrentUser,
        containerDirectory: URL? = nil
    ) {
        storageContainerDirectory = containerDirectory?.standardizedFileURL
        let library = storageContainerDirectory?.appendingPathComponent(
            "Library",
            isDirectory: true
        ) ?? homeDirectory.appendingPathComponent("Library", isDirectory: true)
        supportRoot = library
            .appendingPathComponent("Application Support/AI2Apps/instances", isDirectory: true)
            .appendingPathComponent(instanceID.rawValue, isDirectory: true)
        cacheRoot = library
            .appendingPathComponent("Caches/AI2Apps/instances", isDirectory: true)
            .appendingPathComponent(instanceID.rawValue, isDirectory: true)
    }

    public var isContainerBacked: Bool { storageContainerDirectory != nil }

    public static func packaged(
        instanceID: InstanceID,
        bundle: Bundle = .main,
        fileManager: FileManager = .default
    ) throws -> Self {
        guard let groupIdentifier = bundle.object(
            forInfoDictionaryKey: "AI2AppsApplicationGroupIdentifier"
        ) as? String else {
            return Self(instanceID: instanceID)
        }
        guard (3...255).contains(groupIdentifier.utf8.count),
              groupIdentifier.unicodeScalars.allSatisfy({ scalar in
                  (scalar.value >= 65 && scalar.value <= 90) ||
                      (scalar.value >= 97 && scalar.value <= 122) ||
                      (scalar.value >= 48 && scalar.value <= 57) ||
                      scalar == "." || scalar == "-"
              }),
              !groupIdentifier.contains(".."),
              let container = fileManager.containerURL(
                  forSecurityApplicationGroupIdentifier: groupIdentifier
              ) else {
            throw ContractError.invalidField(
                field: "application_group",
                reason: "the signed instance container is unavailable"
            )
        }
        return Self(instanceID: instanceID, containerDirectory: container)
    }

    public var configDirectory: URL { supportRoot.appendingPathComponent("config", isDirectory: true) }
    public var dataDirectory: URL { supportRoot.appendingPathComponent("data", isDirectory: true) }
    public var runtimeDirectory: URL { supportRoot.appendingPathComponent("runtime", isDirectory: true) }
    public var logDirectory: URL { supportRoot.appendingPathComponent("logs", isDirectory: true) }
    public var diagnosticsDirectory: URL {
        supportRoot.appendingPathComponent("diagnostics", isDirectory: true)
    }
    public var runDirectory: URL { supportRoot.appendingPathComponent("run", isDirectory: true) }
    public var downloadsDirectory: URL { supportRoot.appendingPathComponent("downloads", isDirectory: true) }
    public var browserProfilesDirectory: URL { supportRoot.appendingPathComponent("browser-profiles", isDirectory: true) }
    /// Model checkpoints and download caches are private to this instance.
    /// Other instances consume model capability through an authenticated Local
    /// upstream and never receive filesystem access to this directory.
    public var instanceModelWeightsDirectory: URL {
        cacheRoot.appendingPathComponent("model-weights", isDirectory: true)
    }
    public var instanceHuggingFaceHomeDirectory: URL {
        dataDirectory.appendingPathComponent("huggingface", isDirectory: true)
    }
    public var instanceHuggingFaceHubDirectory: URL {
        instanceModelWeightsDirectory.appendingPathComponent("huggingface/hub", isDirectory: true)
    }
    public var privateDirectories: [URL] {
        [
            supportRoot,
            configDirectory,
            dataDirectory,
            instanceHuggingFaceHomeDirectory,
            runtimeDirectory,
            logDirectory,
            diagnosticsDirectory,
            runDirectory,
            downloadsDirectory,
            browserProfilesDirectory,
            cacheRoot,
            instanceModelWeightsDirectory,
            instanceHuggingFaceHubDirectory,
        ]
    }

    public func preparePrivateDirectories(
        fileManager: FileManager = .default
    ) throws {
        for directory in privateDirectories {
            try fileManager.createDirectory(
                at: directory,
                withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
            try fileManager.setAttributes(
                [.posixPermissions: 0o700],
                ofItemAtPath: directory.path
            )
        }
    }
}
