import AppKit
import Darwin
import Foundation

private enum ServiceState {
    case stopped
    case starting
    case running
    case stopping

    var label: String {
        switch self {
        case .stopped: return "AI2Apps：已停止"
        case .starting: return "AI2Apps：正在启动…"
        case .running: return "AI2Apps：运行中"
        case .stopping: return "AI2Apps：正在停止…"
        }
    }
}

@MainActor
final class TrayDelegate: NSObject, NSApplicationDelegate {
    private let projectDirectory = "/Users/avdpropang/sdk/omlx-moe-cache"
    private let port = 8000

    private lazy var baseDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".omlx", isDirectory: true)
    private lazy var modelDirectory = baseDirectory.appendingPathComponent("models", isDirectory: true)
    private lazy var logDirectory = baseDirectory.appendingPathComponent("logs", isDirectory: true)
    private lazy var logURL = logDirectory.appendingPathComponent("tray-helper.log")
    private lazy var pidURL = baseDirectory.appendingPathComponent("ai2apps-tray-server.pid")
    private lazy var helperPIDURL = baseDirectory.appendingPathComponent("ai2apps-tray-helper.pid")
    private lazy var iconPathURL = baseDirectory.appendingPathComponent("ai2apps-tray-icon-path")
    private lazy var settingsURL = baseDirectory.appendingPathComponent("settings.json")

    private var statusItem: NSStatusItem!
    private let menu = NSMenu()
    private var statusMenuItem: NSMenuItem!
    private var startMenuItem: NSMenuItem!
    private var stopMenuItem: NSMenuItem!
    private var restartMenuItem: NSMenuItem!
    private var dashboardMenuItem: NSMenuItem!
    private var copyAPIKeyMenuItem: NSMenuItem!
    private var timer: Timer?
    private var serverProcess: Process?
    private var state: ServiceState = .stopped
    private var healthCheckInFlight = false
    private var customIcon: NSImage?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        do {
            try FileManager.default.createDirectory(
                at: logDirectory,
                withIntermediateDirectories: true
            )
            try String(ProcessInfo.processInfo.processIdentifier)
                .write(to: helperPIDURL, atomically: true, encoding: .utf8)
        } catch {
            presentError("无法准备 Helper 数据目录：\(error.localizedDescription)")
        }

        loadConfiguredIcon()
        buildMenu()
        refreshHealth()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshHealth() }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        try? FileManager.default.removeItem(at: helperPIDURL)
    }

    private func buildMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem.button?.toolTip = "AI2Apps 服务控制"
        statusItem.menu = menu
        menu.autoenablesItems = false

        statusMenuItem = NSMenuItem(title: state.label, action: nil, keyEquivalent: "")
        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)
        menu.addItem(.separator())

        startMenuItem = menuItem("启动服务", action: #selector(startServer), symbol: "play.circle")
        stopMenuItem = menuItem("停止服务", action: #selector(stopServer), symbol: "stop.circle")
        restartMenuItem = menuItem("重启服务", action: #selector(restartServer), symbol: "arrow.clockwise.circle")
        menu.addItem(startMenuItem)
        menu.addItem(stopMenuItem)
        menu.addItem(restartMenuItem)
        menu.addItem(.separator())

        dashboardMenuItem = menuItem("打开管理后台", action: #selector(openDashboard), symbol: "gauge.with.dots.needle.67percent")
        menu.addItem(dashboardMenuItem)
        copyAPIKeyMenuItem = menuItem("复制 API Key", action: #selector(copyAPIKey), symbol: "key.horizontal")
        menu.addItem(copyAPIKeyMenuItem)
        menu.addItem(menuItem("打开服务日志", action: #selector(openLog), symbol: "doc.text"))
        menu.addItem(.separator())
        menu.addItem(menuItem("退出 Helper", action: #selector(quitHelper), symbol: "power"))

        renderState()
    }

    private func menuItem(_ title: String, action: Selector, symbol: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        item.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        return item
    }

    private func renderState() {
        statusMenuItem.title = state.label
        let isLive = state == .running || state == .starting
        let isTransitioning = state == .starting || state == .stopping
        startMenuItem.isEnabled = !isLive && !isTransitioning
        stopMenuItem.isEnabled = isLive && !isTransitioning
        restartMenuItem.isEnabled = !isTransitioning
        dashboardMenuItem.isEnabled = state == .running

        let image: NSImage?
        if let customIcon {
            image = customIcon
        } else {
            let symbolName = isLive ? "bolt.horizontal.circle.fill" : "bolt.horizontal.circle"
            let configuration = NSImage.SymbolConfiguration(pointSize: 16, weight: .semibold)
            image = NSImage(systemSymbolName: symbolName, accessibilityDescription: "AI2Apps")?
                .withSymbolConfiguration(configuration)
            image?.isTemplate = true
        }
        statusItem.button?.title = ""
        statusItem.button?.image = image
        statusItem.button?.alphaValue = isLive ? 1.0 : 0.5
    }

    private func loadConfiguredIcon() {
        let arguments = ProcessInfo.processInfo.arguments
        if arguments.contains("--default-icon") {
            try? FileManager.default.removeItem(at: iconPathURL)
        } else if let flagIndex = arguments.firstIndex(of: "--icon"),
                  arguments.indices.contains(flagIndex + 1) {
            let requestedPath = NSString(string: arguments[flagIndex + 1]).expandingTildeInPath
            do {
                try requestedPath.write(to: iconPathURL, atomically: true, encoding: .utf8)
            } catch {
                presentError("无法保存图标设置：\(error.localizedDescription)")
            }
        }

        guard let savedPath = try? String(contentsOf: iconPathURL, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !savedPath.isEmpty
        else {
            customIcon = nil
            return
        }

        guard let loaded = NSImage(contentsOfFile: savedPath) else {
            customIcon = nil
            presentError("无法读取自定义图标：\(savedPath)\n\n请使用有效的 PNG 或 SVG 文件。")
            return
        }
        loaded.size = NSSize(width: 18, height: 18)
        loaded.isTemplate = false
        customIcon = loaded
    }

    private func setState(_ next: ServiceState) {
        state = next
        renderState()
    }

    private func refreshHealth() {
        guard !healthCheckInFlight else { return }
        healthCheckInFlight = true
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/v1/models")!)
        request.timeoutInterval = 1
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            let reachable = response is HTTPURLResponse
            Task { @MainActor in
                guard let self else { return }
                self.healthCheckInFlight = false
                if reachable {
                    self.setState(.running)
                } else if self.state != .starting && self.state != .stopping {
                    self.setState(.stopped)
                }
            }
        }.resume()
    }

    @objc private func startServer() {
        guard state != .running && state != .starting else { return }
        setState(.starting)

        do {
            let logHandle = try openLogHandle()
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/zsh")
            process.currentDirectoryURL = URL(fileURLWithPath: projectDirectory, isDirectory: true)
            process.arguments = [
                "-lc",
                "if [[ ! -x .venv/bin/ai2apps ]]; then /opt/homebrew/bin/uv sync --dev; fi && exec .venv/bin/ai2apps serve --model-dir \"$HOME/.omlx/models\" --port \(port)"
            ]
            process.standardOutput = logHandle
            process.standardError = logHandle
            process.terminationHandler = { [weak self] _ in
                Task { @MainActor in
                    guard let self else { return }
                    self.serverProcess = nil
                    try? FileManager.default.removeItem(at: self.pidURL)
                    self.refreshHealth()
                }
            }
            try process.run()
            serverProcess = process
            try String(process.processIdentifier).write(to: pidURL, atomically: true, encoding: .utf8)
        } catch {
            setState(.stopped)
            presentError("启动失败：\(error.localizedDescription)\n\n请查看日志：\(logURL.path)")
        }
    }

    @objc private func stopServer() {
        requestStop(restartAfterStop: false)
    }

    @objc private func restartServer() {
        if state == .stopped {
            startServer()
            return
        }
        requestStop(restartAfterStop: true)
    }

    private func requestStop(restartAfterStop: Bool) {
        guard state != .stopped && state != .stopping else { return }

        let pids: [pid_t]
        if let ownedPID = ownedServerPID() {
            pids = [ownedPID]
        } else {
            pids = listeningPIDs()
            guard !pids.isEmpty else {
                setState(.stopped)
                refreshHealth()
                return
            }
            guard confirmForceStop(pids: pids, restarting: restartAfterStop) else {
                refreshHealth()
                return
            }
        }

        setState(.stopping)
        let failures = pids.filter { pid in
            Darwin.kill(pid, SIGTERM) == -1 && errno != ESRCH
        }
        guard failures.isEmpty else {
            setState(.running)
            presentError("无法终止进程：\(failures.map(String.init).joined(separator: ", "))。请检查进程权限。")
            return
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            guard let self else { return }
            for pid in pids where Darwin.kill(pid, 0) == 0 {
                Darwin.kill(pid, SIGKILL)
            }
            try? FileManager.default.removeItem(at: self.pidURL)

            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { [weak self] in
                guard let self else { return }
                let remaining = self.listeningPIDs()
                guard remaining.isEmpty else {
                    self.setState(.running)
                    self.presentError("端口 \(self.port) 仍被进程 \(remaining.map(String.init).joined(separator: ", ")) 占用。")
                    return
                }
                if restartAfterStop {
                    self.setState(.stopped)
                    self.startServer()
                } else {
                    self.setState(.stopped)
                    self.refreshHealth()
                }
            }
        }
    }

    private func listeningPIDs() -> [pid_t] {
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        process.arguments = ["-nP", "-tiTCP:\(port)", "-sTCP:LISTEN"]
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return []
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        return Array(Set(output.split(whereSeparator: \.isNewline).compactMap { pid_t($0) }))
            .filter { $0 > 1 && $0 != ProcessInfo.processInfo.processIdentifier }
            .sorted()
    }

    private func confirmForceStop(pids: [pid_t], restarting: Bool) -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        let details = pids.map { pid in
            let command = commandLine(for: pid).trimmingCharacters(in: .whitespacesAndNewlines)
            return command.isEmpty ? "PID \(pid)" : "PID \(pid): \(command)"
        }.joined(separator: "\n")

        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "端口 \(port) 被其他进程占用"
        alert.informativeText = "该服务不是由 AI2Apps Helper 启动的。是否强制终止以下监听进程\(restarting ? "并重启 AI2Apps" : "")？\n\n\(details)"
        alert.addButton(withTitle: "强制停止")
        alert.addButton(withTitle: "取消")
        return alert.runModal() == .alertFirstButtonReturn
    }

    private func ownedServerPID() -> pid_t? {
        if let process = serverProcess, process.isRunning {
            return process.processIdentifier
        }
        guard let text = try? String(contentsOf: pidURL, encoding: .utf8),
              let rawPID = Int32(text.trimmingCharacters(in: .whitespacesAndNewlines)),
              rawPID > 1,
              Darwin.kill(rawPID, 0) == 0,
              commandLine(for: rawPID).contains("ai2apps serve")
        else { return nil }
        return rawPID
    }

    private func commandLine(for pid: pid_t) -> String {
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/ps")
        process.arguments = ["-p", String(pid), "-o", "command="]
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        try? process.run()
        process.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func openLogHandle() throws -> FileHandle {
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        return handle
    }

    @objc private func openDashboard() {
        NSWorkspace.shared.open(URL(string: "http://127.0.0.1:\(port)/admin/dashboard")!)
    }

    @objc private func copyAPIKey() {
        do {
            let data = try Data(contentsOf: settingsURL)
            guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let auth = root["auth"] as? [String: Any],
                  let apiKey = auth["api_key"] as? String,
                  !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            else {
                presentError("尚未配置 API Key。\n\n配置文件：\(settingsURL.path)")
                return
            }

            let pasteboard = NSPasteboard.general
            pasteboard.clearContents()
            guard pasteboard.setString(apiKey, forType: .string) else {
                presentError("无法写入系统剪贴板。")
                return
            }

            copyAPIKeyMenuItem.title = "API Key 已复制"
            copyAPIKeyMenuItem.image = NSImage(
                systemSymbolName: "checkmark.circle",
                accessibilityDescription: nil
            )
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                guard let self else { return }
                self.copyAPIKeyMenuItem.title = "复制 API Key"
                self.copyAPIKeyMenuItem.image = NSImage(
                    systemSymbolName: "key.horizontal",
                    accessibilityDescription: nil
                )
            }
        } catch {
            presentError("无法读取 API Key：\(error.localizedDescription)\n\n配置文件：\(settingsURL.path)")
        }
    }

    @objc private func openLog() {
        NSWorkspace.shared.open(logURL)
    }

    @objc private func quitHelper() {
        NSApp.terminate(nil)
    }

    private func presentError(_ message: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = "AI2Apps Helper"
        alert.informativeText = message
        alert.runModal()
    }
}

@main
struct AI2AppsTrayMain {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = TrayDelegate()
        app.delegate = delegate
        app.run()
    }
}
