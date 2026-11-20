import Testing
@testable import AI2AppsSupervisorCore

@Test func oneTimeoutDoesNotDeclareAnOutage() {
    var policy = HealthProbePolicy()
    let result1 = policy.record(.transientFailure)
    #expect(!result1)
    #expect(!policy.shouldRestart)
    let result2 = policy.record(.healthy)
    #expect(!result2)
    #expect(policy.consecutiveFailures == 0)
    let result3 = policy.record(.transientFailure)
    #expect(!result3)
}

@Test func sustainedFailureStillAlertsAndRestarts() {
    var policy = HealthProbePolicy()
    let result4 = policy.record(.transientFailure)
    #expect(!result4)
    let result5 = policy.record(.transientFailure)
    #expect(result5)
    #expect(!policy.shouldRestart)
    let result6 = policy.record(.transientFailure)
    #expect(result6)
    #expect(policy.shouldRestart)
    let result7 = policy.record(.healthy)
    #expect(!result7)
    #expect(!policy.shouldRestart)
}

@Test func deadOrMismatchedServiceFailsImmediately() {
    var policy = HealthProbePolicy()
    let result8 = policy.record(.definiteFailure)
    #expect(result8)
    #expect(policy.shouldRestart)
    let result9 = policy.record(.healthy)
    #expect(!result9)
}
