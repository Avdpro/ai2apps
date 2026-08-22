import Foundation

public struct BrowserAgentLease: Equatable, Sendable {
    public static let defaultTimeToLive: TimeInterval = 30 * 60

    public let timeToLive: TimeInterval
    public private(set) var expiresAt: Date?
    public private(set) var isPaused: Bool

    public init(
        now: Date = Date(),
        timeToLive: TimeInterval = Self.defaultTimeToLive
    ) {
        precondition(timeToLive > 0)
        self.timeToLive = timeToLive
        expiresAt = now.addingTimeInterval(timeToLive)
        isPaused = false
    }

    public mutating func renew(now: Date = Date()) {
        guard !isPaused else { return }
        expiresAt = now.addingTimeInterval(timeToLive)
    }

    public mutating func pause() {
        isPaused = true
        expiresAt = nil
    }

    public mutating func resume(now: Date = Date()) {
        isPaused = false
        expiresAt = now.addingTimeInterval(timeToLive)
    }

    public func isExpired(now: Date = Date()) -> Bool {
        guard !isPaused, let expiresAt else { return false }
        return now >= expiresAt
    }
}
