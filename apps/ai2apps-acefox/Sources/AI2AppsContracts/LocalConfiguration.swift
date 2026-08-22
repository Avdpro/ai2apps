import Foundation

public enum PortMode: String, Codable, Sendable {
    case automatic
    case fixed
}

public struct LocalConfiguration: ValidatedContract, Equatable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var bindAddress: String
    public var portMode: PortMode
    public var configuredPort: Int?
    public var startAtLogin: Bool
    public var autoRestart: Bool

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case bindAddress = "bind_address"
        case portMode = "port_mode"
        case configuredPort = "configured_port"
        case startAtLogin = "start_at_login"
        case autoRestart = "auto_restart"
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        bindAddress: String = "127.0.0.1",
        portMode: PortMode = .automatic,
        configuredPort: Int? = nil,
        startAtLogin: Bool = true,
        autoRestart: Bool = true
    ) {
        self.schemaVersion = schemaVersion
        self.bindAddress = bindAddress
        self.portMode = portMode
        self.configuredPort = configuredPort
        self.startAtLogin = startAtLogin
        self.autoRestart = autoRestart
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decode(Int.self, forKey: .schemaVersion)
        bindAddress = try container.decode(String.self, forKey: .bindAddress)
        portMode = try container.decode(PortMode.self, forKey: .portMode)
        configuredPort = try container.decodeIfPresent(Int.self, forKey: .configuredPort)
        startAtLogin = try container.decode(Bool.self, forKey: .startAtLogin)
        autoRestart = try container.decode(Bool.self, forKey: .autoRestart)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(schemaVersion, forKey: .schemaVersion)
        try container.encode(bindAddress, forKey: .bindAddress)
        try container.encode(portMode, forKey: .portMode)
        try container.encodeIfPresent(configuredPort, forKey: .configuredPort)
        try container.encode(startAtLogin, forKey: .startAtLogin)
        try container.encode(autoRestart, forKey: .autoRestart)
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(contract: "local-config", version: schemaVersion)
        }
        guard bindAddress == "127.0.0.1" else {
            throw ContractError.invalidField(field: "bind_address", reason: "v1 only permits 127.0.0.1")
        }
        switch portMode {
        case .automatic:
            guard configuredPort == nil else {
                throw ContractError.invalidField(field: "configured_port", reason: "must be absent in automatic mode")
            }
        case .fixed:
            guard let configuredPort else {
                throw ContractError.invalidField(field: "configured_port", reason: "is required in fixed mode")
            }
            try Self.validateUserPort(configuredPort, field: "configured_port")
        }
    }

    public var launchPort: Int {
        portMode == .automatic ? 0 : configuredPort ?? 0
    }

    public static func validateUserPort(_ port: Int, field: String) throws {
        guard (1024...65535).contains(port) else {
            throw ContractError.invalidField(field: field, reason: "must be between 1024 and 65535")
        }
    }
}
