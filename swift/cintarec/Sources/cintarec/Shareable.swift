import AppKit
import ScreenCaptureKit

/// A capturable display. SCDisplay gives dimensions in points but no human name,
/// so the name and the scale factor are cross-referenced from NSScreen.
struct DisplayInfo: Encodable {
    let index: Int
    let id: UInt32
    let name: String
    let width: Int
    let height: Int
    let scale: Int
    let pixelWidth: Int
    let pixelHeight: Int
    let isMain: Bool
}

struct WindowInfo: Encodable {
    let id: UInt32
    let app: String
    let bundleID: String
    let title: String
    let width: Int
    let height: Int
}

struct ApplicationInfo: Encodable {
    let bundleID: String
    let name: String
    let pid: Int32
}

struct ShareableContent: Encodable {
    let displays: [DisplayInfo]
    let microphones: [MicrophoneInfo]
    let windows: [WindowInfo]
    let applications: [ApplicationInfo]
}

enum Shareable {
    static func dump() async {
        let content: SCShareableContent
        do {
            content = try await SCShareableContent.excludingDesktopWindows(
                false, onScreenWindowsOnly: true)
        } catch {
            fail(.noScreenPermission, "could not query shareable content: \(error.localizedDescription)")
        }

        emitJSON(
            ShareableContent(
                displays: displays(from: content),
                microphones: Microphones.all(),
                windows: windows(from: content),
                applications: applications(from: content)
            ))
    }

    /// Displays are ordered left to right by their position in the desktop
    /// arrangement, so `--display 1` is the leftmost screen. The index is only
    /// stable while the arrangement is: plugging a monitor in renumbers them,
    /// which is why `--display` also accepts the (stable) display id.
    static func displays(from content: SCShareableContent) -> [DisplayInfo] {
        let mainID = CGMainDisplayID()
        return content.displays
            .sorted { $0.frame.origin.x < $1.frame.origin.x }
            .enumerated()
            .map { index, display in
                let screen = nsScreen(for: display.displayID)
                let scale = Int(screen?.backingScaleFactor ?? 1)
                return DisplayInfo(
                    index: index + 1,
                    id: display.displayID,
                    name: screen?.localizedName ?? "Display \(display.displayID)",
                    width: display.width,
                    height: display.height,
                    scale: scale,
                    pixelWidth: display.width * scale,
                    pixelHeight: display.height * scale,
                    isMain: display.displayID == mainID
                )
            }
    }

    static func windows(from content: SCShareableContent) -> [WindowInfo] {
        // WindowServer owns a pile of internal windows ("Menubar", "Display 1
        // Backstop") that have a title but no real owning application. They are
        // not useful capture targets, so they are dropped from the listing.
        content.windows
            .filter { window in
                guard let app = window.owningApplication else { return false }
                return window.title?.isEmpty == false && !app.applicationName.isEmpty
            }
            .map { window in
                WindowInfo(
                    id: window.windowID,
                    app: window.owningApplication?.applicationName ?? "",
                    bundleID: window.owningApplication?.bundleIdentifier ?? "",
                    title: window.title ?? "",
                    width: Int(window.frame.width),
                    height: Int(window.frame.height)
                )
            }
            .sorted { ($0.app, $0.title) < ($1.app, $1.title) }
    }

    static func applications(from content: SCShareableContent) -> [ApplicationInfo] {
        content.applications
            .map {
                ApplicationInfo(
                    bundleID: $0.bundleIdentifier, name: $0.applicationName, pid: $0.processID)
            }
            .sorted { $0.name < $1.name }
    }

    /// SCDisplay has no name; NSScreen has one but is keyed by CGDirectDisplayID
    /// buried in deviceDescription.
    private static func nsScreen(for displayID: CGDirectDisplayID) -> NSScreen? {
        let key = NSDeviceDescriptionKey("NSScreenNumber")
        return NSScreen.screens.first {
            ($0.deviceDescription[key] as? NSNumber)?.uint32Value == displayID
        }
    }
}
