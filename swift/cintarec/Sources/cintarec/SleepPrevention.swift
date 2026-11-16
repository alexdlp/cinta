import Foundation
import IOKit.pwr_mgt

/// Keep an unattended recording visible and running without changing the
/// user's power settings. macOS also releases these assertions on process exit.
final class SleepPrevention {
    private(set) var assertionIDs: [IOPMAssertionID] = []

    struct Unavailable: LocalizedError {
        let status: IOReturn

        var errorDescription: String? {
            "could not prevent sleep during recording (IOKit error \(status))"
        }
    }

    init() throws {
        for type in [
            kIOPMAssertionTypePreventUserIdleDisplaySleep,
            kIOPMAssertionTypePreventUserIdleSystemSleep,
        ] {
            var id = IOPMAssertionID(0)
            let status = IOPMAssertionCreateWithName(
                type as CFString, IOPMAssertionLevel(kIOPMAssertionLevelOn),
                "cinta screen recording" as CFString, &id)
            guard status == kIOReturnSuccess else {
                release()
                throw Unavailable(status: status)
            }
            assertionIDs.append(id)
        }
    }

    func release() {
        for id in assertionIDs {
            IOPMAssertionRelease(id)
        }
        assertionIDs.removeAll()
    }

    deinit {
        release()
    }
}
