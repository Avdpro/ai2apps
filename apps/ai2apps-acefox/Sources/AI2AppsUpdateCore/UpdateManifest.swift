import CryptoKit
import Foundation

public enum UpdateManifestError: Error, Equatable, CustomStringConvertible {
    case unsupportedSchema(Int)
    case invalidField(String)

    public var description: String {
        switch self {
        case .unsupportedSchema(let version):
            return "unsupported update manifest schema: \(version)"
        case .invalidField(let field):
            return "invalid update manifest field: \(field)"
        }
    }
}

public struct UpdateArtifact: Codable, Equatable, Sendable {
    public let urls: [URL]
    public let filename: String
    public let size: Int64
    public let sha256: String

    public init(url: URL, filename: String, size: Int64, sha256: String) {
        self.urls = [url]
        self.filename = filename
        self.size = size
        self.sha256 = sha256
    }

    public init(urls: [URL], filename: String, size: Int64, sha256: String) {
        self.urls = urls
        self.filename = filename
        self.size = size
        self.sha256 = sha256
    }

    enum CodingKeys: String, CodingKey {
        case url, urls, filename, size, sha256
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let mirrors = try container.decodeIfPresent([URL].self, forKey: .urls)
        let legacy = try container.decodeIfPresent(URL.self, forKey: .url)
        if let mirrors, !mirrors.isEmpty {
            urls = mirrors
        } else if let legacy {
            urls = [legacy]
        } else {
            throw DecodingError.keyNotFound(
                CodingKeys.urls,
                DecodingError.Context(
                    codingPath: decoder.codingPath,
                    debugDescription: "an artifact requires url or urls"
                )
            )
        }
        filename = try container.decode(String.self, forKey: .filename)
        size = try container.decode(Int64.self, forKey: .size)
        sha256 = try container.decode(String.self, forKey: .sha256)
    }

    public func encode(to encoder: Encoder) throws {
        guard let primaryURL = urls.first else {
            throw EncodingError.invalidValue(
                urls,
                EncodingError.Context(
                    codingPath: encoder.codingPath,
                    debugDescription: "an artifact requires at least one URL"
                )
            )
        }
        var container = encoder.container(keyedBy: CodingKeys.self)
        // Keep `url` during the protocol-1 migration so already shipped
        // single-source clients can still consume the first mirror.
        try container.encode(primaryURL, forKey: .url)
        try container.encode(urls, forKey: .urls)
        try container.encode(filename, forKey: .filename)
        try container.encode(size, forKey: .size)
        try container.encode(sha256, forKey: .sha256)
    }

    public func validate(field: String) throws {
        guard (1...4).contains(urls.count), Set(urls).count == urls.count else {
            throw UpdateManifestError.invalidField("\(field).urls")
        }
        for url in urls {
            guard url.scheme?.lowercased() == "https", url.host != nil,
                  url.user == nil, url.password == nil else {
                throw UpdateManifestError.invalidField("\(field).urls")
            }
        }
        guard (1...160).contains(filename.utf8.count),
              filename == URL(fileURLWithPath: filename).lastPathComponent,
              filename != ".", filename != "..", !filename.contains("/") else {
            throw UpdateManifestError.invalidField("\(field).filename")
        }
        guard size > 0 else { throw UpdateManifestError.invalidField("\(field).size") }
        guard sha256.count == 64,
              sha256.allSatisfy({ $0.isASCII && $0.isHexDigit && !$0.isUppercase }) else {
            throw UpdateManifestError.invalidField("\(field).sha256")
        }
    }
}

public struct UpdateRollout: Codable, Equatable, Sendable {
    public let id: String
    public let percentageBasisPoints: Int

    enum CodingKeys: String, CodingKey {
        case id
        case percentageBasisPoints = "percentage_basis_points"
    }

    public init(id: String, percentageBasisPoints: Int) {
        self.id = id
        self.percentageBasisPoints = percentageBasisPoints
    }

    public func validate() throws {
        guard (1...64).contains(id.utf8.count),
              id.unicodeScalars.allSatisfy({ $0.isASCII && ($0.properties.isAlphabetic || $0.properties.numericType != nil || $0 == "-" || $0 == "_") }) else {
            throw UpdateManifestError.invalidField("rollout.id")
        }
        guard (0...10_000).contains(percentageBasisPoints) else {
            throw UpdateManifestError.invalidField("rollout.percentage_basis_points")
        }
    }
}

public struct UpdateRelease: Codable, Equatable, Sendable {
    public let bundleIdentifier: String
    public let instanceID: String
    public let productVersion: String
    public let bundleVersion: String
    public let runtimeProfile: String
    public let minimumSystemVersion: String
    public let architectures: [String]
    public let rollout: UpdateRollout
    public let dmg: UpdateArtifact
    public let metadata: UpdateArtifact

    enum CodingKeys: String, CodingKey {
        case bundleIdentifier = "bundle_identifier"
        case instanceID = "instance_id"
        case productVersion = "product_version"
        case bundleVersion = "bundle_version"
        case runtimeProfile = "runtime_profile"
        case minimumSystemVersion = "minimum_system_version"
        case architectures, rollout, dmg, metadata
    }

    public init(
        bundleIdentifier: String,
        instanceID: String,
        productVersion: String,
        bundleVersion: String,
        runtimeProfile: String,
        minimumSystemVersion: String,
        architectures: [String],
        rollout: UpdateRollout,
        dmg: UpdateArtifact,
        metadata: UpdateArtifact
    ) {
        self.bundleIdentifier = bundleIdentifier
        self.instanceID = instanceID
        self.productVersion = productVersion
        self.bundleVersion = bundleVersion
        self.runtimeProfile = runtimeProfile
        self.minimumSystemVersion = minimumSystemVersion
        self.architectures = architectures
        self.rollout = rollout
        self.dmg = dmg
        self.metadata = metadata
    }

    public var build: Int? {
        guard !bundleVersion.isEmpty,
              bundleVersion.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
        return Int(bundleVersion)
    }

    public func validate() throws {
        guard !bundleIdentifier.isEmpty, bundleIdentifier.utf8.count <= 255 else {
            throw UpdateManifestError.invalidField("release.bundle_identifier")
        }
        guard !instanceID.isEmpty, instanceID.utf8.count <= 64 else {
            throw UpdateManifestError.invalidField("release.instance_id")
        }
        guard let build, build > 0 else {
            throw UpdateManifestError.invalidField("release.bundle_version")
        }
        guard (1...64).contains(productVersion.utf8.count),
              (1...64).contains(runtimeProfile.utf8.count),
              Self.versionComponents(minimumSystemVersion) != nil else {
            throw UpdateManifestError.invalidField("release.version")
        }
        guard (1...4).contains(architectures.count),
              architectures.allSatisfy({ ["arm64", "x86_64"].contains($0) }) else {
            throw UpdateManifestError.invalidField("release.architectures")
        }
        try rollout.validate()
        try dmg.validate(field: "release.dmg")
        try metadata.validate(field: "release.metadata")
        guard dmg.filename.hasSuffix(".dmg"), metadata.filename.hasSuffix(".json") else {
            throw UpdateManifestError.invalidField("release.artifact_filename")
        }
    }

    static func versionComponents(_ value: String) -> [Int]? {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard (1...3).contains(parts.count) else { return nil }
        let numbers = parts.compactMap { part -> Int? in
            guard !part.isEmpty, part.allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
            return Int(part)
        }
        return numbers.count == parts.count ? numbers : nil
    }
}

public struct UpdateManifest: Codable, Equatable, Sendable {
    public let schemaVersion: Int
    public let channel: String
    public let releases: [UpdateRelease]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case channel, releases
    }

    public init(schemaVersion: Int = 1, channel: String, releases: [UpdateRelease]) {
        self.schemaVersion = schemaVersion
        self.channel = channel
        self.releases = releases
    }

    public func validate() throws {
        guard schemaVersion == 1 else { throw UpdateManifestError.unsupportedSchema(schemaVersion) }
        guard (1...32).contains(channel.utf8.count),
              channel.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }) else {
            throw UpdateManifestError.invalidField("channel")
        }
        guard releases.count <= 32 else { throw UpdateManifestError.invalidField("releases") }
        try releases.forEach { try $0.validate() }
    }

    public func selectedRelease(
        bundleIdentifier: String,
        instanceID: String,
        currentBuild: Int,
        runtimeProfile: String,
        architecture: String,
        systemVersion: String,
        cohortID: String
    ) throws -> UpdateRelease? {
        try validate()
        guard let system = UpdateRelease.versionComponents(systemVersion) else {
            throw UpdateManifestError.invalidField("system_version")
        }
        return releases.filter { release in
            guard release.bundleIdentifier == bundleIdentifier,
                  release.instanceID == instanceID,
                  release.runtimeProfile == runtimeProfile,
                  release.architectures.contains(architecture),
                  let build = release.build, build > currentBuild,
                  let minimum = UpdateRelease.versionComponents(release.minimumSystemVersion),
                  Self.compare(system, minimum) >= 0 else { return false }
            return Self.cohortBucket(rolloutID: release.rollout.id, cohortID: cohortID)
                < release.rollout.percentageBasisPoints
        }.max { ($0.build ?? 0) < ($1.build ?? 0) }
    }

    public static func cohortBucket(rolloutID: String, cohortID: String) -> Int {
        let digest = SHA256.hash(data: Data("\(rolloutID):\(cohortID)".utf8))
        let prefix = digest.prefix(8).reduce(UInt64(0)) { ($0 << 8) | UInt64($1) }
        return Int(prefix % 10_000)
    }

    public static func loadOrCreateCohortID(at url: URL, fileManager: FileManager = .default) throws -> String {
        if fileManager.fileExists(atPath: url.path) {
            let value = try String(contentsOf: url, encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard UUID(uuidString: value) != nil else {
                throw UpdateManifestError.invalidField("cohort_id")
            }
            return value.lowercased()
        }
        let value = UUID().uuidString.lowercased()
        try fileManager.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        guard fileManager.createFile(
            atPath: url.path,
            contents: Data((value + "\n").utf8),
            attributes: [.posixPermissions: 0o600]
        ) else {
            let concurrent = try String(contentsOf: url, encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard UUID(uuidString: concurrent) != nil else {
                throw UpdateManifestError.invalidField("cohort_id")
            }
            return concurrent.lowercased()
        }
        try fileManager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
        return value
    }

    private static func compare(_ lhs: [Int], _ rhs: [Int]) -> Int {
        for index in 0..<max(lhs.count, rhs.count) {
            let left = index < lhs.count ? lhs[index] : 0
            let right = index < rhs.count ? rhs[index] : 0
            if left != right { return left < right ? -1 : 1 }
        }
        return 0
    }
}
