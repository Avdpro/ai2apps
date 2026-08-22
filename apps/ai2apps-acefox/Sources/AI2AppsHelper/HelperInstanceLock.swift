import AI2AppsContracts
import Darwin
import Foundation

final class HelperInstanceLock {
    private let descriptor: Int32

    init(paths: InstancePaths) throws {
        try FileManager.default.createDirectory(
            at: paths.runDirectory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        let lockPath = paths.runDirectory.appendingPathComponent("helper.lock").path
        descriptor = open(lockPath, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else {
            throw ContractError.invalidField(field: "helper.lock", reason: String(cString: strerror(errno)))
        }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            close(descriptor)
            throw ContractError.invalidField(field: "helper.lock", reason: "Helper is already running")
        }
        ftruncate(descriptor, 0)
        let processID = "\(getpid())\n"
        processID.withCString { pointer in
            _ = write(descriptor, pointer, strlen(pointer))
        }
    }

    deinit {
        flock(descriptor, LOCK_UN)
        close(descriptor)
    }
}
