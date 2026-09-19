import AI2AppsContracts
import Foundation

public struct LocalLaunchPlan: Equatable, Sendable {
    public let executable: URL
    public let arguments: [String]
    public let environment: [String: String]
    public let bootID: UUID
    public let runDescriptorURL: URL

    public init(
        executable: URL,
        instanceID: InstanceID,
        configuration: LocalConfiguration,
        paths: InstancePaths,
        bootID: UUID = UUID(),
        inheritedEnvironment: [String: String] = [:],
        developmentSourceRoot: URL? = nil
    ) throws {
        try configuration.validate()
        guard executable.isFileURL, executable.path.hasPrefix("/") else {
            throw ContractError.invalidField(field: "runtime.executable", reason: "must be an absolute file URL")
        }
        self.executable = executable
        self.bootID = bootID
        runDescriptorURL = paths.runDirectory.appendingPathComponent("local.json")
        arguments = [
            "serve",
            "--host", configuration.bindAddress,
            "--port", String(configuration.launchPort),
            "--base-path", paths.dataDirectory.path,
        ]
        let protectedEnvironmentVariables = Set([
            "HF_HOME",
            "HF_HUB_CACHE",
            "HF_TOKEN",
            "HF_TOKEN_PATH",
            "HUGGINGFACE_HUB_CACHE",
            "HUGGING_FACE_HUB_TOKEN",
            "TRANSFORMERS_CACHE",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "AI2APPS_HF_IMPORT_HUB_CACHE",
            "AI2APPS_CHECKPOINT_CACHE_ROOT",
            "AI2APPS_INSTANCE_SUPPORT_ROOT",
            "AI2APPS_PRESERVED_CHECKPOINT_CACHE_ROOT",
            "AI2APPS_DEVELOPMENT_SOURCE_ROOT",
        ])
        let sanitizedEnvironment = inheritedEnvironment.filter {
            !protectedEnvironmentVariables.contains($0.key)
        }
        var launchEnvironment = sanitizedEnvironment.merging([
            "AI2APPS_INSTANCE_ID": instanceID.rawValue,
            "AI2APPS_BOOT_ID": bootID.uuidString.lowercased(),
            "AI2APPS_RUN_DESCRIPTOR_PATH": runDescriptorURL.path,
            "AI2APPS_SHELL_AUTOMATION_PATH": paths.runDirectory
                .appendingPathComponent("shell-automation.json").path,
            "AI2APPS_SUPERVISED": "helper",
            // Mutable model state and Worker views remain instance-private.
            // Registry-verified immutable checkpoint blobs use a machine-local
            // shared cache and are hard-linked into each private Worker view.
            "HF_HUB_CACHE": paths.instanceHuggingFaceHubDirectory.path,
            "HF_HOME": paths.instanceHuggingFaceHomeDirectory.path,
            "HF_TOKEN_PATH": paths.instanceHuggingFaceHomeDirectory
                .appendingPathComponent("token", isDirectory: false).path,
            "AI2APPS_MODEL_CACHE_ROOT": paths.instanceModelWeightsDirectory.path,
            "AI2APPS_MODEL_CACHE_MODE": "isolated",
            "AI2APPS_CHECKPOINT_CACHE_ROOT": paths.sharedCheckpointCacheDirectory.path,
            "AI2APPS_INSTANCE_SUPPORT_ROOT": paths.supportRoot
                .deletingLastPathComponent().path,
            "AI2APPS_PRESERVED_CHECKPOINT_CACHE_ROOT": paths
                .preservedLegacyCheckpointCacheDirectory
                .deletingLastPathComponent().path,
            // The packaged Runtime is code-signed and must remain immutable
            // after Local starts. Keep Python from writing bytecode into its
            // embedded site-packages and from importing user site packages.
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        ]) { _, required in required }
        if let importHub = paths.externalHuggingFaceHubDirectory {
            launchEnvironment["AI2APPS_HF_IMPORT_HUB_CACHE"] = importHub.path
        }
        if let developmentSourceRoot {
            guard developmentSourceRoot.isFileURL,
                  developmentSourceRoot.path.hasPrefix("/") else {
                throw ContractError.invalidField(
                    field: "development_source_root",
                    reason: "must be an absolute file URL"
                )
            }
            launchEnvironment["AI2APPS_DEVELOPMENT_SOURCE_ROOT"] =
                developmentSourceRoot.standardizedFileURL.path
        }
        environment = launchEnvironment
    }
}
