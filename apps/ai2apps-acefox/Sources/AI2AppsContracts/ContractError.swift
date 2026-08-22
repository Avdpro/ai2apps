import Foundation

public enum ContractError: Error, Equatable, Sendable, CustomStringConvertible {
    case unsupportedSchema(contract: String, version: Int)
    case invalidField(field: String, reason: String)
    case identityMismatch(expected: String, actual: String)

    public var description: String {
        switch self {
        case .unsupportedSchema(let contract, let version):
            return "Unsupported \(contract) schema version: \(version)"
        case .invalidField(let field, let reason):
            return "Invalid \(field): \(reason)"
        case .identityMismatch(let expected, let actual):
            return "Instance identity mismatch: expected \(expected), got \(actual)"
        }
    }
}

public protocol ValidatedContract: Codable, Sendable {
    func validate() throws
}
