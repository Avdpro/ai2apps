import AI2AppsContracts
import AI2AppsSupervisorCore
import AppKit
import Darwin
import Foundation
import Security

private typealias HelperArguments = HelperLaunchConfiguration

private func validatePackagedRuntime(arguments: HelperArguments) throws {
    guard arguments.isPackaged else { return }
    if let appBundleURL = arguments.appBundleURL,
       Bundle(url: appBundleURL)?.object(
           forInfoDictionaryKey: "AI2AppsDevelopment"
       ) as? Bool == true {
        return
    }
    let runtimeRoot = arguments.runtimeExecutable
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let manifestURL = runtimeRoot.appendingPathComponent("runtime-manifest.json")
    let manifest = try ContractCodec.load(RuntimeManifest.self, from: manifestURL)
    _ = try RuntimeValidator().validate(manifest: manifest, root: runtimeRoot)
}

@MainActor
private final class HelperDelegate: NSObject, NSApplicationDelegate {
    private struct BrowserAgentAuditEvent: Codable {
        let version = 1
        let timestamp: Date
        let action: String
        let profileID: String
        let processID: Int32
        let outcome: String

        enum CodingKeys: String, CodingKey {
            case version
            case timestamp
            case action
            case profileID = "profile_id"
            case processID = "pid"
            case outcome
        }
    }

    private struct ManagedBrowserAgent {
        let application: NSRunningApplication
        let automation: BrowserAgentAutomation
        var lease: BrowserAgentLease
    }

    private let arguments: HelperArguments
    private let paths: InstancePaths
    private let instanceLock: HelperInstanceLock
    private let controlCredentials: HelperControlCredentials
    private var configuration: LocalConfiguration
    private var supervisor: LocalProcessSupervisor
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let statusMenuItem = NSMenuItem(title: "正在初始化…", action: nil, keyEquivalent: "")
    private let portMenuItem = NSMenuItem(title: "端口：自动", action: nil, keyEquivalent: "")
    private let modelStorageMenuItem = NSMenuItem(
        title: "模型存储：本实例私有",
        action: nil,
        keyEquivalent: ""
    )
    private let loginItemMenuItem = NSMenuItem(title: "登录启动：尚未配置", action: nil, keyEquivalent: "")
    private let loginItemToggleMenuItem = NSMenuItem(
        title: "登录时启动",
        action: nil,
        keyEquivalent: ""
    )
    private let updateStatusMenuItem = NSMenuItem(
        title: "更新：尚未检查",
        action: nil,
        keyEquivalent: ""
    )
    private let checkUpdateMenuItem = NSMenuItem(
        title: "检查已下载更新",
        action: nil,
        keyEquivalent: ""
    )
    private let installUpdateMenuItem = NSMenuItem(
        title: "安装更新并退出 AI2Apps…",
        action: nil,
        keyEquivalent: ""
    )
    private let launchBuild: String
    private let mainBundleIdentifier: String?
    private let sandboxedPackage: Bool
    private var actualPort: Int?
    private var healthMonitor: Task<Void, Never>?
    private var browserAgentLeaseMonitor: Task<Void, Never>?
    private var controlServer: HelperControlServer?
    private var browserAgents: [String: ManagedBrowserAgent] = [:]
    private var updateProcess: Process?
    private var stagedCandidateBuild: String?
    private var terminationTask: Task<Void, Never>?
    private var serviceStoppedForTermination = false
    private lazy var menuBarLogo: NSImage? = {
        guard let url = Bundle.main.url(
            forResource: "menubar-logo",
            withExtension: "svg"
        ) else {
            return nil
        }
        return NSImage(contentsOf: url)
    }()

    init(
        arguments: HelperArguments,
        paths: InstancePaths,
        instanceLock: HelperInstanceLock,
        controlCredentials: HelperControlCredentials
    ) {
        self.arguments = arguments
        self.paths = paths
        self.instanceLock = instanceLock
        self.controlCredentials = controlCredentials
        launchBuild = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsBuildNumber"
        ) as? String ?? "1"
        mainBundleIdentifier = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsMainBundleIdentifier"
        ) as? String
        sandboxedPackage = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsApplicationGroupIdentifier"
        ) as? String != nil
        let configURL = paths.configDirectory.appendingPathComponent("local.json")
        configuration = (try? ContractCodec.load(LocalConfiguration.self, from: configURL)) ?? LocalConfiguration()
        supervisor = LocalProcessSupervisor(
            instanceID: arguments.instanceID,
            configuration: configuration,
            paths: paths,
            executable: arguments.runtimeExecutable,
            baseEnvironment: ProcessInfo.processInfo.environment.merging(
                controlCredentials.environment
            ) { _, required in required }
        )
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem.length = NSStatusItem.squareLength
        statusItem.button?.title = ""
        statusItem.button?.imagePosition = .imageOnly
        statusItem.button?.toolTip = "AI2Apps 服务 — \(arguments.instanceID.rawValue)"
        updateStatusIcon(for: .initializing)
        rebuildMenu()
        do {
            try paths.preparePrivateDirectories()
            publishStatus(.initializing, message: "正在初始化 Helper…")
            publishUpdateStatus(.idle, message: "尚未检查更新")
        } catch {
            presentError(error)
            NSApp.terminate(nil)
            return
        }
        do {
            let server = HelperControlServer(
                credentials: controlCredentials
            ) { [weak self] request in
                guard let self else {
                    return .failure(requestID: request.requestID, error: "Helper is shutting down")
                }
                return await self.handleControlRequest(request)
            }
            try server.start()
            controlServer = server
        } catch {
            publishStatus(
                .degraded,
                message: "Helper 控制通道启动失败",
                errorCode: "control_channel_failed"
            )
            presentError(error)
        }
        beginBrowserAgentLeaseMonitoring()
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(browserAgentApplicationDidTerminate(_:)),
            name: NSWorkspace.didTerminateApplicationNotification,
            object: nil
        )
        adoptOrStartLocal()
    }

    func applicationWillTerminate(_ notification: Notification) {
        browserAgentLeaseMonitor?.cancel()
        browserAgentLeaseMonitor = nil
        NSWorkspace.shared.notificationCenter.removeObserver(
            self,
            name: NSWorkspace.didTerminateApplicationNotification,
            object: nil
        )
        for (profileID, agent) in browserAgents {
            if !agent.application.isTerminated {
                auditBrowserEvent(
                    action: "browser.terminate",
                    profileID: profileID,
                    processID: agent.application.processIdentifier,
                    outcome: "helper_exiting"
                )
                agent.application.terminate()
            }
        }
        browserAgents.removeAll()
        controlServer?.stop()
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard updateProcess == nil else {
            NSSound.beep()
            return .terminateCancel
        }
        guard !serviceStoppedForTermination else {
            return .terminateNow
        }
        guard terminationTask == nil else {
            return .terminateLater
        }
        healthMonitor?.cancel()
        healthMonitor = nil
        statusMenuItem.title = "状态：正在停止服务"
        publishStatus(.stopping, message: "正在停止 AI2Apps 服务…")
        terminationTask = Task { [weak self, weak sender] in
            guard let self else { return }
            await supervisor.stop()
            actualPort = nil
            serviceStoppedForTermination = true
            terminationTask = nil
            publishStatus(.helperExiting, message: "AI2Apps 服务已停止，Helper 正在退出")
            sender?.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }

    private func rebuildMenu() {
        let menu = NSMenu()
        // AppKit otherwise re-enables any item whose target implements its
        // action, overriding the explicit update/readiness gates below.
        menu.autoenablesItems = false
        let instance = NSMenuItem(
            title: "实例：\(arguments.instanceID.rawValue)",
            action: nil,
            keyEquivalent: ""
        )
        instance.isEnabled = false
        statusMenuItem.isEnabled = false
        portMenuItem.isEnabled = false
        modelStorageMenuItem.isEnabled = false
        loginItemMenuItem.isEnabled = false
        updateStatusMenuItem.isEnabled = false
        menu.addItem(instance)
        menu.addItem(statusMenuItem)
        menu.addItem(portMenuItem)
        menu.addItem(modelStorageMenuItem)
        menu.addItem(loginItemMenuItem)
        menu.addItem(.separator())
        let openApp = menu.addItem(
            withTitle: "打开 AI2Apps",
            action: #selector(openAI2Apps),
            keyEquivalent: ""
        )
        openApp.target = self
        openApp.isEnabled = mainBundleIdentifier != nil || arguments.appBundleURL != nil
        menu.addItem(withTitle: "启动 AI2Apps 服务", action: #selector(startLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: "停止 AI2Apps 服务", action: #selector(stopLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: "重启 AI2Apps 服务", action: #selector(restartLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: "配置端口…", action: #selector(configurePort), keyEquivalent: "")
            .target = self
        loginItemToggleMenuItem.action = #selector(toggleLoginItem)
        loginItemToggleMenuItem.target = self
        loginItemToggleMenuItem.isEnabled = canConfigureLoginItem
        menu.addItem(loginItemToggleMenuItem)
        menu.addItem(.separator())
        menu.addItem(updateStatusMenuItem)
        checkUpdateMenuItem.action = #selector(checkDownloadedUpdate)
        checkUpdateMenuItem.target = self
        menu.addItem(checkUpdateMenuItem)
        installUpdateMenuItem.action = #selector(installStagedUpdate)
        installUpdateMenuItem.target = self
        menu.addItem(installUpdateMenuItem)
        menu.addItem(withTitle: "复制服务地址", action: #selector(copyLocalAddress), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: "打开日志文件夹", action: #selector(openLogs), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: "导出安全诊断摘要…", action: #selector(exportDiagnostics), keyEquivalent: "")
            .target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "退出 AI2Apps 服务", action: #selector(quitAll), keyEquivalent: "q")
            .target = self
        statusItem.menu = menu
        updatePortLabel()
        updateLoginItemLabel()
        refreshUpdateMenu()
    }

    private var updateDirectory: URL {
        paths.downloadsDirectory.appendingPathComponent("update", isDirectory: true)
    }

    private var stagedUpdateApp: URL {
        updateDirectory.appendingPathComponent("staged/AI2Apps.app", isDirectory: true)
    }

    private var updatePendingMarker: URL? {
        arguments.appBundleURL.map { app in
            app.deletingLastPathComponent().appendingPathComponent(
                ".\(app.lastPathComponent).update.pending"
            )
        }
    }

    private var canManageUpdates: Bool {
        // A sandboxed Login Item cannot inspect or replace its containing App.
        // The dedicated Update Broker will own this capability.
        guard !sandboxedPackage else { return false }
        guard arguments.isPackaged, let app = arguments.appBundleURL,
              let bundle = Bundle(url: app),
              bundle.object(forInfoDictionaryKey: "AI2AppsUpdateStagingProtocol") as? Int == 1,
              (try? app.resourceValues(forKeys: [.volumeIsReadOnlyKey]).volumeIsReadOnly) != true,
              FileManager.default.isWritableFile(atPath: app.deletingLastPathComponent().path) else {
            return false
        }
        let contents = app.appendingPathComponent("Contents", isDirectory: true)
        let required = [
            contents.appendingPathComponent("Helpers/AI2AppsUpdater"),
            contents.appendingPathComponent("Resources/Update/stage-update-candidate.py"),
            contents.appendingPathComponent("Library/AI2AppsLocal/Python/cpython-3.11/bin/python3.11"),
        ]
        return required.allSatisfy { FileManager.default.isExecutableFile(atPath: $0.path) }
    }

    private func refreshUpdateMenu() {
        checkUpdateMenuItem.isEnabled = canManageUpdates && updateProcess == nil
        installUpdateMenuItem.isEnabled = canManageUpdates && updateProcess == nil
            && stagedCandidateBuild != nil
            && FileManager.default.fileExists(atPath: stagedUpdateApp.path)
    }

    private func publishUpdateStatus(
        _ phase: UpdatePhase,
        message: String,
        candidateBuild: String? = nil,
        errorCode: String? = nil
    ) {
        let status = UpdateStatus(
            instanceID: arguments.instanceID,
            phase: phase,
            currentBuild: launchBuild,
            candidateBuild: candidateBuild,
            message: message,
            errorCode: errorCode
        )
        try? ContractCodec.save(
            status,
            to: paths.runDirectory.appendingPathComponent("update.json")
        )
        switch phase {
        case .idle: updateStatusMenuItem.title = "更新：尚未检查"
        case .checking: updateStatusMenuItem.title = "更新：正在验证"
        case .ready: updateStatusMenuItem.title = "更新：Build \(candidateBuild ?? "?") 可安装"
        case .installing: updateStatusMenuItem.title = "更新：正在安装"
        case .succeeded: updateStatusMenuItem.title = "更新：安装成功"
        case .failed: updateStatusMenuItem.title = "更新：失败"
        }
        refreshUpdateMenu()
    }

    private func updatePortLabel() {
        let configured = configuration.portMode == .automatic
            ? "自动"
            : String(configuration.configuredPort ?? 0)
        if let actualPort {
            portMenuItem.title = "端口：\(configured)（当前 \(actualPort)）"
        } else {
            portMenuItem.title = "端口：\(configured)"
        }
    }

    private func updateLoginItemLabel() {
        loginItemToggleMenuItem.state = configuration.startAtLogin ? .on : .off
        let statusURL = paths.runDirectory.appendingPathComponent("login-item.json")
        guard let status = try? ContractCodec.load(LoginItemStatus.self, from: statusURL),
              status.instanceID == arguments.instanceID else {
            loginItemMenuItem.title = "登录启动：尚未配置"
            return
        }
        switch status.phase {
        case .enabled:
            loginItemMenuItem.title = "登录启动：已启用"
        case .requiresApproval:
            loginItemMenuItem.title = "登录启动：等待系统批准"
        case .notRegistered, .notFound:
            loginItemMenuItem.title = "登录启动：未注册"
        case .skippedReadOnly:
            loginItemMenuItem.title = "登录启动：安装后启用"
        case .skippedDevelopment:
            loginItemMenuItem.title = "登录启动：开发模式跳过"
        case .failed:
            loginItemMenuItem.title = "登录启动：注册失败"
        }
    }

    private var canConfigureLoginItem: Bool {
        // The Launcher owns SMAppService registration for sandboxed packages.
        guard !sandboxedPackage else { return false }
        guard arguments.isPackaged, let appBundleURL = arguments.appBundleURL else {
            return false
        }
        let values = try? appBundleURL.resourceValues(forKeys: [.volumeIsReadOnlyKey])
        return values?.volumeIsReadOnly != true
    }

    @objc private func openAI2Apps() {
        if let application = runningAI2AppsShellApplication() {
            application.activate(options: [.activateAllWindows, .activateIgnoringOtherApps])
            return
        }
        let discoveredApp = mainBundleIdentifier.flatMap {
            NSWorkspace.shared.urlForApplication(withBundleIdentifier: $0)
        }
        guard let appBundleURL = discoveredApp ?? arguments.appBundleURL else {
            NSSound.beep()
            return
        }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        configuration.createsNewApplicationInstance = false
        NSWorkspace.shared.openApplication(
            at: appBundleURL,
            configuration: configuration
        ) { [weak self] _, error in
            guard let error else { return }
            DispatchQueue.main.async {
                self?.presentError(error)
            }
        }
    }

    private func startLocal() {
        statusMenuItem.title = "状态：正在启动"
        publishStatus(.starting, message: "正在启动 AI2Apps 服务…")
        Task {
            do {
                let ready = try await supervisor.start()
                actualPort = ready.descriptor.actualPort
                statusMenuItem.title = "状态：运行中"
                publishStatus(
                    .ready,
                    message: "AI2Apps 服务已就绪",
                    actualPort: ready.descriptor.actualPort
                )
                updatePortLabel()
                beginHealthMonitoring()
            } catch LocalSupervisorError.alreadyRunning {
                statusMenuItem.title = "状态：已在运行"
                publishStatus(.ready, message: "AI2Apps 服务已在运行")
            } catch LocalSupervisorError.portInUse(let conflict) {
                actualPort = nil
                statusMenuItem.title = "状态：端口 \(conflict.port) 被占用"
                publishStatus(
                    .failed,
                    message: "固定端口 \(conflict.port) 已被占用",
                    errorCode: "port_conflict"
                )
                updatePortLabel()
                presentError(LocalSupervisorError.portInUse(conflict))
            } catch {
                statusMenuItem.title = "状态：启动失败"
                publishStatus(
                    .failed,
                    message: "AI2Apps 服务启动失败",
                    errorCode: "local_start_failed"
                )
                presentError(error)
            }
        }
    }

    private func adoptOrStartLocal() {
        statusMenuItem.title = "状态：正在检查服务"
        publishStatus(.checking, message: "正在检查已有 AI2Apps 服务…")
        Task {
            do {
                if let ready = try await supervisor.adoptRunningLocal() {
                    actualPort = ready.descriptor.actualPort
                    statusMenuItem.title = "状态：运行中（已接管）"
                    publishStatus(
                        .ready,
                        message: "已接管运行中的 AI2Apps 服务",
                        actualPort: ready.descriptor.actualPort
                    )
                    updatePortLabel()
                    beginHealthMonitoring()
                } else {
                    startLocal()
                }
            } catch {
                statusMenuItem.title = "状态：现有服务验证失败"
                publishStatus(
                    .failed,
                    message: "已有 AI2Apps 服务验证失败",
                    errorCode: "local_adoption_failed"
                )
                presentError(error)
            }
        }
    }

    private func stopLocal(restart: Bool = false) {
        healthMonitor?.cancel()
        healthMonitor = nil
        statusMenuItem.title = "状态：正在停止"
        publishStatus(.stopping, message: "正在停止 AI2Apps 服务…")
        Task {
            await supervisor.stop()
            actualPort = nil
            statusMenuItem.title = "状态：已停止"
            publishStatus(.stopped, message: "AI2Apps 服务已停止")
            updatePortLabel()
            if restart {
                replaceSupervisor()
                startLocal()
            }
        }
    }

    private func beginHealthMonitoring() {
        healthMonitor?.cancel()
        healthMonitor = Task { [weak self] in
            var consecutiveFailures = 0
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self else { return }
                updateLoginItemLabel()
                if await supervisor.healthCheck() {
                    consecutiveFailures = 0
                    statusMenuItem.title = "状态：运行中"
                    publishStatus(.ready, message: "AI2Apps 服务运行正常")
                    continue
                }
                consecutiveFailures += 1
                statusMenuItem.title = "状态：连接异常（\(consecutiveFailures)/3）"
                publishStatus(
                    .degraded,
                    message: "AI2Apps 服务连接异常（\(consecutiveFailures)/3）",
                    errorCode: "local_health_failed"
                )
                if consecutiveFailures >= 3, configuration.autoRestart {
                    statusMenuItem.title = "状态：自动重启中"
                    publishStatus(.restarting, message: "正在自动重启 AI2Apps 服务…")
                    stopLocal(restart: true)
                    return
                }
            }
        }
    }

    private func replaceSupervisor() {
        supervisor = LocalProcessSupervisor(
            instanceID: arguments.instanceID,
            configuration: configuration,
            paths: paths,
            executable: arguments.runtimeExecutable,
            baseEnvironment: ProcessInfo.processInfo.environment.merging(
                controlCredentials.environment
            ) { _, required in required }
        )
    }

    private func publishStatus(
        _ phase: HelperPhase,
        message: String,
        actualPort: Int? = nil,
        errorCode: String? = nil
    ) {
        updateStatusIcon(for: phase)
        statusItem.button?.toolTip = "AI2Apps 服务 — \(arguments.instanceID.rawValue) — \(message)"
        let status = HelperStatus(
            instanceID: arguments.instanceID,
            phase: phase,
            message: message,
            actualPort: actualPort ?? self.actualPort,
            errorCode: errorCode
        )
        do {
            try ContractCodec.save(
                status,
                to: paths.runDirectory.appendingPathComponent("helper.json")
            )
        } catch {
            FileHandle.standardError.write(
                Data("AI2Apps Helper status: \(error)\n".utf8)
            )
        }
    }

    private func updateStatusIcon(for phase: HelperPhase) {
        guard let source = menuBarLogo else {
            // A packaged build is verified to contain the SVG. Keep the menu
            // reachable in an unpackaged developer run if that resource is
            // deliberately absent.
            statusItem.length = NSStatusItem.variableLength
            statusItem.button?.image = nil
            statusItem.button?.title = "AI2"
            return
        }
        let color: NSColor
        switch phase {
        case .ready:
            color = .black
        case .initializing, .checking, .starting, .restarting, .stopping,
             .degraded, .failed:
            color = NSColor(calibratedWhite: 0.48, alpha: 1)
        case .stopped, .helperExiting:
            color = NSColor(calibratedWhite: 0.78, alpha: 1)
        }
        let size = NSSize(width: 18, height: 18)
        let image = NSImage(size: size, flipped: false) { rect in
            source.draw(
                in: rect,
                from: .zero,
                operation: .sourceOver,
                fraction: 1
            )
            color.setFill()
            rect.fill(using: .sourceIn)
            return true
        }
        // State color is meaningful, so this must not be converted into a
        // monochrome macOS template image.
        image.isTemplate = false
        statusItem.length = NSStatusItem.squareLength
        statusItem.button?.title = ""
        statusItem.button?.image = image
    }

    private func handleControlRequest(
        _ request: HelperControlRequest
    ) async -> HelperControlResponse {
        do {
            if request.operation == "local.restart" {
                stopLocal(restart: true)
                return .success(
                    requestID: request.requestID,
                    result: HelperControlResult(status: "restarting")
                )
            }
            let profileID = try BrowserAgentProfileID.derive(
                instanceID: arguments.instanceID,
                actorUserID: request.actorUserID
            ).rawValue
            if request.operation == "browser.release" {
                return releaseBrowserAgent(
                    requestID: request.requestID,
                    profileID: profileID
                )
            }
            if ["browser.renew", "browser.pause", "browser.resume"].contains(
                request.operation
            ) {
                return updateBrowserAgentLease(
                    requestID: request.requestID,
                    profileID: profileID,
                    operation: request.operation
                )
            }
            guard let executable = arguments.aceFoxExecutable else {
                return .failure(
                    requestID: request.requestID,
                    error: "AceFox Agent runtime is unavailable"
                )
            }
            let initialURL: URL?
            if let requestedURL = request.initialURL {
                guard let parsed = URL(string: requestedURL) else {
                    throw ContractError.invalidField(field: "initial_url", reason: "is invalid")
                }
                initialURL = parsed
            } else {
                initialURL = nil
            }
            let automation = try BrowserAgentAutomation(
                port: Self.availableLoopbackPort(),
                token: Self.randomToken()
            )
            let plan = try BrowserAgentLaunchPlan(
                executable: executable,
                instanceID: arguments.instanceID,
                actorUserID: request.actorUserID,
                paths: paths,
                initialURL: initialURL,
                automation: automation,
                inheritedEnvironment: ProcessInfo.processInfo.environment
            )
            if let existing = browserAgents[profileID], !existing.application.isTerminated {
                existing.application.activate(options: [.activateAllWindows])
                auditBrowserEvent(
                    action: "browser.focus",
                    profileID: profileID,
                    processID: existing.application.processIdentifier,
                    outcome: "focused"
                )
                return .success(
                    requestID: request.requestID,
                    result: HelperControlResult(
                        status: "focused",
                        profileID: profileID,
                        processID: existing.application.processIdentifier,
                        automation: Self.controlResult(for: existing.automation)
                    )
                )
            }
            try FileManager.default.createDirectory(
                at: plan.profileDirectory,
                withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
            let agentBundleURL = plan.executable
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
            guard agentBundleURL.pathExtension == "app" else {
                throw ContractError.invalidField(
                    field: "acefox.executable",
                    reason: "must be inside an App bundle"
                )
            }
            let openConfiguration = NSWorkspace.OpenConfiguration()
            openConfiguration.arguments = plan.arguments
            openConfiguration.environment = plan.environment
            openConfiguration.activates = true
            openConfiguration.createsNewApplicationInstance = true
            let application = try await openBrowserApplication(
                at: agentBundleURL,
                configuration: openConfiguration
            )
            browserAgents[profileID] = ManagedBrowserAgent(
                application: application,
                automation: automation,
                lease: BrowserAgentLease()
            )
            auditBrowserEvent(
                action: "browser.launch",
                profileID: profileID,
                processID: application.processIdentifier,
                outcome: "launched"
            )
            return .success(
                requestID: request.requestID,
                result: HelperControlResult(
                    status: "launched",
                    profileID: profileID,
                    processID: application.processIdentifier,
                    automation: Self.controlResult(for: automation)
                )
            )
        } catch {
            return .failure(requestID: request.requestID, error: String(describing: error))
        }
    }

    private func releaseBrowserAgent(
        requestID: String,
        profileID: String
    ) -> HelperControlResponse {
        guard let existing = browserAgents.removeValue(forKey: profileID) else {
            auditBrowserEvent(
                action: "browser.release",
                profileID: profileID,
                processID: 0,
                outcome: "not_running"
            )
            return .success(
                requestID: requestID,
                result: HelperControlResult(
                    status: "not_running",
                    profileID: profileID
                )
            )
        }
        let processID = existing.application.processIdentifier
        guard !existing.application.isTerminated else {
            auditBrowserEvent(
                action: "browser.release",
                profileID: profileID,
                processID: processID,
                outcome: "already_exited"
            )
            return .success(
                requestID: requestID,
                result: HelperControlResult(
                    status: "not_running",
                    profileID: profileID,
                    processID: processID
                )
            )
        }
        auditBrowserEvent(
            action: "browser.release",
            profileID: profileID,
            processID: processID,
            outcome: "terminate_requested"
        )
        existing.application.terminate()
        return .success(
            requestID: requestID,
            result: HelperControlResult(
                status: "released",
                profileID: profileID,
                processID: processID
            )
        )
    }

    private func updateBrowserAgentLease(
        requestID: String,
        profileID: String,
        operation: String
    ) -> HelperControlResponse {
        guard var existing = browserAgents[profileID], !existing.application.isTerminated else {
            browserAgents.removeValue(forKey: profileID)
            return .failure(
                requestID: requestID,
                error: "Browser Agent is not running"
            )
        }
        let status: String
        switch operation {
        case "browser.renew":
            existing.lease.renew()
            status = "renewed"
        case "browser.pause":
            existing.lease.pause()
            status = "paused"
        case "browser.resume":
            existing.lease.resume()
            status = "resumed"
        default:
            return .failure(requestID: requestID, error: "Unsupported lease operation")
        }
        browserAgents[profileID] = existing
        if operation != "browser.renew" {
            auditBrowserEvent(
                action: operation,
                profileID: profileID,
                processID: existing.application.processIdentifier,
                outcome: status
            )
        }
        return .success(
            requestID: requestID,
            result: HelperControlResult(
                status: status,
                profileID: profileID,
                processID: existing.application.processIdentifier
            )
        )
    }

    private func beginBrowserAgentLeaseMonitoring() {
        browserAgentLeaseMonitor?.cancel()
        browserAgentLeaseMonitor = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self else { return }
                let expiredProfileIDs = browserAgents.compactMap { profileID, agent in
                    agent.lease.isExpired() ? profileID : nil
                }
                for profileID in expiredProfileIDs {
                    guard let expired = browserAgents.removeValue(forKey: profileID) else {
                        continue
                    }
                    auditBrowserEvent(
                        action: "browser.expire",
                        profileID: profileID,
                        processID: expired.application.processIdentifier,
                        outcome: "idle_timeout"
                    )
                    if !expired.application.isTerminated {
                        expired.application.terminate()
                    }
                }
            }
        }
    }

    private func openBrowserApplication(
        at url: URL,
        configuration: NSWorkspace.OpenConfiguration
    ) async throws -> NSRunningApplication {
        try await withCheckedThrowingContinuation { continuation in
            NSWorkspace.shared.openApplication(at: url, configuration: configuration) {
                application,
                error in
                if let application {
                    continuation.resume(returning: application)
                } else {
                    continuation.resume(throwing: error ?? ContractError.invalidField(
                        field: "acefox.launch",
                        reason: "LaunchServices returned no application"
                    ))
                }
            }
        }
    }

    @objc private func browserAgentApplicationDidTerminate(_ notification: Notification) {
        guard let application = notification.userInfo?[NSWorkspace.applicationUserInfoKey]
            as? NSRunningApplication,
              let entry = browserAgents.first(where: {
                  $0.value.application.processIdentifier == application.processIdentifier
              }) else {
            return
        }
        browserAgents.removeValue(forKey: entry.key)
        auditBrowserEvent(
            action: "browser.exit",
            profileID: entry.key,
            processID: application.processIdentifier,
            outcome: "terminated"
        )
    }

    private func auditBrowserEvent(
        action: String,
        profileID: String,
        processID: Int32,
        outcome: String
    ) {
        let event = BrowserAgentAuditEvent(
            timestamp: Date(),
            action: action,
            profileID: profileID,
            processID: processID,
            outcome: outcome
        )
        do {
            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
            var data = try encoder.encode(event)
            data.append(0x0A)
            let url = paths.logDirectory.appendingPathComponent("browser-agent-audit.jsonl")
            let descriptor = Darwin.open(
                url.path,
                O_WRONLY | O_CREAT | O_APPEND | O_NOFOLLOW,
                S_IRUSR | S_IWUSR
            )
            guard descriptor >= 0 else {
                throw ContractError.invalidField(
                    field: "browser_agent.audit",
                    reason: String(cString: strerror(errno))
                )
            }
            defer { close(descriptor) }
            guard fchmod(descriptor, S_IRUSR | S_IWUSR) == 0 else {
                throw ContractError.invalidField(
                    field: "browser_agent.audit_mode",
                    reason: String(cString: strerror(errno))
                )
            }
            try data.withUnsafeBytes { bytes in
                var offset = 0
                while offset < bytes.count {
                    let count = Darwin.write(
                        descriptor,
                        bytes.baseAddress!.advanced(by: offset),
                        bytes.count - offset
                    )
                    guard count > 0 else {
                        throw ContractError.invalidField(
                            field: "browser_agent.audit_write",
                            reason: String(cString: strerror(errno))
                        )
                    }
                    offset += count
                }
            }
        } catch {
            FileHandle.standardError.write(
                Data("AI2Apps Browser Agent audit: \(error)\n".utf8)
            )
        }
    }

    private static func randomToken() throws -> String {
        var random = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else {
            throw ContractError.invalidField(
                field: "browser_agent.token",
                reason: "secure random generation failed"
            )
        }
        return random.map { String(format: "%02x", $0) }.joined()
    }

    private static func availableLoopbackPort() throws -> Int {
        let descriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else {
            throw ContractError.invalidField(field: "browser_agent.port", reason: "socket creation failed")
        }
        defer { close(descriptor) }
        var address = sockaddr_in()
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                Darwin.bind(
                    descriptor,
                    socketAddress,
                    socklen_t(MemoryLayout<sockaddr_in>.size)
                )
            }
        }
        guard bound == 0 else {
            throw ContractError.invalidField(field: "browser_agent.port", reason: "ephemeral bind failed")
        }
        var result = sockaddr_in()
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let resolved = withUnsafeMutablePointer(to: &result) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                getsockname(descriptor, socketAddress, &length)
            }
        }
        guard resolved == 0 else {
            throw ContractError.invalidField(field: "browser_agent.port", reason: "getsockname failed")
        }
        return Int(UInt16(bigEndian: result.sin_port))
    }

    private static func controlResult(
        for automation: BrowserAgentAutomation
    ) -> HelperBrowserAutomation {
        HelperBrowserAutomation(
            transport: "webdriver-bidi",
            webSocketURL: automation.webSocketURL.absoluteString,
            authorization: "Bearer \(automation.token)"
        )
    }

    @objc private func startLocalAction() {
        startLocal()
    }

    @objc private func stopLocalAction() {
        stopLocal()
    }

    @objc private func restartLocalAction() {
        stopLocal(restart: true)
    }

    @objc private func configurePort() {
        let alert = NSAlert()
        alert.messageText = "配置 AI2Apps 服务端口"
        alert.informativeText = "留空表示自动分配；固定端口范围为 1024–65535。"
        alert.addButton(withTitle: "保存并重启")
        alert.addButton(withTitle: "取消")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        field.placeholderString = "自动"
        if let port = configuration.configuredPort {
            field.stringValue = String(port)
        }
        alert.accessoryView = field
        NSApp.activate(ignoringOtherApps: true)
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        do {
            let value = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            let next: LocalConfiguration
            if value.isEmpty {
                next = LocalConfiguration(
                    portMode: .automatic,
                    startAtLogin: configuration.startAtLogin,
                    autoRestart: configuration.autoRestart
                )
            } else {
                guard let port = Int(value) else {
                    throw ContractError.invalidField(field: "configured_port", reason: "must be a number")
                }
                next = LocalConfiguration(
                    portMode: .fixed,
                    configuredPort: port,
                    startAtLogin: configuration.startAtLogin,
                    autoRestart: configuration.autoRestart
                )
            }
            try next.validate()
            try ContractCodec.save(next, to: paths.configDirectory.appendingPathComponent("local.json"))
            configuration = next
            updatePortLabel()
            stopLocal(restart: true)
        } catch {
            presentError(error)
        }
    }

    @objc private func toggleLoginItem() {
        guard canConfigureLoginItem else {
            NSSound.beep()
            return
        }
        do {
            let next = LocalConfiguration(
                portMode: configuration.portMode,
                configuredPort: configuration.configuredPort,
                startAtLogin: !configuration.startAtLogin,
                autoRestart: configuration.autoRestart
            )
            try next.validate()
            try ContractCodec.save(
                next,
                to: paths.configDirectory.appendingPathComponent("local.json")
            )
            configuration = next
            updateLoginItemLabel()
            try runLoginItemUpdater()
        } catch {
            presentError(error)
        }
    }

    private func runLoginItemUpdater() throws {
        guard let appBundleURL = arguments.appBundleURL,
              let appBundle = Bundle(url: appBundleURL),
              let executableURL = appBundle.executableURL else {
            throw ContractError.invalidField(
                field: "app_bundle",
                reason: "cannot resolve the packaged launcher"
            )
        }
        let updater = Process()
        updater.executableURL = executableURL
        updater.arguments = ["--update-login-item-only"]
        updater.standardOutput = FileHandle.nullDevice
        updater.standardError = FileHandle.nullDevice
        updater.terminationHandler = { [weak self] process in
            Task { @MainActor in
                self?.updateLoginItemLabel()
                guard process.terminationStatus != 0 else { return }
                self?.presentError(
                    ContractError.invalidField(
                        field: "start_at_login",
                        reason: "system login item update failed"
                    )
                )
            }
        }
        try updater.run()
    }

    private func appBuild(at app: URL) throws -> String {
        let infoURL = app.appendingPathComponent("Contents/Info.plist")
        let data = try Data(contentsOf: infoURL)
        guard let info = try PropertyListSerialization.propertyList(
            from: data,
            format: nil
        ) as? [String: Any],
            let build = info["CFBundleVersion"] as? String,
            !build.isEmpty,
            build.allSatisfy({ $0.isASCII && $0.isNumber }),
            let number = Int(build), number > (Int(launchBuild) ?? 0) else {
            throw ContractError.invalidField(
                field: "candidate_build",
                reason: "must be newer than the running App"
            )
        }
        return build
    }

    private func updateLogHandle() throws -> FileHandle {
        try FileManager.default.createDirectory(
            at: paths.logDirectory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        let url = paths.logDirectory.appendingPathComponent("update.log")
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(
                atPath: url.path,
                contents: nil,
                attributes: [.posixPermissions: 0o600]
            )
        }
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o600],
            ofItemAtPath: url.path
        )
        let handle = try FileHandle(forWritingTo: url)
        try handle.seekToEnd()
        return handle
    }

    private func verifyCode(at url: URL, deep: Bool) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/codesign")
        process.arguments = deep
            ? ["--verify", "--deep", "--strict", url.path]
            : ["--verify", "--strict", url.path]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw ContractError.invalidField(
                field: "update_signature",
                reason: "signed update component verification failed"
            )
        }
    }

    private func prepareRealPrivateDirectory(_ url: URL) throws {
        var status = stat()
        if lstat(url.path, &status) == 0 {
            guard status.st_mode & S_IFMT == S_IFDIR else {
                throw ContractError.invalidField(
                    field: "update_directory",
                    reason: "must be a real directory"
                )
            }
        } else if errno == ENOENT {
            try FileManager.default.createDirectory(
                at: url,
                withIntermediateDirectories: false,
                attributes: [.posixPermissions: 0o700]
            )
        } else {
            throw ContractError.invalidField(
                field: "update_directory",
                reason: "cannot inspect private update directory"
            )
        }
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o700],
            ofItemAtPath: url.path
        )
    }

    private func requireRealRegularFile(_ url: URL, field: String) throws {
        var status = stat()
        guard lstat(url.path, &status) == 0, status.st_mode & S_IFMT == S_IFREG else {
            throw ContractError.invalidField(field: field, reason: "must be a real regular file")
        }
    }

    private func prepareUpdateDirectories() throws {
        try prepareRealPrivateDirectory(paths.supportRoot)
        try prepareRealPrivateDirectory(paths.downloadsDirectory)
        try prepareRealPrivateDirectory(updateDirectory)
        try prepareRealPrivateDirectory(stagedUpdateApp.deletingLastPathComponent())
    }

    @objc private func checkDownloadedUpdate() {
        guard canManageUpdates, updateProcess == nil,
              let appBundle = arguments.appBundleURL else {
            NSSound.beep()
            return
        }
        let dmg = updateDirectory.appendingPathComponent("AI2Apps.dmg")
        let metadata = updateDirectory.appendingPathComponent("AI2Apps.release.json")
        guard FileManager.default.fileExists(atPath: dmg.path),
              FileManager.default.fileExists(atPath: metadata.path) else {
            publishUpdateStatus(
                .failed,
                message: "未找到已下载的更新文件",
                errorCode: "candidate_missing"
            )
            return
        }

        do {
            try prepareUpdateDirectories()
            try requireRealRegularFile(dmg, field: "update_dmg")
            try requireRealRegularFile(metadata, field: "update_metadata")
            if FileManager.default.fileExists(atPath: stagedUpdateApp.path) {
                try FileManager.default.removeItem(at: stagedUpdateApp)
            }
            stagedCandidateBuild = nil
            let contents = appBundle.appendingPathComponent("Contents", isDirectory: true)
            let python = contents.appendingPathComponent(
                "Library/AI2AppsLocal/Python/cpython-3.11/bin/python3.11"
            )
            let script = contents.appendingPathComponent(
                "Resources/Update/stage-update-candidate.py"
            )
            let log = try updateLogHandle()
            let process = Process()
            process.executableURL = python
            var pythonEnvironment = ProcessInfo.processInfo.environment
            pythonEnvironment["PYTHONDONTWRITEBYTECODE"] = "1"
            pythonEnvironment["PYTHONNOUSERSITE"] = "1"
            process.environment = pythonEnvironment
            process.arguments = [
                "-I",
                "-B",
                script.path,
                "--installed-app", appBundle.path,
                "--dmg", dmg.path,
                "--metadata", metadata.path,
                "--output-app", stagedUpdateApp.path,
            ]
            process.standardOutput = log
            process.standardError = log
            process.terminationHandler = { [weak self] process in
                try? log.close()
                Task { @MainActor in
                    guard let self else { return }
                    self.updateProcess = nil
                    if process.terminationStatus == 0,
                       let build = try? self.appBuild(at: self.stagedUpdateApp) {
                        self.stagedCandidateBuild = build
                        self.publishUpdateStatus(
                            .ready,
                            message: "更新已验证，可以安装",
                            candidateBuild: build
                        )
                    } else {
                        self.stagedCandidateBuild = nil
                        self.publishUpdateStatus(
                            .failed,
                            message: "更新验证失败，请查看日志",
                            errorCode: "candidate_verification_failed"
                        )
                    }
                }
            }
            updateProcess = process
            publishUpdateStatus(.checking, message: "正在验证已下载更新")
            try process.run()
        } catch {
            updateProcess = nil
            stagedCandidateBuild = nil
            publishUpdateStatus(
                .failed,
                message: "无法启动更新验证",
                errorCode: "candidate_check_failed"
            )
            presentError(error)
        }
    }

    @objc private func installStagedUpdate() {
        guard canManageUpdates, updateProcess == nil,
              let appBundle = arguments.appBundleURL,
              let candidateBuild = stagedCandidateBuild,
              FileManager.default.fileExists(atPath: stagedUpdateApp.path),
              Bundle(url: appBundle)?.bundleIdentifier != nil,
              let marker = updatePendingMarker else {
            NSSound.beep()
            return
        }
        let alert = NSAlert()
        alert.messageText = "安装 AI2Apps 更新？"
        alert.informativeText = "AI2Apps 窗口将退出并在验证成功后重新打开。Helper 和 AI2Apps 服务会继续运行；失败时自动恢复当前版本。"
        alert.addButton(withTitle: "安装并退出")
        alert.addButton(withTitle: "取消")
        NSApp.activate(ignoringOtherApps: true)
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        let descriptorURL = paths.runDirectory.appendingPathComponent("shell.json")
        guard let shell = try? ContractCodec.load(ShellRunDescriptor.self, from: descriptorURL),
              let expectedExecutable = arguments.aceFoxExecutable,
              ShellProcessIdentityValidator().validate(
                  shell,
                  expectedInstanceID: arguments.instanceID,
                  expectedAppBundle: appBundle,
                  expectedExecutable: expectedExecutable,
                  liveExecutablePath: { [weak self] pid in
                      self?.processExecutablePath(pid: pid_t(pid))
                  }
              ) else {
            publishUpdateStatus(
                .failed,
                message: "无法验证当前 AI2Apps 窗口进程",
                candidateBuild: candidateBuild,
                errorCode: "shell_identity_invalid"
            )
            return
        }
        let backup = appBundle.deletingLastPathComponent().appendingPathComponent(
            "\(appBundle.deletingPathExtension().lastPathComponent).previous.app"
        )
        guard !FileManager.default.fileExists(atPath: backup.path) else {
            publishUpdateStatus(
                .failed,
                message: "上一版本备份仍存在，请先处理备份",
                candidateBuild: candidateBuild,
                errorCode: "backup_exists"
            )
            return
        }

        var externalUpdater: URL?
        var log: FileHandle?
        do {
            let markerDescriptor = open(
                marker.path,
                O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC,
                0o600
            )
            guard markerDescriptor >= 0 else {
                throw ContractError.invalidField(
                    field: "update_pending",
                    reason: "another update is already pending"
                )
            }
            close(markerDescriptor)

            let sourceUpdater = appBundle.appendingPathComponent(
                "Contents/Helpers/AI2AppsUpdater"
            )
            try verifyCode(at: sourceUpdater, deep: false)
            let executorDirectory = paths.runtimeDirectory.appendingPathComponent(
                "update-executors",
                isDirectory: true
            )
            try FileManager.default.createDirectory(
                at: executorDirectory,
                withIntermediateDirectories: true,
                attributes: [.posixPermissions: 0o700]
            )
            try FileManager.default.setAttributes(
                [.posixPermissions: 0o700],
                ofItemAtPath: executorDirectory.path
            )
            let copiedUpdater = executorDirectory.appendingPathComponent(
                "AI2AppsUpdater-\(UUID().uuidString)"
            )
            try FileManager.default.copyItem(at: sourceUpdater, to: copiedUpdater)
            try FileManager.default.setAttributes(
                [.posixPermissions: 0o700],
                ofItemAtPath: copiedUpdater.path
            )
            try verifyCode(at: copiedUpdater, deep: false)
            externalUpdater = copiedUpdater

            let updateLog = try updateLogHandle()
            log = updateLog
            let process = Process()
            process.executableURL = copiedUpdater
            process.arguments = [
                "--installed-app", appBundle.path,
                "--candidate-app", stagedUpdateApp.path,
                "--backup-app", backup.path,
                "--pending-marker", marker.path,
                "--wait-pid", String(shell.processID),
            ]
            process.standardOutput = updateLog
            process.standardError = updateLog
            process.terminationHandler = { [weak self] process in
                try? updateLog.close()
                Task { @MainActor in
                    guard let self else { return }
                    self.updateProcess = nil
                    try? FileManager.default.removeItem(at: copiedUpdater)
                    try? FileManager.default.removeItem(at: marker)
                    if process.terminationStatus == 0 {
                        try? FileManager.default.removeItem(at: self.stagedUpdateApp)
                        self.stagedCandidateBuild = nil
                        self.publishUpdateStatus(
                            .succeeded,
                            message: "更新已安装，正在重新打开 AI2Apps",
                            candidateBuild: candidateBuild
                        )
                        self.openAI2Apps()
                    } else {
                        self.publishUpdateStatus(
                            .failed,
                            message: "更新失败，当前版本已保留或恢复",
                            candidateBuild: candidateBuild,
                            errorCode: "installation_failed"
                        )
                    }
                }
            }
            updateProcess = process
            publishUpdateStatus(
                .installing,
                message: "正在等待 AI2Apps 窗口退出并安装更新",
                candidateBuild: candidateBuild
            )
            try process.run()
            guard kill(pid_t(shell.processID), SIGTERM) == 0 else {
                process.terminate()
                throw ContractError.invalidField(
                    field: "shell",
                    reason: "cannot request the current Shell to terminate"
                )
            }
        } catch {
            updateProcess = nil
            if let externalUpdater {
                try? FileManager.default.removeItem(at: externalUpdater)
            }
            try? FileManager.default.removeItem(at: marker)
            try? log?.close()
            publishUpdateStatus(
                .failed,
                message: "无法启动更新安装",
                candidateBuild: candidateBuild,
                errorCode: "installation_start_failed"
            )
            presentError(error)
        }
    }

    private func processExecutablePath(pid: pid_t) -> String? {
        guard pid > 1, kill(pid, 0) == 0 || errno == EPERM else { return nil }
        // proc_pidpath documents a buffer of up to 4 * MAXPATHLEN. The macro
        // itself is not imported by Swift because it is an expression macro.
        var buffer = [CChar](repeating: 0, count: 4096)
        let length = proc_pidpath(pid, &buffer, UInt32(buffer.count))
        guard length > 0 else { return nil }
        let bytes = buffer.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }
        return String(decoding: bytes, as: UTF8.self)
    }

    @objc private func copyLocalAddress() {
        guard let actualPort else { return }
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString("http://127.0.0.1:\(actualPort)", forType: .string)
    }

    @objc private func openLogs() {
        try? FileManager.default.createDirectory(
            at: paths.logDirectory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        NSWorkspace.shared.open(paths.logDirectory)
    }

    @objc private func exportDiagnostics() {
        do {
            let helperStatus = try? ContractCodec.load(
                HelperStatus.self,
                from: paths.runDirectory.appendingPathComponent("helper.json")
            )
            let localDescriptor = try? ContractCodec.load(
                LocalRunDescriptor.self,
                from: paths.runDirectory.appendingPathComponent("local.json")
            )
            let appBundle = arguments.appBundleURL.flatMap { Bundle(url: $0) }
            let productVersion = appBundle?.object(
                forInfoDictionaryKey: "CFBundleShortVersionString"
            ) as? String ?? "development"
            #if arch(arm64)
            let architecture = "arm64"
            #elseif arch(x86_64)
            let architecture = "x86_64"
            #else
            let architecture = "unknown"
            #endif
            let snapshot = DiagnosticSnapshot(
                instanceID: arguments.instanceID,
                productVersion: productVersion,
                runtimeVersion: localDescriptor?.runtimeVersion,
                operatingSystem: ProcessInfo.processInfo.operatingSystemVersionString,
                architecture: architecture,
                helperPhase: helperStatus?.phase ?? .degraded,
                helperProcessID: ProcessInfo.processInfo.processIdentifier,
                localProcessID: localDescriptor?.processID,
                localBootID: localDescriptor?.bootID,
                portMode: configuration.portMode,
                configuredPort: configuration.configuredPort,
                actualPort: actualPort,
                browserAgentCount: browserAgents.count
            )
            let timestamp = Int(Date().timeIntervalSince1970)
            let destination = paths.diagnosticsDirectory.appendingPathComponent(
                "diagnostic-\(timestamp).json"
            )
            try ContractCodec.save(snapshot, to: destination, mode: 0o600)
            NSWorkspace.shared.activateFileViewerSelecting([destination])
        } catch {
            presentError(error)
        }
    }

    @objc private func quitAll() {
        guard updateProcess == nil else {
            NSSound.beep()
            return
        }
        if let application = runningAI2AppsShellApplication() {
            let alert = NSAlert()
            alert.alertStyle = .warning
            alert.messageText = "AI2Apps 正在运行"
            alert.informativeText = "退出 AI2Apps 服务后，当前 AI2Apps 窗口将无法继续使用本地功能。是否同时退出 AI2Apps？"
            alert.addButton(withTitle: "退出 AI2Apps 和服务")
            alert.addButton(withTitle: "仅退出服务")
            alert.addButton(withTitle: "取消")
            NSApp.activate(ignoringOtherApps: true)
            let response = alert.runModal()
            if response == .alertThirdButtonReturn {
                return
            }
            if response == .alertFirstButtonReturn {
                application.terminate()
            }
        }
        NSApp.terminate(nil)
    }

    private func runningAI2AppsShellApplication() -> NSRunningApplication? {
        guard let appBundle = arguments.appBundleURL,
              let expectedExecutable = arguments.aceFoxExecutable else {
            return nil
        }
        let descriptorURL = paths.runDirectory.appendingPathComponent("shell.json")
        guard let shell = try? ContractCodec.load(
            ShellRunDescriptor.self,
            from: descriptorURL
        ),
            ShellProcessIdentityValidator().validate(
                shell,
                expectedInstanceID: arguments.instanceID,
                expectedAppBundle: appBundle,
                expectedExecutable: expectedExecutable,
                liveExecutablePath: { [weak self] pid in
                    self?.processExecutablePath(pid: pid_t(pid))
                }
            ),
            let application = NSRunningApplication(
                processIdentifier: shell.processID
            ),
            !application.isTerminated else {
            return nil
        }
        return application
    }

    private func presentError(_ error: Error) {
        let alert = NSAlert(error: error)
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }
}

do {
    let arguments = try HelperArguments(
        arguments: CommandLine.arguments,
        helperBundleURL: Bundle.main.bundleURL
    )
    try validatePackagedRuntime(arguments: arguments)
    let paths = try InstancePaths.packaged(instanceID: arguments.instanceID)
    let instanceLock = try HelperInstanceLock(paths: paths)
    let controlCredentials = try HelperControlCredentials(
        instanceID: arguments.instanceID,
        paths: paths
    )
    let application = NSApplication.shared
    let delegate = HelperDelegate(
        arguments: arguments,
        paths: paths,
        instanceLock: instanceLock,
        controlCredentials: controlCredentials
    )
    application.delegate = delegate
    application.run()
    _ = delegate
} catch {
    FileHandle.standardError.write(Data("AI2Apps Helper: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}
