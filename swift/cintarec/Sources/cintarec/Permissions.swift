import AVFoundation
import CoreGraphics
import Foundation

enum Permissions {
    /// macOS grants Screen Recording to the *responsible process*, which is the
    /// terminal emulator, not this binary (DESIGN.md 4.4). So the message has to
    /// name the terminal, not cintarec, or the user will look in the wrong place.
    static func preflightScreenCapture() {
        if CGPreflightScreenCaptureAccess() { return }

        let responsible = ProcessInfo.processInfo.environment["TERM_PROGRAM"] ?? "your terminal"
        log("""
            error: no screen recording permission.

            macOS grants this permission to the application that launched cintarec,
            which is \(responsible) - not cintarec itself.

              1. System Settings > Privacy & Security > Screen & System Audio Recording
              2. Enable \(responsible)
              3. Restart \(responsible) completely

            Open that pane with:
              open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
            """)
        exit(ExitCode.noScreenPermission.rawValue)
    }

    /// The microphone is a separate TCC permission from screen recording, and it
    /// does prompt: unlike screen capture, access can be requested at runtime.
    /// It still needs the embedded Info.plist (see Package.swift) or the process
    /// is killed rather than prompted.
    static func preflightMicrophone() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            return
        case .notDetermined:
            let semaphore = DispatchSemaphore(value: 0)
            var granted = false
            AVCaptureDevice.requestAccess(for: .audio) {
                granted = $0
                semaphore.signal()
            }
            semaphore.wait()
            if granted { return }
            fail(.noMicPermission, "microphone access was denied.")
        default:
            let responsible = ProcessInfo.processInfo.environment["TERM_PROGRAM"] ?? "your terminal"
            log("""
                error: no microphone permission.

                As with screen recording, macOS attributes this to \(responsible),
                not to cintarec.

                  System Settings > Privacy & Security > Microphone > enable \(responsible)
                """)
            exit(ExitCode.noMicPermission.rawValue)
        }
    }
}
