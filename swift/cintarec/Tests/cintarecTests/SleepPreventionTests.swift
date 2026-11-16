import Foundation
import IOKit.pwr_mgt
import Testing

@testable import cintarec

@Test func recordingHoldsRealPowerAssertionsAndReleasesThem() throws {
    let prevention = try SleepPrevention()
    defer { prevention.release() }
    let ids = prevention.assertionIDs
    #expect(ids.count == 2)

    let properties = try ids.map { id in
        try #require(IOPMAssertionCopyProperties(id)?.takeRetainedValue() as? [String: Any])
    }
    #expect(Set(properties.compactMap { $0[kIOPMAssertionTypeKey] as? String }) == [
        kIOPMAssertionTypePreventUserIdleDisplaySleep,
        kIOPMAssertionTypePreventUserIdleSystemSleep,
    ])
    #expect(properties.allSatisfy { ($0[kIOPMAssertionLevelKey] as? Int) == kIOPMAssertionLevelOn })
    // No two-hour (or other) timeout: protection lasts until recording finishes.
    #expect(properties.allSatisfy { ($0[kIOPMAssertionTimeoutKey] as? Double ?? 0) == 0 })

    prevention.release()
    #expect(ids.allSatisfy { IOPMAssertionCopyProperties($0) == nil })
    prevention.release()
}

@Test func exitingScopeReleasesPowerAssertions() throws {
    func acquireAndLeave() throws -> [IOPMAssertionID] {
        let prevention = try SleepPrevention()
        return prevention.assertionIDs
    }
    let ids = try acquireAndLeave()
    #expect(ids.allSatisfy { IOPMAssertionCopyProperties($0) == nil })
}
