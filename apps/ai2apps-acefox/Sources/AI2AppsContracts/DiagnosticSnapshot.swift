import Foundation

public struct DiagnosticSnapshot: ValidatedContract, Equatable, Sendable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var generatedAt: Date
    public var instanceID: InstanceID
    public var productVersion: String
    public var runtimeVersion: String?
    public var operatingSystem: String
    public var architecture: String
    public var helperPhase: HelperPhase
    public var helperProcessID: Int32
    public var localProcessID: Int32?
    public var localBootID: UUID?
    public var portMode: PortMode
    public var configuredPort: Int?
    public var actualPort: Int?
    public var browserAgentCount: Int

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case generatedAt = "generated_at"
        case instanceID = "instance_id"
        case productVersion = "product_version"
        case runtimeVersion = "runtime_version"
        case operatingSystem = "operating_system"
        case architecture
        case helperPhase = "helper_phase"
        case helperProcessID = "helper_pid"
        case localProcessID = "local_pid"
        case localBootID = "local_boot_id"
        case portMode = "port_mode"
        case configuredPort = "configured_port"
        case actualPort = "actual_port"
        case browserAgentCount = "browser_agent_count"
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        generatedAt: Date = Date(),
        instanceID: InstanceID,
        productVersion: String,
        runtimeVersion: String?,
        operatingSystem: String,
        architecture: String,
        helperPhase: HelperPhase,
        helperProcessID: Int32,
        localProcessID: Int32?,
        localBootID: UUID?,
        portMode: PortMode,
        configuredPort: Int?,
        actualPort: Int?,
        browserAgentCount: Int
    ) {
        self.schemaVersion = schemaVersion
        self.generatedAt = generatedAt
        self.instanceID = instanceID
        self.productVersion = productVersion
        self.runtimeVersion = runtimeVersion
        self.operatingSystem = operatingSystem
        self.architecture = architecture
        self.helperPhase = helperPhase
        self.helperProcessID = helperProcessID
        self.localProcessID = localProcessID
        self.localBootID = localBootID
        self.portMode = portMode
        self.configuredPort = configuredPort
        self.actualPort = actualPort
        self.browserAgentCount = browserAgentCount
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(
                contract: "diagnostic-snapshot",
                version: schemaVersion
            )
        }
        try Self.validateText(productVersion, field: "product_version")
        if let runtimeVersion {
            try Self.validateText(runtimeVersion, field: "runtime_version")
        }
        try Self.validateText(operatingSystem, field: "operating_system")
        try Self.validateText(architecture, field: "architecture")
        guard helperProcessID > 0 else {
            throw ContractError.invalidField(field: "helper_pid", reason: "must be positive")
        }
        if let localProcessID, localProcessID <= 0 {
            throw ContractError.invalidField(field: "local_pid", reason: "must be positive")
        }
        if let configuredPort {
            try LocalConfiguration.validateUserPort(
                configuredPort,
                field: "configured_port"
            )
        }
        if let actualPort {
            try LocalConfiguration.validateUserPort(actualPort, field: "actual_port")
        }
        guard (0...1_024).contains(browserAgentCount) else {
            throw ContractError.invalidField(
                field: "browser_agent_count",
                reason: "must be 0 to 1024"
            )
        }
    }

    private static func validateText(_ value: String, field: String) throws {
        guard (1...256).contains(value.utf8.count),
              !value.contains("\n"),
              !value.contains("\r") else {
            throw ContractError.invalidField(
                field: field,
                reason: "must be a single line of 1 to 256 bytes"
            )
        }
    }
}
