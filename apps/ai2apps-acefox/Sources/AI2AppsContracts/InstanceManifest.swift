import Foundation

public struct ProtocolRange: Codable, Equatable, Sendable {
    public var minimum: Int
    public var maximum: Int

    public init(minimum: Int, maximum: Int) {
        self.minimum = minimum
        self.maximum = maximum
    }

    public func validate(field: String) throws {
        guard minimum > 0, maximum >= minimum else {
            throw ContractError.invalidField(field: field, reason: "requires 0 < minimum <= maximum")
        }
    }
}

public struct InstanceManifest: ValidatedContract, Equatable {
    public static let currentSchemaVersion = 1

    public var schemaVersion: Int
    public var instanceID: InstanceID
    public var displayName: String
    public var bundleIdentifier: String
    public var helperBundleIdentifier: String
    public var helperServiceName: String
    public var shellProtocol: ProtocolRange
    public var helperProtocol: ProtocolRange
    public var defaultLocalConfiguration: LocalConfiguration

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case instanceID = "instance_id"
        case displayName = "display_name"
        case bundleIdentifier = "bundle_identifier"
        case helperBundleIdentifier = "helper_bundle_identifier"
        case helperServiceName = "helper_service_name"
        case shellProtocol = "shell_protocol"
        case helperProtocol = "helper_protocol"
        case defaultLocalConfiguration = "default_local_configuration"
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        instanceID: InstanceID,
        displayName: String,
        bundleIdentifier: String,
        helperBundleIdentifier: String,
        helperServiceName: String,
        shellProtocol: ProtocolRange = .init(minimum: 1, maximum: 1),
        helperProtocol: ProtocolRange = .init(minimum: 1, maximum: 1),
        defaultLocalConfiguration: LocalConfiguration = .init()
    ) {
        self.schemaVersion = schemaVersion
        self.instanceID = instanceID
        self.displayName = displayName
        self.bundleIdentifier = bundleIdentifier
        self.helperBundleIdentifier = helperBundleIdentifier
        self.helperServiceName = helperServiceName
        self.shellProtocol = shellProtocol
        self.helperProtocol = helperProtocol
        self.defaultLocalConfiguration = defaultLocalConfiguration
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(contract: "instance-manifest", version: schemaVersion)
        }
        guard !displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ContractError.invalidField(field: "display_name", reason: "must not be empty")
        }
        try Self.validateBundleIdentifier(bundleIdentifier, field: "bundle_identifier")
        try Self.validateBundleIdentifier(helperBundleIdentifier, field: "helper_bundle_identifier")
        guard helperBundleIdentifier != bundleIdentifier else {
            throw ContractError.invalidField(field: "helper_bundle_identifier", reason: "must differ from the app bundle identifier")
        }
        try Self.validateBundleIdentifier(helperServiceName, field: "helper_service_name")
        try shellProtocol.validate(field: "shell_protocol")
        try helperProtocol.validate(field: "helper_protocol")
        try defaultLocalConfiguration.validate()
    }

    private static func validateBundleIdentifier(_ value: String, field: String) throws {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count >= 2,
              parts.allSatisfy({ part in
                  !part.isEmpty && part.unicodeScalars.allSatisfy { scalar in
                      (scalar.value >= 65 && scalar.value <= 90) ||
                          (scalar.value >= 97 && scalar.value <= 122) ||
                          (scalar.value >= 48 && scalar.value <= 57) || scalar == "-"
                  }
              }) else {
            throw ContractError.invalidField(field: field, reason: "must be a reverse-DNS identifier")
        }
    }
}
