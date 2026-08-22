import Foundation

struct ModelAdapterPackageRequest: Codable, Sendable {
    let wheelPath: String
}

struct ModelAdapterPackageListResponse: Codable, Sendable {
    let items: [ModelAdapterPackageDTO]
}

struct ModelAdapterCatalogInstallRequest: Codable, Sendable {
    let packageName: String
    let version: String?
}

struct ModelAdapterCheckpointInstallRequest: Codable, Sendable {
    let packageName: String
    let packageVersion: String
    let recipeId: String
    let memoryTier: String
}

struct ModelAdapterCheckpointInstallResponse: Decodable, Sendable {
    let success: Bool
}

struct ModelAdapterCatalogResponse: Codable, Sendable {
    let metadataVersion: Int
    let generatedAt: String
    let expiresAt: String
    let items: [ModelAdapterCatalogItemDTO]
}

struct ModelAdapterCatalogItemDTO: Codable, Identifiable, Sendable {
    var id: String { "\(packageId)@\(version)" }

    let packageId: String
    let displayName: String
    let version: String
    let status: String
    let statusReason: String?
    let installedVersion: String?
    let updateAvailable: Bool
    let checkpoints: [ModelAdapterCheckpointDTO]
}

struct ModelAdapterCheckpointDTO: Codable, Identifiable, Sendable {
    var id: String { "\(source):\(repoId)@\(revision)" }

    let source: String
    let repoId: String
    let revision: String
    let displayName: String
    let estimatedSizeBytes: Int64?
    let installMode: String
    let recipeId: String?
    let packageId: String
    let packageVersion: String
}

struct ModelAdapterPackageDTO: Codable, Identifiable, Sendable {
    var id: String { normalizedName }

    let name: String
    let normalizedName: String
    let version: String
    let sha256: String
    let path: String?
    let wheelPath: String?
    let entryPoints: [String: String]
    let requirements: [String]
    let restartRequired: Bool?
}

struct ModelAdapterPackageMutationResponse: Codable, Sendable {
    let name: String
    let normalizedName: String
    let version: String
    let operation: String
    let previousVersion: String?
    let restartRequired: Bool
    let catalogMetadataVersion: Int?
}
