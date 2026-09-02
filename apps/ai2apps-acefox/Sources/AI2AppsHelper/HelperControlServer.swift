import AI2AppsContracts
import Darwin
import Foundation
import Security

struct HelperControlRequest: Codable, Sendable {
    let version: Int
    let requestID: String
    let token: String
    let operation: String
    let actorUserID: String
    let browserProfileKey: String?
    let initialURL: String?

    enum CodingKeys: String, CodingKey {
        case version
        case requestID = "request_id"
        case token
        case operation
        case actorUserID = "actor_user_id"
        case browserProfileKey = "browser_profile_key"
        case initialURL = "initial_url"
    }
}

struct HelperControlResult: Codable, Sendable {
    let status: String
    let profileID: String?
    let processID: Int32?
    let automation: HelperBrowserAutomation?

    init(
        status: String,
        profileID: String? = nil,
        processID: Int32? = nil,
        automation: HelperBrowserAutomation? = nil
    ) {
        self.status = status
        self.profileID = profileID
        self.processID = processID
        self.automation = automation
    }

    enum CodingKeys: String, CodingKey {
        case status
        case profileID = "profile_id"
        case processID = "pid"
        case automation
    }
}

struct HelperBrowserAutomation: Codable, Sendable {
    let transport: String
    let webSocketURL: String
    let authorization: String

    enum CodingKeys: String, CodingKey {
        case transport
        case webSocketURL = "web_socket_url"
        case authorization
    }
}

struct HelperControlResponse: Codable, Sendable {
    let requestID: String
    let ok: Bool
    let result: HelperControlResult?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case requestID = "request_id"
        case ok
        case result
        case error
    }

    static func success(requestID: String, result: HelperControlResult) -> Self {
        Self(requestID: requestID, ok: true, result: result, error: nil)
    }

    static func failure(requestID: String, error: String) -> Self {
        Self(requestID: requestID, ok: false, result: nil, error: error)
    }
}

struct HelperControlCredentials: Sendable {
    let endpointURL: URL
    let token: String

    init(instanceID: InstanceID, paths: InstancePaths) throws {
        _ = instanceID
        endpointURL = paths.runDirectory.appendingPathComponent("helper-control.json")

        let tokenURL = paths.runDirectory.appendingPathComponent("helper-control.token")
        if let existing = try? String(contentsOf: tokenURL, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines),
           existing.count == 64,
           existing.allSatisfy({ $0.isHexDigit && !$0.isUppercase }) {
            token = existing
            return
        }
        var random = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else {
            throw ContractError.invalidField(field: "helper.token", reason: "secure random generation failed")
        }
        token = random.map { String(format: "%02x", $0) }.joined()
        try Data((token + "\n").utf8).write(to: tokenURL, options: .atomic)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o600],
            ofItemAtPath: tokenURL.path
        )
    }

    var environment: [String: String] {
        [
            "AI2APPS_HELPER_ENDPOINT": endpointURL.path,
            "AI2APPS_HELPER_TOKEN": token,
            "AI2APPS_BROWSER_BACKEND": "acefox",
        ]
    }
}

private struct HelperControlEndpoint: Codable {
    let version: Int
    let host: String
    let port: UInt16
}

final class HelperControlServer: @unchecked Sendable {
    typealias Handler = @Sendable (HelperControlRequest) async -> HelperControlResponse

    private static let maximumMessageSize = 64 * 1024
    private let credentials: HelperControlCredentials
    private let handler: Handler
    private let queue = DispatchQueue(label: "com.ai2apps.helper.control")
    private let stateLock = NSLock()
    private var listener: Int32 = -1

    init(credentials: HelperControlCredentials, handler: @escaping Handler) {
        self.credentials = credentials
        self.handler = handler
    }

    func start() throws {
        let descriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw posixError("socket") }
        do {
            var noSignal: Int32 = 1
            guard setsockopt(
                descriptor,
                SOL_SOCKET,
                SO_NOSIGPIPE,
                &noSignal,
                socklen_t(MemoryLayout<Int32>.size)
            ) == 0 else { throw posixError("setsockopt") }
            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            address.sin_family = sa_family_t(AF_INET)
            address.sin_port = in_port_t(0)
            address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
            let bindResult = withUnsafePointer(to: &address) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                    bind(descriptor, socketAddress, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            guard bindResult == 0 else { throw posixError("bind") }
            guard listen(descriptor, 8) == 0 else { throw posixError("listen") }

            var boundAddress = sockaddr_in()
            var boundLength = socklen_t(MemoryLayout<sockaddr_in>.size)
            let nameResult = withUnsafeMutablePointer(to: &boundAddress) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                    getsockname(descriptor, socketAddress, &boundLength)
                }
            }
            guard nameResult == 0 else { throw posixError("getsockname") }
            let endpoint = HelperControlEndpoint(
                version: 1,
                host: "127.0.0.1",
                port: UInt16(bigEndian: boundAddress.sin_port)
            )
            let endpointData = try JSONEncoder().encode(endpoint)
            try endpointData.write(to: credentials.endpointURL, options: .atomic)
            try FileManager.default.setAttributes(
                [.posixPermissions: 0o600],
                ofItemAtPath: credentials.endpointURL.path
            )
            stateLock.withLock { listener = descriptor }
            queue.async { [weak self] in self?.acceptLoop(descriptor: descriptor) }
        } catch {
            close(descriptor)
            try? FileManager.default.removeItem(at: credentials.endpointURL)
            throw error
        }
    }

    func stop() {
        let descriptor = stateLock.withLock { () -> Int32 in
            let current = listener
            listener = -1
            return current
        }
        if descriptor >= 0 {
            shutdown(descriptor, SHUT_RDWR)
            close(descriptor)
        }
        try? FileManager.default.removeItem(at: credentials.endpointURL)
    }

    deinit {
        stop()
    }

    private func acceptLoop(descriptor: Int32) {
        while stateLock.withLock({ listener == descriptor }) {
            let connection = accept(descriptor, nil, nil)
            if connection < 0 {
                if errno == EINTR { continue }
                return
            }
            var noSignal: Int32 = 1
            _ = setsockopt(
                connection,
                SOL_SOCKET,
                SO_NOSIGPIPE,
                &noSignal,
                socklen_t(MemoryLayout<Int32>.size)
            )
            Task { [weak self] in
                await self?.handle(connection: connection)
            }
        }
    }

    private func handle(connection: Int32) async {
        defer { close(connection) }
        let request: HelperControlRequest
        do {
            request = try JSONDecoder().decode(
                HelperControlRequest.self,
                from: readMessage(connection: connection)
            )
        } catch {
            writeResponse(
                .failure(requestID: "invalid", error: "Invalid Helper request"),
                connection: connection
            )
            return
        }
        guard request.version == 1,
              [
                  "browser.launch",
                  "browser.release",
                  "browser.delete",
                  "browser.renew",
                  "browser.pause",
                  "browser.resume",
                  "local.restart",
              ].contains(request.operation),
              constantTimeEqual(request.token, credentials.token),
              (1...200).contains(request.actorUserID.utf8.count) else {
            writeResponse(
                .failure(requestID: request.requestID, error: "Helper request rejected"),
                connection: connection
            )
            return
        }

        let response = await handler(request)
        writeResponse(response, connection: connection)
    }

    private func readMessage(connection: Int32) throws -> Data {
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while data.count <= Self.maximumMessageSize {
            let count = Darwin.read(connection, &buffer, buffer.count)
            guard count > 0 else { break }
            data.append(buffer, count: count)
            if data.contains(0x0A) { break }
        }
        guard let newline = data.firstIndex(of: 0x0A), newline <= Self.maximumMessageSize else {
            throw ContractError.invalidField(field: "helper.request", reason: "message is incomplete or too large")
        }
        return data.prefix(upTo: newline)
    }

    private func writeResponse(_ response: HelperControlResponse, connection: Int32) {
        guard var data = try? JSONEncoder().encode(response) else { return }
        data.append(0x0A)
        data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < bytes.count {
                let written = Darwin.write(
                    connection,
                    bytes.baseAddress!.advanced(by: offset),
                    bytes.count - offset
                )
                if written <= 0 { return }
                offset += written
            }
        }
    }

    private func constantTimeEqual(_ first: String, _ second: String) -> Bool {
        let firstBytes = Array(first.utf8)
        let secondBytes = Array(second.utf8)
        guard firstBytes.count == secondBytes.count else { return false }
        return zip(firstBytes, secondBytes).reduce(UInt8(0)) { result, pair in
            result | (pair.0 ^ pair.1)
        } == 0
    }

    private func posixError(_ operation: String) -> ContractError {
        ContractError.invalidField(field: "helper.\(operation)", reason: String(cString: strerror(errno)))
    }
}
