import AI2AppsContracts
import CryptoKit
import Foundation

public struct BrowserAgentProfileID: Equatable, Hashable, Sendable, CustomStringConvertible {
    public let rawValue: String

    public init(rawValue: String) throws {
        guard rawValue.count == 64,
              rawValue.unicodeScalars.allSatisfy({ scalar in
                  (scalar.value >= 48 && scalar.value <= 57) ||
                      (scalar.value >= 97 && scalar.value <= 102)
              }) else {
            throw ContractError.invalidField(field: "browser_profile_id", reason: "must be a lowercase SHA-256 digest")
        }
        self.rawValue = rawValue
    }

    public static func derive(
        instanceID: InstanceID,
        actorUserID: String,
        profileKey: String = "default"
    ) throws -> Self {
        let normalizedUserID = actorUserID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard (1...200).contains(normalizedUserID.utf8.count) else {
            throw ContractError.invalidField(field: "actor_user_id", reason: "must contain 1 to 200 UTF-8 bytes")
        }
        let validCustomKey = profileKey.count == 32 && profileKey.unicodeScalars.allSatisfy { scalar in
            (scalar.value >= 48 && scalar.value <= 57) ||
                (scalar.value >= 97 && scalar.value <= 102)
        }
        guard profileKey == "default" || validCustomKey else {
            throw ContractError.invalidField(
                field: "browser_profile_key",
                reason: "must be default or a lowercase 128-bit hexadecimal identifier"
            )
        }
        // Preserve the original derivation for the default Profile so existing
        // authenticated browser state remains available after this feature ships.
        let material = profileKey == "default"
            ? Data("ai2apps-browser-profile-v1\0\(instanceID.rawValue)\0\(normalizedUserID)".utf8)
            : Data("ai2apps-browser-profile-v2\0\(instanceID.rawValue)\0\(normalizedUserID)\0\(profileKey)".utf8)
        let digest = SHA256.hash(data: material).map { String(format: "%02x", $0) }.joined()
        return try Self(rawValue: digest)
    }

    public var description: String { rawValue }
}

public struct BrowserAgentLaunchPlan: Equatable, Sendable {
    public let executable: URL
    public let profileDirectory: URL
    public let arguments: [String]
    public let environment: [String: String]

    public init(
        executable: URL,
        instanceID: InstanceID,
        actorUserID: String,
        profileKey: String = "default",
        paths: InstancePaths,
        initialURL: URL? = nil,
        automation: BrowserAgentAutomation? = nil,
        inheritedEnvironment: [String: String] = [:]
    ) throws {
        guard executable.isFileURL, executable.path.hasPrefix("/") else {
            throw ContractError.invalidField(field: "acefox.executable", reason: "must be an absolute file URL")
        }
        let profileID = try BrowserAgentProfileID.derive(
            instanceID: instanceID,
            actorUserID: actorUserID,
            profileKey: profileKey
        )
        self.executable = executable
        if let initialURL,
           !["http", "https"].contains(initialURL.scheme?.lowercased() ?? "") {
            throw ContractError.invalidField(field: "initial_url", reason: "must use http or https")
        }
        profileDirectory = paths.browserProfilesDirectory
            .appendingPathComponent("agents", isDirectory: true)
            .appendingPathComponent(profileID.rawValue, isDirectory: true)
        var launchArguments = [
            "-new-instance",
            "-profile", profileDirectory.path,
            "-new-window", initialURL?.absoluteString ?? "about:blank",
        ]
        if let automation {
            try automation.validate()
            launchArguments.append(contentsOf: [
                "--remote-debugging-port", String(automation.port),
                "--remote-allow-hosts", "localhost,127.0.0.1",
            ])
        }
        arguments = launchArguments
        var requiredEnvironment = [
            "AI2APPS_INSTANCE_ID": instanceID.rawValue,
            "AI2APPS_BROWSER_PROFILE_ID": profileID.rawValue,
            "AI2APPS_BROWSER_ROLE": "agent",
            // The shared AI2AppsShell.app is a regular foreground App for the
            // product Shell. Agent instances remain visible but do not create
            // extra Dock or Command-Tab entries.
            "MOZ_APP_NO_DOCK": "1",
        ]
        if let automation {
            requiredEnvironment["AI2APPS_REMOTE_AGENT_TOKEN"] = automation.token
        }
        let safeInheritedKeys: Set<String> = [
            "HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH", "SHELL", "TMPDIR", "TZ",
        ]
        let safeInheritedEnvironment = inheritedEnvironment.filter { key, _ in
            safeInheritedKeys.contains(key) || key.hasPrefix("LC_")
        }
        environment = safeInheritedEnvironment.merging(requiredEnvironment) { _, required in required }
    }
}

public struct BrowserAgentAutomation: Equatable, Sendable {
    public let port: Int
    public let token: String

    public init(port: Int, token: String) {
        self.port = port
        self.token = token
    }

    public func validate() throws {
        guard (1024...65535).contains(port) else {
            throw ContractError.invalidField(field: "browser_agent.port", reason: "must be 1024 to 65535")
        }
        guard token.count == 64,
              token.unicodeScalars.allSatisfy({ scalar in
                  (scalar.value >= 48 && scalar.value <= 57) ||
                      (scalar.value >= 97 && scalar.value <= 102)
              }) else {
            throw ContractError.invalidField(
                field: "browser_agent.token",
                reason: "must be a lowercase 256-bit hexadecimal token"
            )
        }
    }

    public var webSocketURL: URL {
        URL(string: "ws://127.0.0.1:\(port)/session")!
    }
}
