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
        inheritedEnvironment: [String: String] = [:]
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
        let inheritedModelVariables = Set([
            "HF_HOME",
            "HF_HUB_CACHE",
            "HF_TOKEN",
            "HF_TOKEN_PATH",
            "HUGGINGFACE_HUB_CACHE",
            "HUGGING_FACE_HUB_TOKEN",
            "TRANSFORMERS_CACHE",
        ])
        let sanitizedEnvironment = inheritedEnvironment.filter {
            !inheritedModelVariables.contains($0.key)
        }
        environment = sanitizedEnvironment.merging([
            "AI2APPS_INSTANCE_ID": instanceID.rawValue,
            "AI2APPS_BOOT_ID": bootID.uuidString.lowercased(),
            "AI2APPS_RUN_DESCRIPTOR_PATH": runDescriptorURL.path,
            "AI2APPS_SHELL_AUTOMATION_PATH": paths.runDirectory
                .appendingPathComponent("shell-automation.json").path,
            "AI2APPS_SUPERVISED": "helper",
            // Model files are instance-private. Sibling AI2Apps installations
            // consume exported model capability through an authenticated Local
            // upstream instead of sharing a mutable filesystem cache.
            "HF_HUB_CACHE": paths.instanceHuggingFaceHubDirectory.path,
            "HF_HOME": paths.instanceHuggingFaceHomeDirectory.path,
            "HF_TOKEN_PATH": paths.instanceHuggingFaceHomeDirectory
                .appendingPathComponent("token", isDirectory: false).path,
            "AI2APPS_MODEL_CACHE_ROOT": paths.instanceModelWeightsDirectory.path,
            "AI2APPS_MODEL_CACHE_MODE": "isolated",
        ]) { _, required in required }
    }
}
