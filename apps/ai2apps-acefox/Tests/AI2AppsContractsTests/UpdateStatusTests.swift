import AI2AppsContracts
import Foundation
import Testing

@Test func updateStatusIsBoundedAndContainsNoArtifactPaths() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let status = UpdateStatus(
        instanceID: instance,
        phase: .ready,
        currentBuild: "2198",
        candidateBuild: "2200",
        message: "更新已验证，可以安装",
        updatedAt: Date(timeIntervalSince1970: 1_234)
    )
    try status.validate()
    let data = try ContractCodec.encoder().encode(status)
    let decoded = try ContractCodec.decoder().decode(UpdateStatus.self, from: data)
    #expect(decoded == status)
    let text = String(decoding: data, as: UTF8.self)
    #expect(!text.contains(".dmg"))
    #expect(!text.contains("/Users/"))
}

@Test func updateStatusRejectsDowngradeAndUnsafeMessage() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let downgrade = UpdateStatus(
        instanceID: instance,
        phase: .ready,
        currentBuild: "2200",
        candidateBuild: "2198",
        message: "ready"
    )
    #expect(throws: ContractError.self) { try downgrade.validate() }

    let unsafe = UpdateStatus(
        instanceID: instance,
        phase: .failed,
        currentBuild: "2200",
        message: "failed\n/private/secret",
        errorCode: "Bad Error"
    )
    #expect(throws: ContractError.self) { try unsafe.validate() }
}
