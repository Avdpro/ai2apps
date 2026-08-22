import Foundation

public enum LoginItemPhase: String, Codable, Sendable {
    case enabled
    case requiresApproval = "requires_approval"
    case notRegistered = "not_registered"
    case notFound = "not_found"
    case skippedReadOnly = "skipped_read_only"
    case skippedDevelopment = "skipped_development"
    case failed
}

public struct LoginItemStatus: ValidatedContract, Equatable, Sendable {
    public static let currentSchemaVersion = 1

    public let schemaVersion: Int
    public let instanceID: InstanceID
    public let phase: LoginItemPhase
    public let updatedAt: Date
    public let errorCode: String?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case instanceID = "instance_id"
        case phase
        case updatedAt = "updated_at"
        case errorCode = "error_code"
    }

    public init(
        schemaVersion: Int = currentSchemaVersion,
        instanceID: InstanceID,
        phase: LoginItemPhase,
        updatedAt: Date = Date(),
        errorCode: String? = nil
    ) {
        self.schemaVersion = schemaVersion
        self.instanceID = instanceID
        self.phase = phase
        self.updatedAt = updatedAt
        self.errorCode = errorCode
    }

    public func validate() throws {
        guard schemaVersion == Self.currentSchemaVersion else {
            throw ContractError.unsupportedSchema(
                contract: "login-item-status",
                version: schemaVersion
            )
        }
        if let errorCode {
            guard !errorCode.isEmpty, errorCode.utf8.count <= 64,
                  errorCode.unicodeScalars.allSatisfy({ scalar in
                      (scalar.value >= 97 && scalar.value <= 122) ||
                          (scalar.value >= 48 && scalar.value <= 57) ||
                          scalar == "_"
                  }) else {
                throw ContractError.invalidField(
                    field: "error_code",
                    reason: "must be a bounded lowercase machine code"
                )
            }
        }
        guard phase == .failed || errorCode == nil else {
            throw ContractError.invalidField(
                field: "error_code",
                reason: "is only allowed for failed status"
            )
        }
        guard phase != .failed || errorCode != nil else {
            throw ContractError.invalidField(
                field: "error_code",
                reason: "is required for failed status"
            )
        }
    }
}
