import AI2AppsSupervisorCore
import Foundation
import Testing

@Test func browserAgentLeaseExpiresAfterThirtyIdleMinutes() {
    let start = Date(timeIntervalSince1970: 1_000)
    let lease = BrowserAgentLease(now: start)

    #expect(!lease.isExpired(now: start.addingTimeInterval(1_799)))
    #expect(lease.isExpired(now: start.addingTimeInterval(1_800)))
}

@Test func browserAgentLeaseRenewalRestartsTheIdleWindow() {
    let start = Date(timeIntervalSince1970: 2_000)
    var lease = BrowserAgentLease(now: start)
    lease.renew(now: start.addingTimeInterval(1_200))

    #expect(!lease.isExpired(now: start.addingTimeInterval(2_999)))
    #expect(lease.isExpired(now: start.addingTimeInterval(3_000)))
}

@Test func browserAgentLeasePausesForManualControlAndResumesFresh() {
    let start = Date(timeIntervalSince1970: 3_000)
    var lease = BrowserAgentLease(now: start)
    lease.pause()

    #expect(lease.isPaused)
    #expect(!lease.isExpired(now: start.addingTimeInterval(86_400)))

    lease.resume(now: start.addingTimeInterval(86_400))
    #expect(!lease.isPaused)
    #expect(!lease.isExpired(now: start.addingTimeInterval(88_199)))
    #expect(lease.isExpired(now: start.addingTimeInterval(88_200)))
}
