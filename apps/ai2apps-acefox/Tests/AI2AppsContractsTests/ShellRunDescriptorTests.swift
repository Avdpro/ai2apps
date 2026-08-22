import AI2AppsContracts
import Foundation
import Testing

@Test func shellRunDescriptorRoundTrips() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let descriptor = ShellRunDescriptor(
        instanceID: instance,
        processID: 123,
        appBundlePath: "/Applications/AI2Apps.app",
        executablePath: "/Applications/AI2Apps.app/Contents/MacOS/acefox-bin",
        publishedAt: Date(timeIntervalSince1970: 1_234)
    )
    try descriptor.validate()
    let data = try ContractCodec.encoder().encode(descriptor)
    #expect(try ContractCodec.decoder().decode(ShellRunDescriptor.self, from: data) == descriptor)
}

@Test func shellRunDescriptorRejectsUnsafeIdentity() throws {
    let instance = try InstanceID(rawValue: "customer-a")
    let invalid = ShellRunDescriptor(
        instanceID: instance,
        processID: 1,
        appBundlePath: "relative/AI2Apps.app",
        executablePath: "/Applications/AI2Apps.app/Contents/MacOS/acefox-bin"
    )
    #expect(throws: ContractError.self) { try invalid.validate() }
}
