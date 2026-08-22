import AI2AppsContracts
import Foundation

public struct ReadyLocal: Equatable, Sendable {
    public let descriptor: LocalRunDescriptor

    public init(descriptor: LocalRunDescriptor) {
        self.descriptor = descriptor
    }

    public var origin: URL {
        URL(string: "http://127.0.0.1:\(descriptor.actualPort)")!
    }
}

public enum SupervisorState: Equatable, Sendable {
    case stopped
    case validatingRuntime(bootID: UUID)
    case starting(bootID: UUID)
    case migrating(processID: Int32, bootID: UUID)
    case ready(ReadyLocal)
    case degraded(ReadyLocal, consecutiveHealthFailures: Int)
    case stopping(processID: Int32?)
    case failed(message: String, restartAttempt: Int)

    public var isRunningLike: Bool {
        switch self {
        case .starting, .migrating, .ready, .degraded, .stopping:
            return true
        case .stopped, .validatingRuntime, .failed:
            return false
        }
    }
}

public enum SupervisorEvent: Equatable, Sendable {
    case requestStart(bootID: UUID)
    case runtimeValidated(bootID: UUID)
    case processSpawned(processID: Int32, bootID: UUID)
    case migrationStarted(processID: Int32, bootID: UUID)
    case localReady(LocalRunDescriptor)
    case healthFailed
    case healthRecovered
    case requestStop
    case processExited(expected: Bool, message: String?)
    case stopCompleted
    case retryScheduled(attempt: Int, message: String)
}

public enum SupervisorTransitionError: Error, Equatable, Sendable {
    case invalidTransition(state: String, event: String)
    case staleBootID
}

public enum SupervisorReducer {
    public static func reduce(
        state: SupervisorState,
        event: SupervisorEvent,
        expectedInstanceID: InstanceID
    ) throws -> SupervisorState {
        switch (state, event) {
        case (.stopped, .requestStart(let bootID)),
             (.failed, .requestStart(let bootID)):
            return .validatingRuntime(bootID: bootID)

        case (.validatingRuntime(let expected), .runtimeValidated(let actual)):
            guard expected == actual else { throw SupervisorTransitionError.staleBootID }
            return .starting(bootID: actual)

        case (.starting(let expected), .processSpawned(let processID, let actual)):
            guard expected == actual else { throw SupervisorTransitionError.staleBootID }
            guard processID > 0 else {
                throw ContractError.invalidField(field: "pid", reason: "must be positive")
            }
            return .migrating(processID: processID, bootID: actual)

        case (.starting(let expected), .migrationStarted(let processID, let actual)),
             (.migrating(_, let expected), .migrationStarted(let processID, let actual)):
            guard expected == actual else { throw SupervisorTransitionError.staleBootID }
            return .migrating(processID: processID, bootID: actual)

        case (.migrating(_, let expectedBootID), .localReady(let descriptor)),
             (.starting(let expectedBootID), .localReady(let descriptor)):
            guard descriptor.bootID == expectedBootID else { throw SupervisorTransitionError.staleBootID }
            try descriptor.validate(expectedInstanceID: expectedInstanceID)
            return .ready(ReadyLocal(descriptor: descriptor))

        case (.ready(let local), .healthFailed):
            return .degraded(local, consecutiveHealthFailures: 1)

        case (.degraded(let local, let failures), .healthFailed):
            return .degraded(local, consecutiveHealthFailures: failures + 1)

        case (.degraded(let local, _), .healthRecovered):
            return .ready(local)

        case (.starting, .requestStop),
             (.migrating, .requestStop):
            return .stopping(processID: nil)

        case (.ready(let local), .requestStop),
             (.degraded(let local, _), .requestStop):
            return .stopping(processID: local.descriptor.processID)

        case (.validatingRuntime, .requestStop):
            return .stopped

        case (.stopping, .stopCompleted),
             (_, .processExited(expected: true, message: _)):
            return .stopped

        case (_, .processExited(expected: false, let message)):
            return .failed(message: message ?? "Local process exited unexpectedly", restartAttempt: 0)

        case (.failed, .retryScheduled(let attempt, let message)):
            return .failed(message: message, restartAttempt: attempt)

        default:
            throw SupervisorTransitionError.invalidTransition(
                state: String(describing: state),
                event: String(describing: event)
            )
        }
    }
}
