import Foundation

public enum HealthProbeResult: Equatable, Sendable {
    case healthy
    case transientFailure
    case definiteFailure
}

/// A missed response is evidence to confirm, not a service outage by itself.
/// Process death and a mismatched service identity never receive this grace.
public struct HealthProbePolicy: Sendable {
    public private(set) var consecutiveFailures = 0
    public init() {}

    @discardableResult
    public mutating func record(_ result: HealthProbeResult) -> Bool {
        switch result {
        case .healthy: consecutiveFailures = 0
        case .transientFailure: consecutiveFailures += 1
        case .definiteFailure: consecutiveFailures = max(3, consecutiveFailures + 1)
        }
        return consecutiveFailures >= 2
    }
    public var shouldRestart: Bool { consecutiveFailures >= 3 }
}
