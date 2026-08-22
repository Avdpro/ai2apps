import Foundation

public struct LocalRunDescriptor: ValidatedContract, Equatable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var instanceID: InstanceID
    public var processID: Int32
    public var configuredPort: Int?
    public var actualPort: Int
    public var bootID: UUID
    public var runtimeVersion: String
    public var startedAt: Date

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case instanceID = "instance_id"
        case processID = "pid"
        case configuredPort = "configured_port"
        case actualPort = "actual_port"
        case bootID = "boot_id"
        case runtimeVersion = "runtime_version"
        case startedAt = "started_at"
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        instanceID: InstanceID,
        processID: Int32,
        configuredPort: Int?,
        actualPort: Int,
        bootID: UUID,
        runtimeVersion: String,
        startedAt: Date
    ) {
        self.schemaVersion = schemaVersion
        self.instanceID = instanceID
        self.processID = processID
        self.configuredPort = configuredPort
        self.actualPort = actualPort
        self.bootID = bootID
        self.runtimeVersion = runtimeVersion
        self.startedAt = startedAt
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(contract: "local-run-descriptor", version: schemaVersion)
        }
        guard processID > 0 else {
            throw ContractError.invalidField(field: "pid", reason: "must be positive")
        }
        if let configuredPort {
            try LocalConfiguration.validateUserPort(configuredPort, field: "configured_port")
        }
        try LocalConfiguration.validateUserPort(actualPort, field: "actual_port")
        guard !runtimeVersion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ContractError.invalidField(field: "runtime_version", reason: "must not be empty")
        }
        guard startedAt <= Date().addingTimeInterval(300) else {
            throw ContractError.invalidField(field: "started_at", reason: "must not be more than five minutes in the future")
        }
    }

    public func validate(expectedInstanceID: InstanceID) throws {
        try validate()
        guard instanceID == expectedInstanceID else {
            throw ContractError.identityMismatch(expected: expectedInstanceID.rawValue, actual: instanceID.rawValue)
        }
    }
}
