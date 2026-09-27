import Foundation
import Testing

@testable import cintarec

// core/recorder.py and the cinta commands read these keys by name. Renaming a
// Swift property silently renames the key, so the shape is pinned here.

private func object(_ value: some Encodable) throws -> [String: Any] {
    try #require(JSONSerialization.jsonObject(with: encodeJSON(value)) as? [String: Any])
}

private let display = DisplayInfo(
    index: 1, id: 1, name: "Built-in", width: 1512, height: 982, scale: 2,
    pixelWidth: 3024, pixelHeight: 1964, isMain: true)

@Test func listShape() throws {
    let content = ShareableContent(
        displays: [display],
        microphones: [MicrophoneInfo(index: 1, id: "uid", name: "Mic", isDefault: true)],
        windows: [
            WindowInfo(id: 3, app: "Finder", bundleID: "com.apple.finder", title: "", width: 1, height: 1)
        ],
        applications: [ApplicationInfo(bundleID: "com.apple.finder", name: "Finder", pid: 1)]
    )
    let json = try object(content)
    #expect(Set(json.keys) == ["displays", "microphones", "windows", "applications"])

    let displays = try #require(json["displays"] as? [[String: Any]])
    #expect(Set(displays[0].keys) == [
        "index", "id", "name", "width", "height", "scale", "pixelWidth", "pixelHeight", "isMain",
    ])
    let microphones = try #require(json["microphones"] as? [[String: Any]])
    #expect(Set(microphones[0].keys) == ["index", "id", "name", "isDefault"])
}

@Test func reportShape() throws {
    let report = Report(
        path: "/tmp/a.mov", durationSeconds: 3, fps: 30, width: 3024, height: 1964,
        codec: "h264", display: display,
        audioTracks: [
            AudioTrack(kind: "system", channels: 2),
            AudioTrack(kind: "mic", channels: 1, device: "Mic"),
        ],
        bytes: 1024, stoppedBy: "duration")
    let json = try object(report)
    #expect(Set(json.keys) == [
        "path", "durationSeconds", "fps", "width", "height", "codec", "display",
        "audioTracks", "bytes", "stoppedBy",
    ])

    // A track without a device omits the key rather than writing null.
    let tracks = try #require(json["audioTracks"] as? [[String: Any]])
    #expect(Set(tracks[0].keys) == ["kind", "channels"])
    #expect(Set(tracks[1].keys) == ["kind", "channels", "device"])
}

@Test func pathsAreNotEscaped() throws {
    let text = try #require(String(data: encodeJSON(["path": "/tmp/a.mov"]), encoding: .utf8))
    #expect(text.contains("\"/tmp/a.mov\""))
}

@Test func startedIsOneLineWithItsKeys() throws {
    let data = try encodeJSON(
        StartedEvent(path: "/tmp/a.mov", startedAt: "2026-09-27T12:00:00.000Z"), oneLine: true)
    let text = try #require(String(data: data, encoding: .utf8))
    // core/recorder.py recognises the event by this prefix before parsing it.
    #expect(text.hasPrefix("{\"event\":\"started\""))
    #expect(!text.contains("\n"))
    #expect(Set(try object(StartedEvent(path: "", startedAt: "")).keys) == ["event", "path", "startedAt"])
}
