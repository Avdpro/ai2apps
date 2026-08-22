import Foundation

public struct PackagedHelperLayout: Equatable, Sendable {
    public let instanceID: InstanceID
    public let helperBundleURL: URL
    public let appBundleURL: URL
    public let runtimeExecutable: URL
    public let aceFoxExecutable: URL

    public init(
        helperBundleURL: URL,
        fileManager: FileManager = .default
    ) throws {
        let helper = helperBundleURL.resolvingSymlinksInPath().standardizedFileURL
        let loginItems = helper.deletingLastPathComponent()
        let library = loginItems.deletingLastPathComponent()
        let contents = library.deletingLastPathComponent()
        let app = contents.deletingLastPathComponent()
        guard helper.pathExtension == "app",
              loginItems.lastPathComponent == "LoginItems",
              library.lastPathComponent == "Library",
              contents.lastPathComponent == "Contents",
              app.pathExtension == "app" else {
            throw ContractError.invalidField(
                field: "helper_bundle",
                reason: "must be nested below App/Contents/Library/LoginItems"
            )
        }

        let infoURL = helper.appendingPathComponent("Contents/Info.plist")
        let infoData: Data
        do {
            infoData = try Data(contentsOf: infoURL)
        } catch {
            throw ContractError.invalidField(
                field: "app_bundle",
                reason: "cannot read Helper Info.plist"
            )
        }
        guard let info = try PropertyListSerialization.propertyList(
            from: infoData,
            options: [],
            format: nil
        ) as? [String: Any],
            let rawInstanceID = info["AI2AppsInstanceID"] as? String else {
            throw ContractError.invalidField(
                field: "instance_id",
                reason: "Helper is missing AI2AppsInstanceID"
            )
        }

        let helperContents = helper.appendingPathComponent("Contents", isDirectory: true)
        let runtime = helperContents.appendingPathComponent(
            "Resources/AI2AppsLocal/bin/omlx"
        )
        // Shell and actor-bound browser Agents deliberately share one signed
        // AceFox bundle. Each Agent still receives its own process, profile,
        // automation port, and lease; only the immutable program files are
        // shared so the installed App does not carry a second Gecko runtime.
        let aceFox = contents.appendingPathComponent(
            "Applications/AI2AppsShell.app/Contents/MacOS/acefox-bin"
        )
        guard fileManager.isExecutableFile(atPath: runtime.path) else {
            throw ContractError.invalidField(
                field: "runtime",
                reason: "packaged Local executable is missing"
            )
        }
        guard fileManager.isExecutableFile(atPath: aceFox.path) else {
            throw ContractError.invalidField(
                field: "acefox",
                reason: "packaged AceFox executable is missing"
            )
        }
        let sharedBrowserBundle = aceFox
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        guard Bundle(url: sharedBrowserBundle)?.object(
            forInfoDictionaryKey: "AI2AppsSharedBrowserBundle"
        ) as? Bool == true else {
            throw ContractError.invalidField(
                field: "acefox",
                reason: "shared browser bundle contract is missing"
            )
        }

        instanceID = try InstanceID(rawValue: rawInstanceID)
        self.helperBundleURL = helper
        appBundleURL = app
        runtimeExecutable = runtime
        aceFoxExecutable = aceFox
    }
}

public struct HelperLaunchConfiguration: Equatable, Sendable {
    public let instanceID: InstanceID
    public let runtimeExecutable: URL
    public let aceFoxExecutable: URL?
    public let appBundleURL: URL?
    public let isPackaged: Bool

    public init(
        arguments: [String],
        environment: [String: String] = ProcessInfo.processInfo.environment,
        helperBundleURL: URL,
        fileManager: FileManager = .default
    ) throws {
        var instance: String?
        var runtimePath = environment["AI2APPS_LOCAL_EXECUTABLE"]
        var aceFoxPath = environment["AI2APPS_ACEFOX_EXECUTABLE"]
        var appBundlePath = environment["AI2APPS_APP_BUNDLE"]
        var index = 1
        while index < arguments.count {
            switch arguments[index] {
            case "--instance" where index + 1 < arguments.count:
                index += 1
                instance = arguments[index]
            case "--runtime" where index + 1 < arguments.count:
                index += 1
                runtimePath = arguments[index]
            case "--acefox" where index + 1 < arguments.count:
                index += 1
                aceFoxPath = arguments[index]
            case "--app-bundle" where index + 1 < arguments.count:
                index += 1
                appBundlePath = arguments[index]
            default:
                break
            }
            index += 1
        }

        if let packaged = try? PackagedHelperLayout(
            helperBundleURL: helperBundleURL,
            fileManager: fileManager
        ) {
            try Self.requireMatch(
                supplied: instance,
                packaged: packaged.instanceID.rawValue,
                field: "instance_id"
            )
            try Self.requirePathMatch(
                supplied: runtimePath,
                packaged: packaged.runtimeExecutable,
                field: "runtime"
            )
            try Self.requirePathMatch(
                supplied: aceFoxPath,
                packaged: packaged.aceFoxExecutable,
                field: "acefox"
            )
            try Self.requirePathMatch(
                supplied: appBundlePath,
                packaged: packaged.appBundleURL,
                field: "app_bundle"
            )
            instanceID = packaged.instanceID
            runtimeExecutable = packaged.runtimeExecutable
            aceFoxExecutable = packaged.aceFoxExecutable
            appBundleURL = packaged.appBundleURL
            isPackaged = true
            return
        }

        guard let runtimePath, runtimePath.hasPrefix("/") else {
            throw ContractError.invalidField(
                field: "runtime",
                reason: "pass --runtime /absolute/path or AI2APPS_LOCAL_EXECUTABLE"
            )
        }
        let runtime = URL(fileURLWithPath: runtimePath).standardizedFileURL
        guard fileManager.isExecutableFile(atPath: runtime.path) else {
            throw ContractError.invalidField(
                field: "runtime",
                reason: "executable not found"
            )
        }
        instanceID = try InstanceID(rawValue: instance ?? "default")
        runtimeExecutable = runtime
        aceFoxExecutable = try Self.optionalExecutable(
            path: aceFoxPath,
            field: "acefox",
            fileManager: fileManager
        )
        if let appBundlePath {
            guard appBundlePath.hasPrefix("/"), appBundlePath.hasSuffix(".app") else {
                throw ContractError.invalidField(
                    field: "app_bundle",
                    reason: "must be an absolute .app path"
                )
            }
            appBundleURL = URL(fileURLWithPath: appBundlePath, isDirectory: true)
                .standardizedFileURL
        } else {
            appBundleURL = nil
        }
        isPackaged = false
    }

    private static func optionalExecutable(
        path: String?,
        field: String,
        fileManager: FileManager
    ) throws -> URL? {
        guard let path else { return nil }
        guard path.hasPrefix("/") else {
            throw ContractError.invalidField(field: field, reason: "must be absolute")
        }
        let url = URL(fileURLWithPath: path).standardizedFileURL
        guard fileManager.isExecutableFile(atPath: url.path) else {
            throw ContractError.invalidField(field: field, reason: "executable not found")
        }
        return url
    }

    private static func requireMatch(
        supplied: String?,
        packaged: String,
        field: String
    ) throws {
        guard supplied == nil || supplied == packaged else {
            throw ContractError.invalidField(
                field: field,
                reason: "cannot override signed packaged identity"
            )
        }
    }

    private static func requirePathMatch(
        supplied: String?,
        packaged: URL,
        field: String
    ) throws {
        guard let supplied else { return }
        guard supplied.hasPrefix("/"),
              URL(fileURLWithPath: supplied).resolvingSymlinksInPath().standardizedFileURL == packaged else {
            throw ContractError.invalidField(
                field: field,
                reason: "cannot override signed packaged path"
            )
        }
    }
}
