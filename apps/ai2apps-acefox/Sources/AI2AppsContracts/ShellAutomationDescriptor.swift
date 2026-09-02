import Foundation

public struct ShellAutomationDescriptor: ValidatedContract, Equatable, Sendable {
    public let version: Int
    public let instanceID: InstanceID
    public let host: String
    public let port: Int
    public let token: String
    public let processID: Int32
    public let publishedAt: Date

    public init(
        instanceID: InstanceID,
        port: Int,
        token: String,
        processID: Int32,
        publishedAt: Date = Date()
    ) {
        version = 1
        self.instanceID = instanceID
        host = "127.0.0.1"
        self.port = port
        self.token = token
        self.processID = processID
        self.publishedAt = publishedAt
    }

    enum CodingKeys: String, CodingKey {
        case version = "schema_version"
        case instanceID = "instance_id"
        case host
        case port
        case token
        case processID = "pid"
        case publishedAt = "published_at"
    }

    public func validate() throws {
        guard version == 1 else {
            throw ContractError.unsupportedSchema(
                contract: "shell-automation-descriptor",
                version: version
            )
        }
        guard host == "127.0.0.1" else {
            throw ContractError.invalidField(
                field: "host",
                reason: "must be IPv4 loopback"
            )
        }
        guard (1024...65535).contains(port) else {
            throw ContractError.invalidField(
                field: "port",
                reason: "must be 1024 to 65535"
            )
        }
        guard token.count == 64,
              token.unicodeScalars.allSatisfy({ scalar in
                  (scalar.value >= 48 && scalar.value <= 57) ||
                      (scalar.value >= 97 && scalar.value <= 102)
              }) else {
            throw ContractError.invalidField(
                field: "token",
                reason: "must be a lowercase 256-bit hexadecimal token"
            )
        }
        guard processID > 1 else {
            throw ContractError.invalidField(
                field: "pid",
                reason: "must identify the Shell browser process"
            )
        }
    }
}
