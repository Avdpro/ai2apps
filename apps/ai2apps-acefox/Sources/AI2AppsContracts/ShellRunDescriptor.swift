import Foundation

public struct ShellRunDescriptor: ValidatedContract, Equatable, Sendable {
    public let version: Int
    public let instanceID: InstanceID
    public let processID: Int32
    public let appBundlePath: String
    public let executablePath: String
    public let publishedAt: Date

    public init(
        instanceID: InstanceID,
        processID: Int32,
        appBundlePath: String,
        executablePath: String,
        publishedAt: Date = Date()
    ) {
        version = 1
        self.instanceID = instanceID
        self.processID = processID
        self.appBundlePath = appBundlePath
        self.executablePath = executablePath
        self.publishedAt = publishedAt
    }

    enum CodingKeys: String, CodingKey {
        case version
        case instanceID = "instance_id"
        case processID = "pid"
        case appBundlePath = "app_bundle_path"
        case executablePath = "executable_path"
        case publishedAt = "published_at"
    }

    public func validate() throws {
        guard version == 1 else {
            throw ContractError.unsupportedSchema(contract: "shell-run-descriptor", version: version)
        }
        guard processID > 1 else {
            throw ContractError.invalidField(field: "pid", reason: "must identify a user process")
        }
        try Self.validateAbsolutePath(appBundlePath, field: "app_bundle_path")
        try Self.validateAbsolutePath(executablePath, field: "executable_path")
    }

    private static func validateAbsolutePath(_ path: String, field: String) throws {
        guard (2...4096).contains(path.utf8.count), path.hasPrefix("/"),
              !path.contains("\n"), !path.contains("\r"), !path.contains("\0") else {
            throw ContractError.invalidField(field: field, reason: "must be a bounded absolute path")
        }
    }
}
