import AI2AppsContracts
import Foundation
import Testing

@Test func bootstrapAcceptsMatchingInstanceAndBoot() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let bootID = UUID()
    let bootstrap = ClientBootstrap(
        status: "ready",
        product: "ai2apps",
        productVersion: "1.0.0",
        apiVersion: 1,
        instanceID: instanceID,
        installationID: "installation-a",
        bootID: bootID,
        shellPath: "/",
        capabilities: ["shell"]
    )

    try bootstrap.validate(expectedInstanceID: instanceID, expectedBootID: bootID)
}

@Test func bootstrapRejectsAnotherBoot() throws {
    let instanceID = try InstanceID(rawValue: "customer-a")
    let bootstrap = ClientBootstrap(
        status: "ready",
        product: "ai2apps",
        productVersion: "1.0.0",
        apiVersion: 1,
        instanceID: instanceID,
        installationID: "installation-a",
        bootID: UUID(),
        shellPath: "/",
        capabilities: ["shell"]
    )

    #expect(throws: ContractError.self) {
        try bootstrap.validate(expectedInstanceID: instanceID, expectedBootID: UUID())
    }
}
