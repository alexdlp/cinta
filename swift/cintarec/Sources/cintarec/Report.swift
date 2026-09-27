import Foundation

/// The JSON contract with core/recorder.py (DESIGN.md 4.5).
struct AudioTrack: Encodable {
    let kind: String
    let channels: Int
    var device: String?
}

struct Report: Encodable {
    let path: String
    let durationSeconds: Double
    let fps: Int
    let width: Int
    let height: Int
    let codec: String
    let display: DisplayInfo
    let audioTracks: [AudioTrack]
    let bytes: Int
    let stoppedBy: String
}
