import AI2AppsContracts
import Darwin
import Foundation

public enum LocalSupervisorError: Error, Equatable, Sendable {
    case alreadyRunning
    case portInUse(PortConflict)
    case processExited(status: Int32)
    case descriptorProcessMismatch(expected: Int32, actual: Int32)
    case startupTimedOut
    case bootstrapRejected(String)
}

public actor LocalProcessSupervisor {
    public private(set) var state: SupervisorState = .stopped

    private let instanceID: InstanceID
    private let configuration: LocalConfiguration
    private let paths: InstancePaths
    private let executable: URL
    private let baseEnvironment: [String: String]
    private var process: Process?
    private var managedDescriptor: LocalRunDescriptor?
    private var processLogHandle: FileHandle?

    public init(
        instanceID: InstanceID,
        configuration: LocalConfiguration,
        paths: InstancePaths,
        executable: URL,
        baseEnvironment: [String: String] = ProcessInfo.processInfo.environment
    ) {
        self.instanceID = instanceID
        self.configuration = configuration
        self.paths = paths
        self.executable = executable
        self.baseEnvironment = baseEnvironment
    }

    @discardableResult
    public func start(timeout: Duration = .seconds(90)) async throws -> ReadyLocal {
        guard process == nil, managedDescriptor == nil, !state.isRunningLike else {
            throw LocalSupervisorError.alreadyRunning
        }

        let bootID = UUID()
        state = try SupervisorReducer.reduce(
            state: state,
            event: .requestStart(bootID: bootID),
            expectedInstanceID: instanceID
        )

        if let conflict = try LoopbackPortInspector().conflict(for: configuration) {
            state = .failed(message: "Port \(conflict.port) is already in use", restartAttempt: 0)
            throw LocalSupervisorError.portInUse(conflict)
        }

        let plan = try LocalLaunchPlan(
            executable: executable,
            instanceID: instanceID,
            configuration: configuration,
            paths: paths,
            bootID: bootID,
            inheritedEnvironment: baseEnvironment
        )
        try prepareRunDirectory(descriptorURL: plan.runDescriptorURL)
        state = try SupervisorReducer.reduce(
            state: state,
            event: .runtimeValidated(bootID: bootID),
            expectedInstanceID: instanceID
        )

        let child = Process()
        child.executableURL = plan.executable
        child.arguments = plan.arguments
        child.environment = plan.environment
        child.currentDirectoryURL = paths.supportRoot
        let logHandle = try openProcessLog()
        child.standardOutput = logHandle
        child.standardError = logHandle
        try child.run()
        process = child
        processLogHandle = logHandle
        managedDescriptor = nil
        state = try SupervisorReducer.reduce(
            state: state,
            event: .processSpawned(processID: child.processIdentifier, bootID: bootID),
            expectedInstanceID: instanceID
        )

        do {
            let ready = try await waitUntilReady(
                process: child,
                descriptorURL: plan.runDescriptorURL,
                bootID: bootID,
                timeout: timeout
            )
            state = try SupervisorReducer.reduce(
                state: state,
                event: .localReady(ready.descriptor),
                expectedInstanceID: instanceID
            )
            managedDescriptor = ready.descriptor
            return ready
        } catch {
            if child.isRunning {
                child.terminate()
            }
            process = nil
            try? processLogHandle?.close()
            processLogHandle = nil
            managedDescriptor = nil
            state = .failed(message: String(describing: error), restartAttempt: 0)
            throw error
        }
    }

    @discardableResult
    public func adoptRunningLocal() async throws -> ReadyLocal? {
        guard process == nil, managedDescriptor == nil, !state.isRunningLike else {
            throw LocalSupervisorError.alreadyRunning
        }
        let descriptorURL = paths.runDirectory.appendingPathComponent("local.json")
        guard FileManager.default.fileExists(atPath: descriptorURL.path) else {
            return nil
        }
        let descriptor = try ContractCodec.load(LocalRunDescriptor.self, from: descriptorURL)
        try descriptor.validate(expectedInstanceID: instanceID)
        guard isProcessRunning(descriptor.processID) else {
            try? FileManager.default.removeItem(at: descriptorURL)
            return nil
        }
        let ready = ReadyLocal(descriptor: descriptor)
        _ = try await fetchBootstrap(from: ready.origin, bootID: descriptor.bootID)
        managedDescriptor = descriptor
        state = .ready(ready)
        return ready
    }

    public func stop(gracePeriod: Duration = .seconds(8)) async {
        guard let descriptor = managedDescriptor else {
            if let child = process {
                if child.isRunning {
                    child.terminate()
                }
                process = nil
                try? processLogHandle?.close()
                processLogHandle = nil
            }
            state = .stopped
            return
        }
        let child = process
        state = (try? SupervisorReducer.reduce(
            state: state,
            event: .requestStop,
            expectedInstanceID: instanceID
        )) ?? .stopping(processID: descriptor.processID)

        if !isProcessRunning(descriptor.processID) {
            process = nil
            try? processLogHandle?.close()
            processLogHandle = nil
            managedDescriptor = nil
            state = .stopped
            return
        }
        if child == nil {
            do {
                _ = try await fetchBootstrap(
                    from: ReadyLocal(descriptor: descriptor).origin,
                    bootID: descriptor.bootID
                )
            } catch {
                state = .failed(message: "Refused to stop an unverified adopted Local process", restartAttempt: 0)
                return
            }
        }

        if let child, child.isRunning {
            child.terminate()
        } else {
            kill(descriptor.processID, SIGTERM)
        }

        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: gracePeriod)
        while isProcessRunning(descriptor.processID), clock.now < deadline {
            try? await Task.sleep(for: .milliseconds(50))
        }
        if isProcessRunning(descriptor.processID) {
            kill(descriptor.processID, SIGKILL)
        }
        process = nil
        try? processLogHandle?.close()
        processLogHandle = nil
        managedDescriptor = nil
        state = .stopped
    }

    public func healthCheck() async -> Bool {
        let local: ReadyLocal
        switch state {
        case .ready(let ready), .degraded(let ready, _):
            local = ready
        default:
            return false
        }
        do {
            _ = try await fetchBootstrap(from: local.origin, bootID: local.descriptor.bootID)
            if case .degraded = state {
                state = (try? SupervisorReducer.reduce(
                    state: state,
                    event: .healthRecovered,
                    expectedInstanceID: instanceID
                )) ?? state
            }
            return true
        } catch {
            state = (try? SupervisorReducer.reduce(
                state: state,
                event: .healthFailed,
                expectedInstanceID: instanceID
            )) ?? state
            return false
        }
    }

    private func prepareRunDirectory(descriptorURL: URL) throws {
        try FileManager.default.createDirectory(
            at: paths.runDirectory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        if FileManager.default.fileExists(atPath: descriptorURL.path) {
            try FileManager.default.removeItem(at: descriptorURL)
        }
    }

    private func openProcessLog() throws -> FileHandle {
        try FileManager.default.createDirectory(
            at: paths.logDirectory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        let logURL = paths.logDirectory.appendingPathComponent("local.log")
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(
                atPath: logURL.path,
                contents: nil,
                attributes: [.posixPermissions: 0o600]
            )
        }
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        return handle
    }

    private func waitUntilReady(
        process child: Process,
        descriptorURL: URL,
        bootID: UUID,
        timeout: Duration
    ) async throws -> ReadyLocal {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        var validatedDescriptor: LocalRunDescriptor?
        while clock.now < deadline {
            guard child.isRunning else {
                throw LocalSupervisorError.processExited(status: child.terminationStatus)
            }
            if validatedDescriptor == nil,
               FileManager.default.fileExists(atPath: descriptorURL.path) {
                let descriptor = try ContractCodec.load(LocalRunDescriptor.self, from: descriptorURL)
                try descriptor.validate(expectedInstanceID: instanceID)
                guard descriptor.bootID == bootID else {
                    throw SupervisorTransitionError.staleBootID
                }
                guard descriptor.processID == child.processIdentifier else {
                    throw LocalSupervisorError.descriptorProcessMismatch(
                        expected: child.processIdentifier,
                        actual: descriptor.processID
                    )
                }
                validatedDescriptor = descriptor
            }
            if let descriptor = validatedDescriptor {
                let ready = ReadyLocal(descriptor: descriptor)
                do {
                    _ = try await fetchBootstrap(from: ready.origin, bootID: bootID)
                    return ready
                } catch {
                    // Binding the socket and publishing the descriptor happens
                    // just before the application finishes its startup work.
                    // Keep polling within the single startup deadline.
                }
            }
            try await Task.sleep(for: .milliseconds(100))
        }
        throw LocalSupervisorError.startupTimedOut
    }

    private func fetchBootstrap(from origin: URL, bootID: UUID) async throws -> ClientBootstrap {
        let url = origin.appending(path: "v1/platform/client/bootstrap")
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw LocalSupervisorError.bootstrapRejected("HTTP bootstrap request failed")
        }
        let bootstrap = try ContractCodec.decoder().decode(ClientBootstrap.self, from: data)
        do {
            try bootstrap.validate(expectedInstanceID: instanceID, expectedBootID: bootID)
        } catch {
            throw LocalSupervisorError.bootstrapRejected(String(describing: error))
        }
        return bootstrap
    }

    private func isProcessRunning(_ processID: Int32) -> Bool {
        guard processID > 0 else { return false }
        return kill(processID, 0) == 0 || errno == EPERM
    }
}
