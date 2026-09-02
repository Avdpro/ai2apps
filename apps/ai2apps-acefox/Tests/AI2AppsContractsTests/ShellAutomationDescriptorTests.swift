import AI2AppsContracts
import Foundation
import Testing

@Test func shellAutomationDescriptorRoundTrips() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let descriptor = ShellAutomationDescriptor(
        instanceID: instance,
        port: 49152,
        token: String(repeating: "a", count: 64),
        processID: 123,
        publishedAt: Date(timeIntervalSince1970: 1_234)
    )
    try descriptor.validate()
    let data = try ContractCodec.encoder().encode(descriptor)
    #expect(
        try ContractCodec.decoder().decode(
            ShellAutomationDescriptor.self,
            from: data
        ) == descriptor
    )
}

@Test func shellAutomationDescriptorRejectsUnsafeEndpoint() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let invalid = ShellAutomationDescriptor(
        instanceID: instance,
        port: 80,
        token: "secret",
        processID: 1
    )
    #expect(throws: ContractError.self) { try invalid.validate() }
}
