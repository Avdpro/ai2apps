import Foundation

public enum HelperPhase: String, Codable, CaseIterable, Sendable {
    case initializing
    case checking
    case starting
    case ready
    case degraded
    case restarting
    case stopping
    case stopped
    case failed
    case helperExiting = "helper_exiting"
}

public struct HelperStatus: ValidatedContract, Equatable, Sendable {
    public var schemaVersion: Int
    public var instanceID: InstanceID
    public var helperProcessID: Int32
    public var phase: HelperPhase
    public var message: String
    public var actualPort: Int?
    public var errorCode: String?
    public var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case instanceID = "instance_id"
        case helperProcessID = "helper_pid"
        case phase
        case message
        case actualPort = "actual_port"
        case errorCode = "error_code"
        case updatedAt = "updated_at"
    }

    public init(
        schemaVersion: Int = 1,
        instanceID: InstanceID,
        helperProcessID: Int32 = ProcessInfo.processInfo.processIdentifier,
        phase: HelperPhase,
        message: String,
        actualPort: Int? = nil,
        errorCode: String? = nil,
        updatedAt: Date = Date()
    ) {
        self.schemaVersion = schemaVersion
        self.instanceID = instanceID
        self.helperProcessID = helperProcessID
        self.phase = phase
        self.message = message
        self.actualPort = actualPort
        self.errorCode = errorCode
        self.updatedAt = updatedAt
    }

    public func validate() throws {
        guard schemaVersion == 1 else {
            throw ContractError.unsupportedSchema(contract: "helper-status", version: schemaVersion)
        }
        guard helperProcessID > 0 else {
            throw ContractError.invalidField(field: "helper_pid", reason: "must be positive")
        }
        guard (1...256).contains(message.utf8.count),
              !message.contains("\n"), !message.contains("\r") else {
            throw ContractError.invalidField(
                field: "helper_status.message",
                reason: "must be a single line of 1 to 256 bytes"
            )
        }
        if let actualPort, !(1024...65_535).contains(actualPort) {
            throw ContractError.invalidField(field: "actual_port", reason: "must be 1024 to 65535")
        }
        if let errorCode {
            guard (1...64).contains(errorCode.utf8.count),
                  errorCode.unicodeScalars.allSatisfy({ scalar in
                      (scalar.value >= 97 && scalar.value <= 122) ||
                          (scalar.value >= 48 && scalar.value <= 57) ||
                          scalar == "_" || scalar == "-" || scalar == "."
                  }) else {
                throw ContractError.invalidField(
                    field: "helper_status.error_code",
                    reason: "must be lowercase ASCII identifier"
                )
            }
        }
    }
}
