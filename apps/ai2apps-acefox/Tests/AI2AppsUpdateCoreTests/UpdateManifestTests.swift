import AI2AppsUpdateCore
import Foundation
import Testing

private final class RangeURLProtocol: URLProtocol, @unchecked Sendable {
    static let payload = Data("resumable-update-payload".utf8)
    private static let lock = NSLock()
    nonisolated(unsafe) private static var ranges: [String] = []
    nonisolated(unsafe) private static var hosts: [String] = []
    nonisolated(unsafe) private static var failingHosts: Set<String> = []

    static func reset(failing: Set<String> = []) {
        lock.withLock {
            ranges = []
            hosts = []
            failingHosts = failing
        }
    }
    static func recordedRanges() -> [String] { lock.withLock { ranges } }
    static func recordedHosts() -> [String] { lock.withLock { hosts } }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let range = request.value(forHTTPHeaderField: "Range") ?? ""
        let host = request.url?.host ?? ""
        let shouldFail = Self.lock.withLock {
            Self.ranges.append(range)
            Self.hosts.append(host)
            return Self.failingHosts.contains(host)
        }
        if shouldFail {
            client?.urlProtocol(self, didFailWithError: URLError(.cannotConnectToHost))
            return
        }
        let offset = Int(range.dropFirst("bytes=".count).dropLast()) ?? 0
        let body = Self.payload.dropFirst(offset)
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: offset > 0 ? 206 : 200,
            httpVersion: "HTTP/1.1",
            headerFields: offset > 0
                ? ["Content-Range": "bytes \(offset)-\(Self.payload.count - 1)/\(Self.payload.count)"]
                : nil
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

private final class MirrorURLProtocol: URLProtocol, @unchecked Sendable {
    static let payload = RangeURLProtocol.payload
    private static let lock = NSLock()
    nonisolated(unsafe) private static var ranges: [String] = []
    nonisolated(unsafe) private static var hosts: [String] = []

    static func reset() {
        lock.withLock {
            ranges = []
            hosts = []
        }
    }
    static func recordedRanges() -> [String] { lock.withLock { ranges } }
    static func recordedHosts() -> [String] { lock.withLock { hosts } }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let range = request.value(forHTTPHeaderField: "Range") ?? ""
        let host = request.url?.host ?? ""
        Self.lock.withLock {
            Self.ranges.append(range)
            Self.hosts.append(host)
        }
        if host == "modelscope.example" {
            client?.urlProtocol(self, didFailWithError: URLError(.cannotConnectToHost))
            return
        }
        let offset = Int(range.dropFirst("bytes=".count).dropLast()) ?? 0
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: offset > 0 ? 206 : 200,
            httpVersion: "HTTP/1.1",
            headerFields: offset > 0
                ? ["Content-Range": "bytes \(offset)-\(Self.payload.count - 1)/\(Self.payload.count)"]
                : nil
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(Self.payload.dropFirst(offset)))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

private func artifact(_ name: String) -> UpdateArtifact {
    UpdateArtifact(
        url: URL(string: "https://updates.example.test/\(name)")!,
        filename: name,
        size: 123,
        sha256: String(repeating: "a", count: 64)
    )
}

private func release(build: Int, rollout: Int = 10_000) -> UpdateRelease {
    UpdateRelease(
        bundleIdentifier: "com.ai2apps.desktop",
        instanceID: "default",
        productVersion: "1.2.3",
        bundleVersion: String(build),
        runtimeProfile: "full",
        minimumSystemVersion: "13.0",
        architectures: ["arm64"],
        rollout: UpdateRollout(id: "stable-\(build)", percentageBasisPoints: rollout),
        dmg: artifact("AI2Apps-\(build).dmg"),
        metadata: artifact("AI2Apps-\(build).release.json")
    )
}

@Test func manifestSelectsHighestCompatibleEligibleBuild() throws {
    let manifest = UpdateManifest(channel: "stable", releases: [
        release(build: 101),
        release(build: 103),
        release(build: 102),
    ])
    let selected = try manifest.selectedRelease(
        bundleIdentifier: "com.ai2apps.desktop",
        instanceID: "default",
        currentBuild: 100,
        runtimeProfile: "full",
        architecture: "arm64",
        systemVersion: "14.5.0",
        cohortID: "00000000-0000-0000-0000-000000000001"
    )
    #expect(selected?.bundleVersion == "103")
}

@Test func artifactManifestSupportsMirrorsAndLegacyURL() throws {
    let mirrored = UpdateArtifact(
        urls: [
            URL(string: "https://modelscope.example/AI2Apps.dmg")!,
            URL(string: "https://github.example/AI2Apps.dmg")!,
        ],
        filename: "AI2Apps.dmg",
        size: 123,
        sha256: String(repeating: "a", count: 64)
    )
    let encoded = try JSONEncoder().encode(mirrored)
    let object = try JSONSerialization.jsonObject(with: encoded) as? [String: Any]
    #expect(object?["url"] != nil)
    #expect((object?["urls"] as? [String])?.count == 2)
    #expect(try JSONDecoder().decode(UpdateArtifact.self, from: encoded).urls.count == 2)

    let legacy = Data("""
    {"url":"https://updates.example/AI2Apps.dmg","filename":"AI2Apps.dmg","size":123,"sha256":"\(String(repeating: "a", count: 64))"}
    """.utf8)
    #expect(try JSONDecoder().decode(UpdateArtifact.self, from: legacy).urls.count == 1)
}

@Test func rolloutCohortIsStableAndHonorsClosedRollout() throws {
    let first = UpdateManifest.cohortBucket(rolloutID: "stable-200", cohortID: "device-a")
    let second = UpdateManifest.cohortBucket(rolloutID: "stable-200", cohortID: "device-a")
    #expect(first == second)
    #expect((0..<10_000).contains(first))

    let manifest = UpdateManifest(channel: "stable", releases: [release(build: 200, rollout: 0)])
    let selected = try manifest.selectedRelease(
        bundleIdentifier: "com.ai2apps.desktop",
        instanceID: "default",
        currentBuild: 100,
        runtimeProfile: "full",
        architecture: "arm64",
        systemVersion: "14.0",
        cohortID: "device-a"
    )
    #expect(selected == nil)
}

@Test func cohortIdentifierPersistsAcrossChecks() throws {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(
        "ai2apps-cohort-tests-\(UUID().uuidString)", isDirectory: true
    )
    defer { try? FileManager.default.removeItem(at: directory) }
    let url = directory.appendingPathComponent("update-cohort-id")
    let first = try UpdateManifest.loadOrCreateCohortID(at: url)
    let second = try UpdateManifest.loadOrCreateCohortID(at: url)
    #expect(first == second)
    #expect(UUID(uuidString: first) != nil)
}

@Test func downloaderHashesFilesWithoutLoadingWholeArtifact() throws {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent(
        "ai2apps-download-hash-\(UUID().uuidString)"
    )
    defer { try? FileManager.default.removeItem(at: url) }
    try Data("abc".utf8).write(to: url)
    #expect(
        try ResumableDownloader.sha256(at: url)
            == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
}

@Test func downloaderResumesFromVerifiedPartialLength() async throws {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(
        "ai2apps-resume-tests-\(UUID().uuidString)", isDirectory: true
    )
    defer { try? FileManager.default.removeItem(at: directory) }
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let destination = directory.appendingPathComponent("AI2Apps.dmg")
    let partial = destination.appendingPathExtension("part")
    try RangeURLProtocol.payload.prefix(9).write(to: partial)
    let source = directory.appendingPathComponent("source")
    try RangeURLProtocol.payload.write(to: source)
    let artifact = UpdateArtifact(
        url: URL(string: "https://updates.example.test/AI2Apps.dmg")!,
        filename: "AI2Apps.dmg",
        size: Int64(RangeURLProtocol.payload.count),
        sha256: try ResumableDownloader.sha256(at: source)
    )
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [RangeURLProtocol.self]
    let session = URLSession(configuration: configuration)
    RangeURLProtocol.reset()
    _ = try await ResumableDownloader().download(artifact, to: destination, session: session)
    #expect(try Data(contentsOf: destination) == RangeURLProtocol.payload)
    #expect(RangeURLProtocol.recordedRanges() == ["bytes=9-"])
}

@Test func downloaderFailsOverAndKeepsTheSamePartialFile() async throws {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(
        "ai2apps-mirror-tests-\(UUID().uuidString)", isDirectory: true
    )
    defer { try? FileManager.default.removeItem(at: directory) }
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    let destination = directory.appendingPathComponent("AI2Apps.dmg")
    try RangeURLProtocol.payload.prefix(9).write(to: destination.appendingPathExtension("part"))
    let source = directory.appendingPathComponent("source")
    try RangeURLProtocol.payload.write(to: source)
    let artifact = UpdateArtifact(
        urls: [
            URL(string: "https://modelscope.example/AI2Apps.dmg")!,
            URL(string: "https://github.example/AI2Apps.dmg")!,
        ],
        filename: "AI2Apps.dmg",
        size: Int64(RangeURLProtocol.payload.count),
        sha256: try ResumableDownloader.sha256(at: source)
    )
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [MirrorURLProtocol.self]
    let session = URLSession(configuration: configuration)
    MirrorURLProtocol.reset()
    _ = try await ResumableDownloader().download(artifact, to: destination, session: session)
    #expect(try Data(contentsOf: destination) == RangeURLProtocol.payload)
    #expect(MirrorURLProtocol.recordedHosts() == ["modelscope.example", "github.example"])
    #expect(MirrorURLProtocol.recordedRanges() == ["bytes=9-", "bytes=9-"])
}
