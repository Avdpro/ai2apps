import CryptoKit
import Foundation

public enum ResumableDownloadError: Error, Equatable, CustomStringConvertible {
    case invalidResponse
    case invalidRange
    case sizeMismatch(expected: Int64, actual: Int64)
    case checksumMismatch
    case unsafePartialFile

    public var description: String {
        switch self {
        case .invalidResponse: return "download server returned an invalid response"
        case .invalidRange: return "download server returned an invalid byte range"
        case .sizeMismatch(let expected, let actual): return "download size mismatch: expected \(expected), got \(actual)"
        case .checksumMismatch: return "download SHA-256 mismatch"
        case .unsafePartialFile: return "partial download is not a regular file"
        }
    }
}

public struct ResumableDownloader: Sendable {
    public typealias Progress = @Sendable (_ received: Int64, _ total: Int64) -> Void

    public init() {}

    public func download(
        _ artifact: UpdateArtifact,
        to destination: URL,
        session: URLSession = .shared,
        progress: @escaping Progress = { _, _ in }
    ) async throws -> URL {
        try artifact.validate(field: "artifact")
        let fileManager = FileManager.default
        try fileManager.createDirectory(
            at: destination.deletingLastPathComponent(),
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        let partial = destination.appendingPathExtension("part")
        var existing = try partialSize(at: partial, fileManager: fileManager)
        if existing > artifact.size {
            try fileManager.removeItem(at: partial)
            existing = 0
        }
        if existing == artifact.size {
            return try finish(partial: partial, destination: destination, artifact: artifact)
        }

        var lastError: Error = ResumableDownloadError.invalidResponse
        for url in artifact.urls {
            do {
                return try await download(
                    artifact,
                    from: url,
                    partial: partial,
                    destination: destination,
                    session: session,
                    progress: progress
                )
            } catch is CancellationError {
                throw CancellationError()
            } catch {
                if Task.isCancelled { throw CancellationError() }
                lastError = error
            }
        }
        throw lastError
    }

    private func download(
        _ artifact: UpdateArtifact,
        from url: URL,
        partial: URL,
        destination: URL,
        session: URLSession,
        progress: @escaping Progress
    ) async throws -> URL {
        let fileManager = FileManager.default
        var existing = try partialSize(at: partial, fileManager: fileManager)
        if existing > artifact.size {
            try fileManager.removeItem(at: partial)
            existing = 0
        }

        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        request.timeoutInterval = 120
        request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
        if existing > 0 { request.setValue("bytes=\(existing)-", forHTTPHeaderField: "Range") }
        let (bytes, response) = try await session.bytes(for: request)
        guard let http = response as? HTTPURLResponse,
              http.url?.scheme?.lowercased() == "https" else {
            throw ResumableDownloadError.invalidResponse
        }

        var append = existing > 0 && http.statusCode == 206
        if append {
            guard http.value(forHTTPHeaderField: "Content-Range")?.hasPrefix("bytes \(existing)-") == true else {
                throw ResumableDownloadError.invalidRange
            }
        } else {
            guard http.statusCode == 200 else { throw ResumableDownloadError.invalidResponse }
            existing = 0
            append = false
        }

        if !fileManager.fileExists(atPath: partial.path) {
            fileManager.createFile(atPath: partial.path, contents: nil, attributes: [.posixPermissions: 0o600])
        }
        let handle = try FileHandle(forWritingTo: partial)
        defer { try? handle.close() }
        if append { try handle.seekToEnd() } else { try handle.truncate(atOffset: 0) }

        var received = existing
        var buffer = Data()
        buffer.reserveCapacity(64 * 1024)
        progress(received, artifact.size)
        for try await byte in bytes {
            try Task.checkCancellation()
            buffer.append(byte)
            if buffer.count >= 64 * 1024 {
                try handle.write(contentsOf: buffer)
                received += Int64(buffer.count)
                buffer.removeAll(keepingCapacity: true)
                guard received <= artifact.size else {
                    throw ResumableDownloadError.sizeMismatch(expected: artifact.size, actual: received)
                }
                progress(received, artifact.size)
            }
        }
        if !buffer.isEmpty {
            try handle.write(contentsOf: buffer)
            received += Int64(buffer.count)
        }
        try handle.synchronize()
        progress(received, artifact.size)
        guard received == artifact.size else {
            throw ResumableDownloadError.sizeMismatch(expected: artifact.size, actual: received)
        }
        return try finish(partial: partial, destination: destination, artifact: artifact)
    }

    public static func sha256(at url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private func partialSize(at url: URL, fileManager: FileManager) throws -> Int64 {
        guard fileManager.fileExists(atPath: url.path) else { return 0 }
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true else {
            throw ResumableDownloadError.unsafePartialFile
        }
        return Int64(values.fileSize ?? 0)
    }

    private func finish(partial: URL, destination: URL, artifact: UpdateArtifact) throws -> URL {
        let actual = try Self.sha256(at: partial)
        guard actual == artifact.sha256 else {
            try? FileManager.default.removeItem(at: partial)
            throw ResumableDownloadError.checksumMismatch
        }
        let fileManager = FileManager.default
        if fileManager.fileExists(atPath: destination.path) { try fileManager.removeItem(at: destination) }
        try fileManager.moveItem(at: partial, to: destination)
        try fileManager.setAttributes([.posixPermissions: 0o600], ofItemAtPath: destination.path)
        return destination
    }
}
