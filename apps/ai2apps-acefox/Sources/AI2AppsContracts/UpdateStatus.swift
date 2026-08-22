import Foundation

public enum UpdatePhase: String, Codable, CaseIterable, Sendable {
    case idle
    case checking
    case ready
    case installing
    case succeeded
    case failed
}

public struct UpdateStatus: ValidatedContract, Equatable, Sendable {
    public var schemaVersion: Int
    public var instanceID: InstanceID
    public var phase: UpdatePhase
    public var currentBuild: String
    public var candidateBuild: String?
    public var message: String
    public var errorCode: String?
    public var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case instanceID = "instance_id"
        case phase
        case currentBuild = "current_build"
        case candidateBuild = "candidate_build"
        case message
        case errorCode = "error_code"
        case updatedAt = "updated_at"
    }

    public init(
        schemaVersion: Int = 1,
        instanceID: InstanceID,
        phase: UpdatePhase,
        currentBuild: String,
        candidateBuild: String? = nil,
        message: String,
        errorCode: String? = nil,
        updatedAt: Date = Date()
    ) {
        self.schemaVersion = schemaVersion
        self.instanceID = instanceID
        self.phase = phase
        self.currentBuild = currentBuild
        self.candidateBuild = candidateBuild
        self.message = message
        self.errorCode = errorCode
        self.updatedAt = updatedAt
    }

    public func validate() throws {
        guard schemaVersion == 1 else {
            throw ContractError.unsupportedSchema(contract: "update-status", version: schemaVersion)
        }
        let current = try Self.positiveBuild(currentBuild, field: "current_build")
        let candidate = try candidateBuild.map {
            try Self.positiveBuild($0, field: "candidate_build")
        }
        switch phase {
        case .idle, .checking:
            guard candidate == nil else {
                throw ContractError.invalidField(
                    field: "candidate_build",
                    reason: "must be absent before a candidate is ready"
                )
            }
        case .ready, .installing, .succeeded:
            guard let candidate, candidate > current else {
                throw ContractError.invalidField(
                    field: "candidate_build",
                    reason: "must be newer than current_build"
                )
            }
        case .failed:
            if let candidate, candidate <= current {
                throw ContractError.invalidField(
                    field: "candidate_build",
                    reason: "must be newer than current_build when present"
                )
            }
        }
        guard (1...256).contains(message.utf8.count),
              !message.contains("\n"), !message.contains("\r") else {
            throw ContractError.invalidField(
                field: "update_status.message",
                reason: "must be a single line of 1 to 256 bytes"
            )
        }
        if let errorCode {
            guard (1...64).contains(errorCode.utf8.count),
                  errorCode.unicodeScalars.allSatisfy({ scalar in
                      (scalar.value >= 97 && scalar.value <= 122) ||
                          (scalar.value >= 48 && scalar.value <= 57) ||
                          scalar == "_" || scalar == "-" || scalar == "."
                  }) else {
                throw ContractError.invalidField(
                    field: "update_status.error_code",
                    reason: "must be a lowercase ASCII identifier"
                )
            }
        }
    }

    private static func positiveBuild(_ value: String, field: String) throws -> Int {
        guard !value.isEmpty, value.allSatisfy({ $0.isASCII && $0.isNumber }),
              let number = Int(value), number > 0 else {
            throw ContractError.invalidField(field: field, reason: "must be a positive integer string")
        }
        return number
    }
}
