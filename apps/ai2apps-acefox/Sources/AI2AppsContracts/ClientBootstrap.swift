import Foundation

public struct ClientBootstrap: Codable, Equatable, Sendable {
    public var status: String
    public var product: String
    public var productVersion: String
    public var apiVersion: Int
    public var instanceID: InstanceID?
    public var installationID: String?
    public var bootID: UUID?
    public var shellPath: String
    public var capabilities: [String]

    enum CodingKeys: String, CodingKey {
        case status
        case product
        case productVersion = "product_version"
        case apiVersion = "api_version"
        case instanceID = "instance_id"
        case installationID = "installation_id"
        case bootID = "boot_id"
        case shellPath = "shell_path"
        case capabilities
    }

    public init(
        status: String,
        product: String,
        productVersion: String,
        apiVersion: Int,
        instanceID: InstanceID?,
        installationID: String?,
        bootID: UUID?,
        shellPath: String,
        capabilities: [String]
    ) {
        self.status = status
        self.product = product
        self.productVersion = productVersion
        self.apiVersion = apiVersion
        self.instanceID = instanceID
        self.installationID = installationID
        self.bootID = bootID
        self.shellPath = shellPath
        self.capabilities = capabilities
    }

    public func validate(expectedInstanceID: InstanceID, expectedBootID: UUID) throws {
        guard status == "ready" else {
            throw ContractError.invalidField(field: "bootstrap.status", reason: "must be ready")
        }
        guard product == "ai2apps", apiVersion == 1 else {
            throw ContractError.invalidField(field: "bootstrap.protocol", reason: "unsupported Local API")
        }
        guard instanceID == expectedInstanceID else {
            throw ContractError.identityMismatch(
                expected: expectedInstanceID.rawValue,
                actual: instanceID?.rawValue ?? "missing"
            )
        }
        guard bootID == expectedBootID else {
            throw ContractError.invalidField(field: "bootstrap.boot_id", reason: "does not match the supervised process")
        }
        guard shellPath.hasPrefix("/"), !shellPath.hasPrefix("//") else {
            throw ContractError.invalidField(field: "bootstrap.shell_path", reason: "must be an absolute URL path")
        }
    }
}
