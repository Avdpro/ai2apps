import AI2AppsContracts
import AI2AppsSupervisorCore
import AI2AppsUpdateCore
import AppKit
import Darwin
import Foundation
import Security

private typealias HelperArguments = HelperLaunchConfiguration

private func validatedDevelopmentSourceRoot() throws -> URL? {
    let development = Bundle.main.object(
        forInfoDictionaryKey: "AI2AppsDevelopment"
    ) as? Bool == true
    guard development,
          let rawRoot = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsDevelopmentSourceRoot"
          ) as? String else {
        return nil
    }
    guard rawRoot.hasPrefix("/") else {
        throw ContractError.invalidField(
            field: "development_source_root",
            reason: "must be absolute"
        )
    }
    let root = URL(fileURLWithPath: rawRoot, isDirectory: true)
        .standardizedFileURL
    var isDirectory: ObjCBool = false
    guard FileManager.default.fileExists(
        atPath: root.appendingPathComponent("ai2apps/__init__.py").path,
        isDirectory: &isDirectory
    ), !isDirectory.boolValue else {
        throw ContractError.invalidField(
            field: "development_source_root",
            reason: "must contain ai2apps/__init__.py"
        )
    }
    return root
}

private func makeLocalSupervisor(
    arguments: HelperArguments,
    configuration: LocalConfiguration,
    paths: InstancePaths,
    controlCredentials: HelperControlCredentials,
    developmentBuild: Bool,
    developmentSourceRoot: URL?
) -> LocalProcessSupervisor {
    var environment = ProcessInfo.processInfo.environment.merging(
        controlCredentials.environment
    ) { _, required in required }
    if developmentBuild {
        // Development Runtime packages are intentionally accepted only by
        // development builds. Release Helpers never receive this marker.
        environment["AI2APPS_ALLOW_DEVELOPMENT_RUNTIME"] = "1"
    }
    return LocalProcessSupervisor(
        instanceID: arguments.instanceID,
        configuration: configuration,
        paths: paths,
        executable: arguments.runtimeExecutable,
        baseEnvironment: environment,
        developmentSourceRoot: developmentSourceRoot
    )
}

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
private final class HelperDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
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
    private let statusMenuItem = NSMenuItem(title: L("正在初始化…", "Initializing…"), action: nil, keyEquivalent: "")
    private let portMenuItem = NSMenuItem(title: L("端口：自动", "Port: Automatic"), action: nil, keyEquivalent: "")
    private let modelStorageMenuItem = NSMenuItem(
        title: L("模型存储：本实例私有", "Model storage: Private to this instance"),
        action: nil,
        keyEquivalent: ""
    )
    private let loginItemMenuItem = NSMenuItem(title: L("登录启动：尚未配置", "Launch at login: Not configured"), action: nil, keyEquivalent: "")
    private let loginItemToggleMenuItem = NSMenuItem(
        title: L("登录时启动", "Launch at login"),
        action: nil,
        keyEquivalent: ""
    )
    private let updateStatusMenuItem = NSMenuItem(
        title: L("更新：尚未检查", "Update: Not checked"),
        action: nil,
        keyEquivalent: ""
    )
    private let checkUpdateMenuItem = NSMenuItem(
        title: L("检查更新", "Check for updates"),
        action: nil,
        keyEquivalent: ""
    )
    private let installUpdateMenuItem = NSMenuItem(
        title: L("安装更新并退出 AI2Apps…", "Install update and quit AI2Apps…"),
        action: nil,
        keyEquivalent: ""
    )
    private let launchBuild: String
    private let mainBundleIdentifier: String?
    private let appDisplayName: String
    private let sandboxedPackage: Bool
    private let developmentBuild: Bool
    private let developmentSourceRoot: URL?
    private let allowsInstanceDataReset: Bool
    private var actualPort: Int?
    private var healthMonitor: Task<Void, Never>?
    private var browserAgentLeaseMonitor: Task<Void, Never>?
    private var controlServer: HelperControlServer?
    private var browserAgents: [String: ManagedBrowserAgent] = [:]
    private var updateProcess: Process?
    private var testEnvironmentProcess: Process?
    private let testEnvironmentMenuItem = NSMenuItem(title: L("启动测试环境", "Start test environment"), action: nil, keyEquivalent: "")
    private var updateDownloadTask: Task<Void, Never>?
    private var periodicUpdateTask: Task<Void, Never>?
    private var updateTipPopover: NSPopover?
    private var updateTipDismissalTask: Task<Void, Never>?
    private var stagedCandidateBuild: String?
    private var currentUpdatePhase: UpdatePhase = .idle
    private var currentUpdateMessage = L("尚未检查更新", "Updates not checked")
    private var terminationTask: Task<Void, Never>?
    private var resetInProgress = false
    private var serviceStoppedForTermination = false
    private var preserveLocalForUpdateHandoff = false
    private var currentHelperPhase: HelperPhase = .initializing
    private var currentHelperMessage = L("正在初始化…", "Initializing…")
    private lazy var menuBarLogo: NSImage? = {
        guard let url = Bundle.main.url(
            forResource: "menubar-logo",
            withExtension: "svg"
        ) else {
            return nil
        }
        return NSImage(contentsOf: url)
    }()
    private lazy var menuBarUpdateLogo: NSImage? = {
        guard let url = Bundle.main.url(
            forResource: "menubar-logo-update",
            withExtension: "svg"
        ) else {
            return nil
        }
        return NSImage(contentsOf: url)
    }()
    private lazy var menuBarWorkLogo: NSImage? = {
        guard let url = Bundle.main.url(
            forResource: "menubar-logo-work",
            withExtension: "svg"
        ) else {
            return nil
        }
        return NSImage(contentsOf: url)
    }()
    private lazy var menuBarReadyLogo: NSImage? = {
        guard let url = Bundle.main.url(
            forResource: "menubar-logo-ready",
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
        controlCredentials: HelperControlCredentials,
        developmentSourceRoot: URL? = nil
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
        appDisplayName = arguments.appBundleURL
            .flatMap { Bundle(url: $0) }
            .flatMap {
                ($0.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String)
                    ?? ($0.object(forInfoDictionaryKey: "CFBundleName") as? String)
            } ?? "AI2Apps"
        sandboxedPackage = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsApplicationGroupIdentifier"
        ) as? String != nil
        let isDevelopmentBuild = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsDevelopment"
        ) as? Bool == true
        developmentBuild = isDevelopmentBuild
        self.developmentSourceRoot = developmentSourceRoot
        allowsInstanceDataReset = Bundle.main.object(
            forInfoDictionaryKey: "AI2AppsAllowInstanceDataReset"
        ) as? Bool == true
        let configURL = paths.configDirectory.appendingPathComponent("local.json")
        configuration = (try? ContractCodec.load(LocalConfiguration.self, from: configURL)) ?? LocalConfiguration()
        supervisor = makeLocalSupervisor(
            arguments: arguments,
            configuration: configuration,
            paths: paths,
            controlCredentials: controlCredentials,
            developmentBuild: isDevelopmentBuild,
            developmentSourceRoot: developmentSourceRoot
        )
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem.length = NSStatusItem.squareLength
        statusItem.button?.title = ""
        statusItem.button?.imagePosition = .imageOnly
        statusItem.button?.toolTip = L("AI2Apps 服务 — \(arguments.instanceID.rawValue)", "AI2Apps service — \(arguments.instanceID.rawValue)")
        updateStatusIcon(for: .initializing)
        rebuildMenu()
        do {
            try paths.preparePrivateDirectories()
            publishStatus(.initializing, message: L("正在初始化 Helper…", "Initializing Helper…"))
            publishUpdateStatus(.idle, message: L("尚未检查更新", "Updates not checked"))
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
                message: L("Helper 控制通道启动失败", "Could not start Helper control channel"),
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
        beginPeriodicUpdateChecks()
    }

    func applicationWillTerminate(_ notification: Notification) {
        updateDownloadTask?.cancel()
        updateDownloadTask = nil
        periodicUpdateTask?.cancel()
        periodicUpdateTask = nil
        updateTipDismissalTask?.cancel()
        updateTipDismissalTask = nil
        updateTipPopover?.close()
        updateTipPopover = nil
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
        if preserveLocalForUpdateHandoff {
            healthMonitor?.cancel()
            healthMonitor = nil
            return .terminateNow
        }
        guard updateProcess == nil else {
            NSSound.beep()
            return .terminateCancel
        }
        guard !resetInProgress else {
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
        statusMenuItem.title = L("状态：正在停止服务", "Status: Stopping service")
        publishStatus(.stopping, message: L("正在停止 AI2Apps 服务…", "Stopping AI2Apps service…"))
        terminationTask = Task { [weak self, weak sender] in
            guard let self else { return }
            if let process = testEnvironmentProcess, process.isRunning {
                process.interrupt()
                while process.isRunning {
                    try? await Task.sleep(for: .milliseconds(200))
                }
            }
            await supervisor.stop()
            actualPort = nil
            serviceStoppedForTermination = true
            terminationTask = nil
            publishStatus(.helperExiting, message: L("AI2Apps 服务已停止，Helper 正在退出", "AI2Apps service stopped; Helper is exiting"))
            sender?.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }

    func menuWillOpen(_ menu: NSMenu) {
        for item in menu.items {
            item.title = HelperLocalization.refresh(item.title)
        }
    }

    private func rebuildMenu() {
        let menu = NSMenu()
        // AppKit otherwise re-enables any item whose target implements its
        // action, overriding the explicit update/readiness gates below.
        menu.autoenablesItems = false
        menu.delegate = self
        let instance = NSMenuItem(
            title: L("实例：\(arguments.instanceID.rawValue)", "Instance: \(arguments.instanceID.rawValue)"),
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
            withTitle: L("打开 AI2Apps", "Open AI2Apps"),
            action: #selector(openAI2Apps),
            keyEquivalent: ""
        )
        openApp.target = self
        openApp.isEnabled = mainBundleIdentifier != nil || arguments.appBundleURL != nil
        menu.addItem(withTitle: L("启动 AI2Apps 服务", "Start AI2Apps service"), action: #selector(startLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: L("停止 AI2Apps 服务", "Stop AI2Apps service"), action: #selector(stopLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: L("重启 AI2Apps 服务", "Restart AI2Apps service"), action: #selector(restartLocalAction), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: L("配置端口…", "Configure port…"), action: #selector(configurePort), keyEquivalent: "")
            .target = self
        loginItemToggleMenuItem.action = #selector(toggleLoginItem)
        loginItemToggleMenuItem.target = self
        loginItemToggleMenuItem.isEnabled = canConfigureLoginItem
        menu.addItem(loginItemToggleMenuItem)
        menu.addItem(.separator())
        menu.addItem(updateStatusMenuItem)
        checkUpdateMenuItem.action = #selector(checkForUpdates)
        checkUpdateMenuItem.target = self
        menu.addItem(checkUpdateMenuItem)
        installUpdateMenuItem.action = #selector(installStagedUpdate)
        installUpdateMenuItem.target = self
        menu.addItem(installUpdateMenuItem)
        menu.addItem(withTitle: L("复制服务地址", "Copy service address"), action: #selector(copyLocalAddress), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: L("打开日志文件夹", "Open logs folder"), action: #selector(openLogs), keyEquivalent: "")
            .target = self
        menu.addItem(withTitle: L("导出安全诊断摘要…", "Export safe diagnostics…"), action: #selector(exportDiagnostics), keyEquivalent: "")
            .target = self
        if allowsInstanceDataReset {
            menu.addItem(.separator())
            menu.addItem(
                withTitle: L("重置数据…", "Reset data…"),
                action: #selector(resetInstanceData),
                keyEquivalent: ""
            ).target = self
        }
        menu.addItem(.separator())
        if allowsTestEnvironment {
            testEnvironmentMenuItem.action = #selector(toggleTestEnvironment)
            testEnvironmentMenuItem.target = self
            menu.addItem(testEnvironmentMenuItem)
        }
        menu.addItem(withTitle: L("退出 AI2Apps 服务", "Quit AI2Apps service"), action: #selector(quitAll), keyEquivalent: "q")
            .target = self
        statusItem.menu = menu
        updatePortLabel()
        updateLoginItemLabel()
        refreshUpdateMenu()
    }

    private var allowsTestEnvironment: Bool {
        developmentBuild && arguments.instanceID.rawValue == "app-dev"
            && mainBundleIdentifier == "com.ai2apps.desktop.appdev"
            && developmentSourceRoot != nil
    }

    @objc private func toggleTestEnvironment() {
        guard allowsTestEnvironment else { return }
        if let process = testEnvironmentProcess, process.isRunning {
            testEnvironmentMenuItem.title = L("正在停止测试…", "Stopping tests…")
            testEnvironmentMenuItem.isEnabled = false
            process.interrupt()
            return
        }
        guard let root = developmentSourceRoot else { return }
        let directory = root.appendingPathComponent("ai2apps-test-system")
        let executable = directory.appendingPathComponent("bin/ai2apps-test")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            presentError(ContractError.invalidField(field: "test_environment", reason: L("测试工具不存在：\(executable.path)", "Test tool not found: \(executable.path)")))
            return
        }
        let process = Process()
        let output = Pipe()
        process.executableURL = executable
        process.arguments = ["select", "--no-open"]
        process.currentDirectoryURL = directory
        var environment = ProcessInfo.processInfo.environment
        // Never pass App-Dev's privileged Local identity into the Test Harness.
        for key in environment.keys where key.hasPrefix("AI2APPS_") {
            environment.removeValue(forKey: key)
        }
        process.environment = environment
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        process.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                self?.testEnvironmentProcess = nil
                self?.testEnvironmentMenuItem.title = L("启动测试环境", "Start test environment")
                self?.testEnvironmentMenuItem.isEnabled = true
            }
        }
        do {
            try process.run()
            testEnvironmentProcess = process
            testEnvironmentMenuItem.title = L("停止测试", "Stop tests")
            openAI2Apps()
            Task { [weak self] in
                do {
                    for try await line in output.fileHandleForReading.bytes.lines {
                        guard let data = line.data(using: .utf8),
                              let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                              let address = payload["selectorUrl"] as? String else { continue }
                        try await self?.openTestEnvironmentPage(address)
                        break
                    }
                } catch {
                    self?.presentError(error)
                }
            }
        } catch { presentError(error) }
    }

    private func openTestEnvironmentPage(_ address: String) async throws {
        guard allowsTestEnvironment, let target = URL(string: address),
              target.scheme == "http", target.host == "127.0.0.1", target.port != nil,
              target.path == "/", target.fragment != nil else {
            throw ContractError.invalidField(field: "test_environment", reason: L("无效测试地址", "Invalid test URL"))
        }
        for _ in 0..<30 {
            if let port = actualPort {
                var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/v1/platform/client/app-dev-test-environment")!)
                request.httpMethod = "POST"
                request.timeoutInterval = 30
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue("Bearer \(controlCredentials.environment["AI2APPS_HELPER_TOKEN"] ?? "")", forHTTPHeaderField: "Authorization")
                request.httpBody = try JSONSerialization.data(withJSONObject: ["initial_url": address])
                let (_, response) = try await URLSession.shared.data(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                    throw ContractError.invalidField(field: "test_environment", reason: L("App-Dev 打开测试页面失败（HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0)），请停止测试后重试。", "App-Dev could not open the test page (HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0)). Stop tests and try again."))
                }
                return
            }
            try await Task.sleep(for: .seconds(1))
        }
        throw ContractError.invalidField(field: "test_environment", reason: L("App-Dev 服务未就绪", "App-Dev service is not ready"))
    }

    private var updateDirectory: URL {
        paths.downloadsDirectory.appendingPathComponent("update", isDirectory: true)
    }

    private var updateManifestURL: URL? {
        guard let app = arguments.appBundleURL,
              let value = Bundle(url: app)?.object(
                  forInfoDictionaryKey: "AI2AppsUpdateManifestURL"
              ) as? String,
              let url = URL(string: value), url.scheme?.lowercased() == "https",
              url.host != nil else { return nil }
        return url
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
        let required = [
            app.appendingPathComponent("Contents/Helpers/AI2AppsUpdater"),
            app.appendingPathComponent("Contents/Resources/Update/stage-update-candidate.py"),
            arguments.runtimePythonExecutable,
        ]
        return required.allSatisfy { FileManager.default.isExecutableFile(atPath: $0.path) }
    }

    private func refreshUpdateMenu() {
        checkUpdateMenuItem.isEnabled = canManageUpdates && updateProcess == nil
            && updateDownloadTask == nil && updateManifestURL != nil
        installUpdateMenuItem.isEnabled = canManageUpdates && updateProcess == nil
            && updateDownloadTask == nil
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
        currentUpdatePhase = phase
        currentUpdateMessage = message
        switch phase {
        case .idle: updateStatusMenuItem.title = L("更新：\(message)", "Update: \(message)")
        case .checking: updateStatusMenuItem.title = L("更新：\(message)", "Update: \(message)")
        case .ready: updateStatusMenuItem.title = L("更新：Build \(candidateBuild ?? "?") 可安装", "Update: Build \(candidateBuild ?? "?") ready to install")
        case .installing: updateStatusMenuItem.title = L("更新：正在安装", "Update: Installing")
        case .succeeded: updateStatusMenuItem.title = L("更新：安装成功", "Update: Installed")
        case .failed: updateStatusMenuItem.title = L("更新：失败", "Update: Failed")
        }
        refreshUpdateMenu()
        updateStatusIcon(for: currentHelperPhase)
    }

    private func updatePortLabel() {
        let configured = configuration.portMode == .automatic
            ? L("自动", "Automatic")
            : String(configuration.configuredPort ?? 0)
        if let actualPort {
            portMenuItem.title = L("端口：\(configured)（当前 \(actualPort)）", "Port: \(configured) (current \(actualPort))")
        } else {
            portMenuItem.title = L("端口：\(configured)", "Port: \(configured)")
        }
    }

    private func updateLoginItemLabel() {
        loginItemToggleMenuItem.state = configuration.startAtLogin ? .on : .off
        let statusURL = paths.runDirectory.appendingPathComponent("login-item.json")
        guard let status = try? ContractCodec.load(LoginItemStatus.self, from: statusURL),
              status.instanceID == arguments.instanceID else {
            loginItemMenuItem.title = L("登录启动：尚未配置", "Launch at login: Not configured")
            return
        }
        switch status.phase {
        case .enabled:
            loginItemMenuItem.title = L("登录启动：已启用", "Launch at login: Enabled")
        case .requiresApproval:
            loginItemMenuItem.title = L("登录启动：等待系统批准", "Launch at login: Awaiting system approval")
        case .notRegistered, .notFound:
            loginItemMenuItem.title = L("登录启动：未注册", "Launch at login: Not registered")
        case .skippedReadOnly:
            loginItemMenuItem.title = L("登录启动：安装后启用", "Launch at login: Enable after installation")
        case .skippedDevelopment:
            loginItemMenuItem.title = L("登录启动：开发模式跳过", "Launch at login: Skipped in development")
        case .failed:
            loginItemMenuItem.title = L("登录启动：注册失败", "Launch at login: Registration failed")
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
        if let application = runningAI2AppsShellApplicationForActivation() {
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
        statusMenuItem.title = L("状态：正在启动", "Status: Starting")
        publishStatus(.starting, message: L("正在启动 AI2Apps 服务…", "Starting AI2Apps service…"))
        Task {
            do {
                let ready = try await supervisor.start()
                actualPort = ready.descriptor.actualPort
                statusMenuItem.title = L("状态：运行中", "Status: Running")
                publishStatus(
                    .ready,
                    message: L("AI2Apps 服务已就绪", "AI2Apps service is ready"),
                    actualPort: ready.descriptor.actualPort
                )
                updatePortLabel()
                beginHealthMonitoring()
            } catch LocalSupervisorError.alreadyRunning {
                statusMenuItem.title = L("状态：已在运行", "Status: Already running")
                publishStatus(.ready, message: L("AI2Apps 服务已在运行", "AI2Apps service is already running"))
            } catch LocalSupervisorError.portInUse(let conflict) {
                actualPort = nil
                statusMenuItem.title = L("状态：端口 \(conflict.port) 被占用", "Status: Port \(conflict.port) is in use")
                publishStatus(
                    .failed,
                    message: L("固定端口 \(conflict.port) 已被占用", "Fixed port \(conflict.port) is in use"),
                    errorCode: "port_conflict"
                )
                updatePortLabel()
                presentError(LocalSupervisorError.portInUse(conflict))
            } catch {
                statusMenuItem.title = L("状态：启动失败", "Status: Startup failed")
                publishStatus(
                    .failed,
                    message: L("AI2Apps 服务启动失败", "AI2Apps service failed to start"),
                    errorCode: "local_start_failed"
                )
                presentError(error)
            }
        }
    }

    private func adoptOrStartLocal() {
        statusMenuItem.title = L("状态：正在检查服务", "Status: Checking service")
        publishStatus(.checking, message: L("正在检查已有 AI2Apps 服务…", "Checking existing AI2Apps service…"))
        Task {
            do {
                if let ready = try await supervisor.adoptRunningLocal() {
                    actualPort = ready.descriptor.actualPort
                    statusMenuItem.title = L("状态：运行中（已接管）", "Status: Running (adopted)")
                    publishStatus(
                        .ready,
                        message: L("已接管运行中的 AI2Apps 服务", "Adopted running AI2Apps service"),
                        actualPort: ready.descriptor.actualPort
                    )
                    updatePortLabel()
                    beginHealthMonitoring()
                } else {
                    startLocal()
                }
            } catch {
                statusMenuItem.title = L("状态：现有服务验证失败", "Status: Existing service verification failed")
                publishStatus(
                    .failed,
                    message: L("已有 AI2Apps 服务验证失败", "Existing AI2Apps service verification failed"),
                    errorCode: "local_adoption_failed"
                )
                presentError(error)
            }
        }
    }

    private func stopLocal(restart: Bool = false) {
        healthMonitor?.cancel()
        healthMonitor = nil
        statusMenuItem.title = L("状态：正在停止", "Status: Stopping")
        publishStatus(.stopping, message: L("正在停止 AI2Apps 服务…", "Stopping AI2Apps service…"))
        Task {
            await supervisor.stop()
            actualPort = nil
            statusMenuItem.title = L("状态：已停止", "Status: Stopped")
            publishStatus(.stopped, message: L("AI2Apps 服务已停止", "AI2Apps service stopped"))
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
                    statusMenuItem.title = L("状态：运行中", "Status: Running")
                    publishStatus(.ready, message: L("AI2Apps 服务运行正常", "AI2Apps service is healthy"))
                    continue
                }
                consecutiveFailures += 1
                statusMenuItem.title = L("状态：连接异常（\(consecutiveFailures)/3）", "Status: Connection failure (\(consecutiveFailures)/3)")
                publishStatus(
                    .degraded,
                    message: L("AI2Apps 服务连接异常（\(consecutiveFailures)/3）", "AI2Apps service connection failure (\(consecutiveFailures)/3)"),
                    errorCode: "local_health_failed"
                )
                if consecutiveFailures >= 3, configuration.autoRestart {
                    statusMenuItem.title = L("状态：自动重启中", "Status: Restarting automatically")
                    publishStatus(.restarting, message: L("正在自动重启 AI2Apps 服务…", "Automatically restarting AI2Apps service…"))
                    stopLocal(restart: true)
                    return
                }
            }
        }
    }

    private func replaceSupervisor() {
        supervisor = makeLocalSupervisor(
            arguments: arguments,
            configuration: configuration,
            paths: paths,
            controlCredentials: controlCredentials,
            developmentBuild: developmentBuild,
            developmentSourceRoot: developmentSourceRoot
        )
    }

    private func publishStatus(
        _ phase: HelperPhase,
        message: String,
        actualPort: Int? = nil,
        errorCode: String? = nil
    ) {
        currentHelperMessage = message
        updateStatusIcon(for: phase)
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
        currentHelperPhase = phase
        let hasInstallableUpdate = stagedCandidateBuild != nil
            && FileManager.default.fileExists(atPath: stagedUpdateApp.path)
        let isDownloading = currentUpdatePhase == .checking
            && (currentUpdateMessage.hasPrefix("正在下载")
                || currentUpdateMessage.hasPrefix("Downloading "))
        let isBusy = (currentUpdatePhase == .checking && !isDownloading)
            || currentUpdatePhase == .installing
        let activityTitle = updateActivityTitle(
            isDownloading: isDownloading
        )
        let source: NSImage?
        if hasInstallableUpdate {
            source = menuBarReadyLogo ?? menuBarUpdateLogo ?? menuBarLogo
        } else if isDownloading {
            source = menuBarUpdateLogo ?? menuBarLogo
        } else if isBusy {
            source = menuBarWorkLogo ?? menuBarLogo
        } else {
            source = menuBarLogo
        }
        guard let source else {
            // A packaged build is verified to contain the SVG. Keep the menu
            // reachable in an unpackaged developer run if that resource is
            // deliberately absent.
            statusItem.length = NSStatusItem.variableLength
            statusItem.button?.image = nil
            statusItem.button?.title = activityTitle.map { "AI2 \($0)" } ?? "AI2"
            return
        }
        let color: NSColor
        if hasInstallableUpdate || isDownloading || isBusy {
            color = .black
        } else {
            switch phase {
            case .ready:
                color = .black
            case .initializing, .checking, .starting, .restarting, .stopping,
                 .degraded, .failed:
                color = NSColor(calibratedWhite: 0.48, alpha: 1)
            case .stopped, .helperExiting:
                color = NSColor(calibratedWhite: 0.78, alpha: 1)
            }
        }
        // The logo has generous intrinsic margins. Render it slightly larger
        // than the conventional 18-point menu-bar glyph so its visible mark
        // matches neighbouring status icons.
        let size = NSSize(width: 22, height: 22)
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
        statusItem.length = activityTitle == nil
            ? NSStatusItem.squareLength
            : NSStatusItem.variableLength
        statusItem.button?.title = activityTitle.map { " \($0)" } ?? ""
        statusItem.button?.imagePosition = activityTitle == nil ? .imageOnly : .imageLeft
        statusItem.button?.image = image
        if hasInstallableUpdate {
            statusItem.button?.toolTip = L("AI2Apps — Build \(stagedCandidateBuild ?? "?") 可安装", "AI2Apps — Build \(stagedCandidateBuild ?? "?") ready to install")
        } else if currentUpdatePhase == .checking || currentUpdatePhase == .installing {
            statusItem.button?.toolTip = "AI2Apps — \(currentUpdateMessage)"
        } else {
            statusItem.button?.toolTip = L("AI2Apps 服务 — \(arguments.instanceID.rawValue) — \(currentHelperMessage)", "AI2Apps service — \(arguments.instanceID.rawValue) — \(currentHelperMessage)")
        }
    }

    private func updateActivityTitle(
        isDownloading: Bool
    ) -> String? {
        if isDownloading {
            if let separator = currentUpdateMessage.lastIndex(where: { $0 == "：" || $0 == ":" }) {
                let progress = currentUpdateMessage[currentUpdateMessage.index(after: separator)...]
                if progress.hasSuffix("%") {
                    return String(progress).trimmingCharacters(in: .whitespaces)
                }
            }
            return "0%"
        }
        return nil
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
            if request.operation == "instance.reset" {
                guard allowsInstanceDataReset,
                      arguments.instanceID.rawValue == "test",
                      mainBundleIdentifier == "com.ai2apps.desktop.test",
                      request.actorUserID == "ai2apps-test-harness",
                      request.confirmInstanceID == "test",
                      canBeginInstanceDataReset else {
                    return .failure(
                        requestID: request.requestID,
                        error: "Test instance reset request rejected"
                    )
                }
                Task { @MainActor [weak self] in
                    try? await Task.sleep(for: .milliseconds(250))
                    self?.beginInstanceDataReset()
                }
                return .success(
                    requestID: request.requestID,
                    result: HelperControlResult(status: "resetting")
                )
            }
            let profileKey = request.browserProfileKey ?? "default"
            let profileID = try BrowserAgentProfileID.derive(
                instanceID: arguments.instanceID,
                actorUserID: request.actorUserID,
                profileKey: profileKey
            ).rawValue
            if request.operation == "browser.delete" {
                guard profileKey != "default" else {
                    return .failure(
                        requestID: request.requestID,
                        error: "The default browser Profile cannot be deleted"
                    )
                }
                return try await deleteBrowserProfile(
                    requestID: request.requestID,
                    profileID: profileID
                )
            }
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
                profileKey: profileKey,
                paths: paths,
                initialURL: initialURL,
                automation: automation,
                inheritedEnvironment: ProcessInfo.processInfo.environment
            )
            if let existing = browserAgents[profileID], !existing.application.isTerminated {
                existing.application.activate(
                    options: [.activateAllWindows, .activateIgnoringOtherApps]
                )
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
            let launchDeadline = Date().addingTimeInterval(5)
            while !application.isFinishedLaunching, Date() < launchDeadline {
                try await Task.sleep(for: .milliseconds(100))
            }
            application.activate(
                options: [.activateAllWindows, .activateIgnoringOtherApps]
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

    private func deleteBrowserProfile(
        requestID: String,
        profileID: String
    ) async throws -> HelperControlResponse {
        if let existing = browserAgents.removeValue(forKey: profileID),
           !existing.application.isTerminated {
            existing.application.terminate()
            let deadline = Date().addingTimeInterval(5)
            while !existing.application.isTerminated, Date() < deadline {
                try await Task.sleep(for: .milliseconds(100))
            }
            guard existing.application.isTerminated else {
                throw ContractError.invalidField(
                    field: "browser_profile",
                    reason: "AceFox did not exit before Profile deletion"
                )
            }
        }
        let profileDirectory = paths.browserProfilesDirectory
            .appendingPathComponent("agents", isDirectory: true)
            .appendingPathComponent(profileID, isDirectory: true)
        if FileManager.default.fileExists(atPath: profileDirectory.path) {
            try FileManager.default.removeItem(at: profileDirectory)
        }
        auditBrowserEvent(
            action: "browser.delete",
            profileID: profileID,
            processID: 0,
            outcome: "deleted"
        )
        return .success(
            requestID: requestID,
            result: HelperControlResult(status: "deleted", profileID: profileID)
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
        alert.messageText = L("配置 AI2Apps 服务端口", "Configure AI2Apps service port")
        alert.informativeText = L("留空表示自动分配；固定端口范围为 1024–65535。", "Leave blank for automatic allocation; fixed ports must be 1024–65535.")
        alert.addButton(withTitle: L("保存并重启", "Save and restart"))
        alert.addButton(withTitle: L("取消", "Cancel"))
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 260, height: 24))
        field.placeholderString = L("自动", "Automatic")
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

    private func beginPeriodicUpdateChecks() {
        guard updateManifestURL != nil else { return }
        periodicUpdateTask = Task { [weak self] in
            do {
                try await Task.sleep(for: .seconds(30))
                while !Task.isCancelled {
                    self?.startUpdateCheckIfPossible(audibleFailure: false)
                    try await Task.sleep(for: .seconds(24 * 60 * 60))
                }
            } catch {
                // Cancellation is expected during Helper shutdown.
            }
        }
    }

    @objc private func checkForUpdates() {
        startUpdateCheckIfPossible(audibleFailure: true)
    }

    private func startUpdateCheckIfPossible(audibleFailure: Bool) {
        guard canManageUpdates, updateProcess == nil, updateDownloadTask == nil,
              stagedCandidateBuild == nil, updateManifestURL != nil else {
            if audibleFailure {
                NSSound.beep()
            }
            return
        }
        publishUpdateStatus(.checking, message: L("正在联网检查更新", "Checking for updates online"))
        updateDownloadTask = Task { [weak self] in
            guard let self else { return }
            await self.performOnlineUpdateCheck(showCurrentVersionTip: audibleFailure)
            self.updateDownloadTask = nil
            self.refreshUpdateMenu()
        }
        refreshUpdateMenu()
    }

    private func performOnlineUpdateCheck(showCurrentVersionTip: Bool) async {
        guard let manifestURL = updateManifestURL,
              let appBundleURL = arguments.appBundleURL,
              let appBundle = Bundle(url: appBundleURL),
              let bundleIdentifier = appBundle.bundleIdentifier,
              let buildText = appBundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String,
              let currentBuild = Int(buildText), currentBuild > 0,
              let runtimeProfile = appBundle.object(
                  forInfoDictionaryKey: "AI2AppsRuntimeProfile"
              ) as? String else {
            publishUpdateStatus(.failed, message: L("更新配置不完整", "Update configuration is incomplete"), errorCode: "update_config_invalid")
            return
        }
        do {
            publishUpdateStatus(.checking, message: L("正在联网检查更新", "Checking for updates online"))
            let manifest = try await fetchUpdateManifest(from: manifestURL)
            let cohortID = try UpdateManifest.loadOrCreateCohortID(
                at: paths.configDirectory.appendingPathComponent("update-cohort-id")
            )
            let version = ProcessInfo.processInfo.operatingSystemVersion
            let systemVersion = "\(version.majorVersion).\(version.minorVersion).\(version.patchVersion)"
            #if arch(arm64)
            let architecture = "arm64"
            #elseif arch(x86_64)
            let architecture = "x86_64"
            #else
            let architecture = "unsupported"
            #endif
            guard let release = try manifest.selectedRelease(
                bundleIdentifier: bundleIdentifier,
                instanceID: arguments.instanceID.rawValue,
                currentBuild: currentBuild,
                runtimeProfile: runtimeProfile,
                architecture: architecture,
                systemVersion: systemVersion,
                cohortID: cohortID
            ) else {
                publishUpdateStatus(.idle, message: L("已是最新版本", "Already up to date"))
                if showCurrentVersionTip {
                    presentCurrentVersionTip()
                }
                return
            }

            try prepareUpdateDirectories()
            let incoming = updateDirectory.appendingPathComponent(
                "incoming-\(release.bundleVersion)",
                isDirectory: true
            )
            try prepareRealPrivateDirectory(incoming)
            let metadata = incoming.appendingPathComponent(release.metadata.filename)
            let dmg = incoming.appendingPathComponent(release.dmg.filename)
            let downloader = ResumableDownloader()
            _ = try await downloader.download(
                release.metadata,
                to: metadata,
                progress: updateProgressHandler(build: release.bundleVersion, label: L("清单", "Manifest"))
            )
            _ = try await downloader.download(
                release.dmg,
                to: dmg,
                progress: updateProgressHandler(build: release.bundleVersion, label: L("安装包", "Package"))
            )
            try Task.checkCancellation()
            stageDownloadedUpdate(dmg: dmg, metadata: metadata)
        } catch is CancellationError {
            publishUpdateStatus(.idle, message: L("更新下载已暂停", "Update download paused"))
        } catch {
            publishUpdateStatus(
                .failed,
                message: L("联网检查或下载更新失败", "Update check or download failed"),
                errorCode: "online_update_failed"
            )
            try? appendUpdateLog("online update failed: \(error)\n")
        }
    }

    private func presentCurrentVersionTip() {
        guard let button = statusItem.button else { return }
        updateTipDismissalTask?.cancel()
        updateTipPopover?.close()

        let label = NSTextField(labelWithString: L("当前已是最新版本", "You are up to date"))
        label.font = .systemFont(ofSize: 13, weight: .medium)
        label.textColor = .labelColor
        label.alignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false

        let controller = NSViewController()
        let contentView = NSView(frame: NSRect(x: 0, y: 0, width: 176, height: 42))
        contentView.addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 14),
            label.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -14),
            label.centerYAnchor.constraint(equalTo: contentView.centerYAnchor),
        ])
        controller.view = contentView

        let popover = NSPopover()
        popover.behavior = .transient
        popover.animates = true
        popover.contentSize = contentView.frame.size
        popover.contentViewController = controller
        updateTipPopover = popover
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)

        updateTipDismissalTask = Task { [weak self, weak popover] in
            do {
                try await Task.sleep(for: .seconds(3))
            } catch {
                return
            }
            popover?.close()
            self?.updateTipPopover = nil
            self?.updateTipDismissalTask = nil
        }
    }

    private func fetchUpdateManifest(from url: URL) async throws -> UpdateManifest {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        request.timeoutInterval = 30
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200,
              http.url?.scheme?.lowercased() == "https" else {
            throw UpdateManifestError.invalidField("http_status")
        }
        var data = Data()
        data.reserveCapacity(64 * 1024)
        for try await byte in bytes {
            guard data.count < 1024 * 1024 else {
                throw UpdateManifestError.invalidField("manifest_size")
            }
            data.append(byte)
        }
        let manifest = try JSONDecoder().decode(UpdateManifest.self, from: data)
        try manifest.validate()
        return manifest
    }

    private func updateProgressHandler(
        build: String,
        label: String
    ) -> ResumableDownloader.Progress {
        { [weak self] received, total in
            let percent = total > 0 ? min(100, Int(received * 100 / total)) : 0
            Task { @MainActor in
                self?.publishUpdateStatus(
                    .checking,
                    message: L("正在下载 Build \(build) \(label)：\(percent)%", "Downloading Build \(build) \(label): \(percent)%")
                )
            }
        }
    }

    private func appendUpdateLog(_ message: String) throws {
        let handle = try updateLogHandle()
        defer { try? handle.close() }
        try handle.write(contentsOf: Data(message.utf8))
    }

    @objc private func checkDownloadedUpdate() {
        let dmg = updateDirectory.appendingPathComponent("AI2Apps.dmg")
        let metadata = updateDirectory.appendingPathComponent("AI2Apps.release.json")
        stageDownloadedUpdate(dmg: dmg, metadata: metadata)
    }

    private func stageDownloadedUpdate(dmg: URL, metadata: URL) {
        guard canManageUpdates, updateProcess == nil,
              let appBundle = arguments.appBundleURL else {
            NSSound.beep()
            return
        }
        guard FileManager.default.fileExists(atPath: dmg.path),
              FileManager.default.fileExists(atPath: metadata.path) else {
            publishUpdateStatus(
                .failed,
                message: L("未找到已下载的更新文件", "Downloaded update files were not found"),
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
            let python = arguments.runtimePythonExecutable
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
                            message: L("更新已验证，可以安装", "Update verified and ready to install"),
                            candidateBuild: build
                        )
                    } else {
                        self.stagedCandidateBuild = nil
                        self.publishUpdateStatus(
                            .failed,
                            message: L("更新验证失败，请查看日志", "Update verification failed; check logs"),
                            errorCode: "candidate_verification_failed"
                        )
                    }
                }
            }
            updateProcess = process
            publishUpdateStatus(.checking, message: L("正在验证已下载更新", "Verifying downloaded update"))
            try process.run()
        } catch {
            updateProcess = nil
            stagedCandidateBuild = nil
            publishUpdateStatus(
                .failed,
                message: L("无法启动更新验证", "Could not start update verification"),
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
        alert.messageText = L("安装 AI2Apps 更新？", "Install AI2Apps update?")
        alert.informativeText = L("AI2Apps 窗口将退出并在验证成功后重新打开。Helper 和 AI2Apps 服务会继续运行；失败时自动恢复当前版本。", "AI2Apps windows will close and reopen after verification. Helper and the AI2Apps service will keep running. The current version will be restored if installation fails.")
        alert.addButton(withTitle: L("安装并退出", "Install and quit"))
        alert.addButton(withTitle: L("取消", "Cancel"))
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
                message: L("无法验证当前 AI2Apps 窗口进程", "Could not verify the current AI2Apps window process"),
                candidateBuild: candidateBuild,
                errorCode: "shell_identity_invalid"
            )
            return
        }
        let backup = appBundle.deletingLastPathComponent().appendingPathComponent(
            "\(appBundle.deletingPathExtension().lastPathComponent).previous.app"
        )
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
                            message: L("更新已安装，正在重新打开 AI2Apps", "Update installed; reopening AI2Apps"),
                            candidateBuild: candidateBuild
                        )
                        do {
                            try self.launchUpdatedApplicationForHandoff(appBundle: appBundle)
                            self.preserveLocalForUpdateHandoff = true
                            NSApp.terminate(nil)
                        } catch {
                            self.publishUpdateStatus(
                                .failed,
                                message: L("更新已安装，但自动重启失败", "Update installed, but automatic restart failed"),
                                candidateBuild: candidateBuild,
                                errorCode: "handoff_failed"
                            )
                            self.presentError(error)
                        }
                    } else {
                        self.publishUpdateStatus(
                            .failed,
                            message: L("更新失败，当前版本已保留或恢复", "Update failed; the current version was kept or restored"),
                            candidateBuild: candidateBuild,
                            errorCode: "installation_failed"
                        )
                    }
                }
            }
            updateProcess = process
            publishUpdateStatus(
                .installing,
                message: L("正在等待 AI2Apps 窗口退出并安装更新", "Waiting for AI2Apps windows to close and install the update"),
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
                message: L("无法启动更新安装", "Could not start update installation"),
                candidateBuild: candidateBuild,
                errorCode: "installation_start_failed"
            )
            presentError(error)
        }
    }

    private func launchUpdatedApplicationForHandoff(appBundle: URL) throws {
        let launcher = appBundle.appendingPathComponent("Contents/MacOS/AI2Apps")
        guard FileManager.default.isExecutableFile(atPath: launcher.path) else {
            throw ContractError.invalidField(
                field: "post_update_handoff",
                reason: "updated Launcher is not executable"
            )
        }
        let process = Process()
        process.executableURL = launcher
        process.arguments = [
            "--post-update-handoff",
            "--wait-helper-pid", String(ProcessInfo.processInfo.processIdentifier),
        ]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = try updateLogHandle()
        try process.run()
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
            alert.messageText = L("AI2Apps 正在运行", "AI2Apps is running")
            alert.informativeText = L("退出 AI2Apps 服务后，当前 AI2Apps 窗口将无法继续使用本地功能。是否同时退出 AI2Apps？", "AI2Apps windows will lose local functionality when the service quits. Quit AI2Apps as well?")
            alert.addButton(withTitle: L("退出 AI2Apps 和服务", "Quit AI2Apps and service"))
            alert.addButton(withTitle: L("仅退出服务", "Quit service only"))
            alert.addButton(withTitle: L("取消", "Cancel"))
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

    @objc private func resetInstanceData() {
        guard canBeginInstanceDataReset else {
            NSSound.beep()
            return
        }

        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = L("重置 \(appDisplayName) 数据？", "Reset \(appDisplayName) data?")
        alert.informativeText = L("这会退出 \(appDisplayName)，永久删除 \(arguments.instanceID.rawValue) 实例的账号、设置、应用、下载、浏览器资料和私有模型准备数据。本机共享的已验证 Checkpoint 与公共 Hugging Face cache 不会被删除。", "This will quit \(appDisplayName) and permanently delete accounts, settings, apps, downloads, browser profiles and private model preparation data for instance \(arguments.instanceID.rawValue). Shared verified checkpoints and the public Hugging Face cache will be kept.")
        alert.addButton(withTitle: L("重置数据并退出", "Reset data and quit"))
        alert.addButton(withTitle: L("取消", "Cancel"))
        NSApp.activate(ignoringOtherApps: true)
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        beginInstanceDataReset()
    }

    private var canBeginInstanceDataReset: Bool {
        allowsInstanceDataReset && !resetInProgress
            && updateProcess == nil && updateDownloadTask == nil
    }

    private func beginInstanceDataReset() {
        guard canBeginInstanceDataReset else { return }

        resetInProgress = true
        healthMonitor?.cancel()
        healthMonitor = nil
        periodicUpdateTask?.cancel()
        periodicUpdateTask = nil
        browserAgentLeaseMonitor?.cancel()
        browserAgentLeaseMonitor = nil
        statusMenuItem.title = L("状态：正在重置数据", "Status: Resetting data")
        publishStatus(
            .stopping,
            message: L("正在停止服务并重置 \(arguments.instanceID.rawValue) 实例数据…", "Stopping the service and resetting instance \(arguments.instanceID.rawValue)…")
        )

        let shellApplication = runningAI2AppsShellApplication()
        Task { [weak self] in
            guard let self else { return }
            await supervisor.stop()
            // Reset has already received explicit confirmation and will delete
            // the browser profile. Force termination avoids AceFox displaying
            // a second, unrelated quit confirmation over the reset operation.
            shellApplication?.forceTerminate()
            for (_, agent) in browserAgents where !agent.application.isTerminated {
                agent.application.forceTerminate()
            }
            browserAgents.removeAll()
            controlServer?.stop()
            controlServer = nil
            actualPort = nil

            do {
                try InstanceDataReset(paths: paths).perform()
            } catch {
                presentError(
                    ContractError.invalidField(
                        field: "instance_data_reset",
                        reason: L("重置未能完整完成：\(error)；请重新打开 \(appDisplayName) 后再试", "Reset did not complete: \(error). Reopen \(appDisplayName) and try again.")
                    )
                )
            }
            serviceStoppedForTermination = true
            resetInProgress = false
            NSApp.terminate(nil)
        }
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

    private func runningAI2AppsShellApplicationForActivation() -> NSRunningApplication? {
        if let application = runningAI2AppsShellApplication() {
            return application
        }
        guard let appBundle = arguments.appBundleURL,
              let expectedExecutable = arguments.aceFoxExecutable,
              let expectedMainBundleIdentifier = Bundle(url: appBundle)?.bundleIdentifier else {
            return nil
        }
        let expectedShellBundleURL = expectedExecutable
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        guard let expectedShellBundleIdentifier = Bundle(
            url: expectedShellBundleURL
        )?.bundleIdentifier else {
            return nil
        }
        let descriptorURL = paths.runDirectory.appendingPathComponent("shell.json")
        guard let shell = try? ContractCodec.load(
            ShellRunDescriptor.self,
            from: descriptorURL
        ),
            let application = NSRunningApplication(
                processIdentifier: shell.processID
            ),
            !application.isTerminated,
            let liveExecutablePath = processExecutablePath(
                pid: pid_t(shell.processID)
            ),
            let liveShellBundleURL = Self.containingAppBundle(
                forExecutablePath: liveExecutablePath
            ),
            let liveShellBundle = Bundle(url: liveShellBundleURL),
            let rawLiveInstanceID = liveShellBundle.object(
                forInfoDictionaryKey: "AI2AppsInstanceID"
            ) as? String,
            let liveInstanceID = try? InstanceID(rawValue: rawLiveInstanceID) else {
            return nil
        }
        let liveMainBundleURL = liveShellBundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        guard ShellProcessIdentityValidator().validateForActivation(
            shell,
            expectedInstanceID: arguments.instanceID,
            expectedShellBundleIdentifier: expectedShellBundleIdentifier,
            expectedMainBundleIdentifier: expectedMainBundleIdentifier,
            liveShellBundleIdentifier: application.bundleIdentifier,
            liveMainBundleIdentifier: Bundle(url: liveMainBundleURL)?.bundleIdentifier,
            liveInstanceID: liveInstanceID,
            liveExecutablePath: liveExecutablePath,
            liveBundleExecutablePath: liveShellBundle.executableURL?.standardizedFileURL.path
        ) else {
            return nil
        }
        return application
    }

    private static func containingAppBundle(forExecutablePath path: String) -> URL? {
        var candidate = URL(fileURLWithPath: path).deletingLastPathComponent()
        while candidate.path != "/" {
            if candidate.pathExtension == "app" {
                return candidate.standardizedFileURL
            }
            candidate.deleteLastPathComponent()
        }
        return nil
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
    HelperLocalization.settingsURL = paths.dataDirectory.appendingPathComponent("settings.json")
    let instanceLock = try HelperInstanceLock(paths: paths)
    let controlCredentials = try HelperControlCredentials(
        instanceID: arguments.instanceID,
        paths: paths
    )
    let developmentSourceRoot = try validatedDevelopmentSourceRoot()
    let application = NSApplication.shared
    let delegate = HelperDelegate(
        arguments: arguments,
        paths: paths,
        instanceLock: instanceLock,
        controlCredentials: controlCredentials,
        developmentSourceRoot: developmentSourceRoot
    )
    application.delegate = delegate
    application.run()
    _ = delegate
} catch {
    FileHandle.standardError.write(Data("AI2Apps Helper: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}
