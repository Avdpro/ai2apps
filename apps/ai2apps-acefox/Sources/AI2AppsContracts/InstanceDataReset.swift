import Foundation

public struct InstanceDataReset: Sendable {
    public let paths: InstancePaths

    public init(paths: InstancePaths) {
        self.paths = paths
    }

    /// Removes only the instance-owned support and cache roots. The optional
    /// external Hugging Face Hub import cache is deliberately outside these
    /// roots and is never a reset target.
    public func perform(fileManager: FileManager = .default) throws {
        let targets = try validatedTargets()
        for target in targets {
            try rejectSymbolicLinkComponents(for: target, fileManager: fileManager)
        }
        try preserveLegacyCheckpointCache(fileManager: fileManager)
        // Installed Package and model snapshots are deliberately made
        // read-only after verification. Restore owner access on directories
        // inside the private instance roots before asking Foundation to remove
        // the trees. Internal symbolic links are unlinked as links and are
        // never followed or made writable.
        for target in targets where fileManager.fileExists(atPath: target.path) {
            try makeDirectoryTreeRemovable(at: target, fileManager: fileManager)
        }
        for target in targets where fileManager.fileExists(atPath: target.path) {
            try fileManager.removeItem(at: target)
        }
    }

    public func validatedTargets() throws -> [URL] {
        let supportRoot = paths.supportRoot.standardizedFileURL
        let cacheRoot = paths.cacheRoot.standardizedFileURL
        let targets = [supportRoot, cacheRoot]

        guard targets.allSatisfy({ target in
            target.lastPathComponent == supportRoot.lastPathComponent
                && target.deletingLastPathComponent().lastPathComponent == "instances"
        }) else {
            throw ContractError.invalidField(
                field: "instance_data_reset",
                reason: "target must be an instance root"
            )
        }
        guard supportRoot.path != cacheRoot.path,
              !supportRoot.path.hasPrefix(cacheRoot.path + "/"),
              !cacheRoot.path.hasPrefix(supportRoot.path + "/") else {
            throw ContractError.invalidField(
                field: "instance_data_reset",
                reason: "support and cache roots must be separate"
            )
        }
        if let externalHub = paths.externalHuggingFaceHubDirectory?.standardizedFileURL {
            guard targets.allSatisfy({ target in
                externalHub.path != target.path
                    && !externalHub.path.hasPrefix(target.path + "/")
            }) else {
                throw ContractError.invalidField(
                    field: "instance_data_reset",
                    reason: "external Hugging Face cache must be preserved"
                )
            }
        }
        let sharedCheckpointCache = paths.sharedCheckpointCacheDirectory.standardizedFileURL
        guard targets.allSatisfy({ target in
            sharedCheckpointCache.path != target.path
                && !sharedCheckpointCache.path.hasPrefix(target.path + "/")
        }) else {
            throw ContractError.invalidField(
                field: "instance_data_reset",
                reason: "shared checkpoint cache must be preserved"
            )
        }
        return targets
    }

    private func preserveLegacyCheckpointCache(
        fileManager: FileManager
    ) throws {
        let source = paths.legacyCheckpointCacheDirectory.standardizedFileURL
        guard fileManager.fileExists(atPath: source.path) else { return }
        try rejectSymbolicLinkComponents(for: source, fileManager: fileManager)

        let destination = paths.preservedLegacyCheckpointCacheDirectory
            .standardizedFileURL
        guard !fileManager.fileExists(atPath: destination.path) else {
            throw ContractError.invalidField(
                field: "instance_data_reset",
                reason: "preserved legacy checkpoint cache already exists"
            )
        }
        let parent = destination.deletingLastPathComponent()
        try fileManager.createDirectory(
            at: parent,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        try fileManager.setAttributes(
            [.posixPermissions: 0o700],
            ofItemAtPath: parent.path
        )
        try fileManager.moveItem(at: source, to: destination)
    }

    private func rejectSymbolicLinkComponents(
        for target: URL,
        fileManager: FileManager
    ) throws {
        let components = [
            target,
            target.deletingLastPathComponent(),
            target.deletingLastPathComponent().deletingLastPathComponent(),
        ]
        for component in components where fileManager.fileExists(atPath: component.path) {
            let attributes = try fileManager.attributesOfItem(atPath: component.path)
            guard attributes[.type] as? FileAttributeType != .typeSymbolicLink else {
                throw ContractError.invalidField(
                    field: "instance_data_reset",
                    reason: "target path must not contain symbolic links"
                )
            }
        }
    }

    private func makeDirectoryTreeRemovable(
        at root: URL,
        fileManager: FileManager
    ) throws {
        var pending = [root]
        while let item = pending.popLast() {
            let attributes = try fileManager.attributesOfItem(atPath: item.path)
            guard attributes[.type] as? FileAttributeType != .typeSymbolicLink else {
                continue
            }
            guard attributes[.type] as? FileAttributeType == .typeDirectory else {
                continue
            }

            let permissions = (attributes[.posixPermissions] as? NSNumber)?.uint16Value
                ?? 0
            let removablePermissions = permissions | 0o700
            if removablePermissions != permissions {
                try fileManager.setAttributes(
                    [.posixPermissions: NSNumber(value: removablePermissions)],
                    ofItemAtPath: item.path
                )
            }
            pending.append(contentsOf: try fileManager.contentsOfDirectory(
                at: item,
                includingPropertiesForKeys: nil,
                options: []
            ))
        }
    }
}
