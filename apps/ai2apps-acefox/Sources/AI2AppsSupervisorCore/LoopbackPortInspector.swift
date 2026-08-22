import AI2AppsContracts
import Darwin
import Foundation

public struct PortConflict: Equatable, Sendable {
    public let host: String
    public let port: Int

    public init(host: String, port: Int) {
        self.host = host
        self.port = port
    }
}

public struct LoopbackPortInspector: Sendable {
    public init() {}

    public func conflict(for configuration: LocalConfiguration) throws -> PortConflict? {
        try configuration.validate()
        guard configuration.portMode == .fixed, let port = configuration.configuredPort else {
            return nil
        }
        return isAvailable(port: port) ? nil : PortConflict(host: configuration.bindAddress, port: port)
    }

    public func isAvailable(port: Int) -> Bool {
        guard (1024...65535).contains(port) else { return false }
        let descriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { return false }
        defer { close(descriptor) }

        var address = sockaddr_in()
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(port).bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")

        let result = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                bind(descriptor, socketAddress, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }
}
