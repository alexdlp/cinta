import Foundation

enum AudioMode: String {
    case system
    case mic
    case both
    case none

    var capturesSystem: Bool { self == .system || self == .both }
    var capturesMic: Bool { self == .mic || self == .both }
}

enum VideoCodec: String {
    case h264
    case hevc
}

struct RecordOptions {
    var display: String?  // index from --list, or id:N
    var mic: String?  // index from --list, or id:UID
    var duration: Double?  // nil = record until SIGINT
    var output: URL
    var audio: AudioMode = .system
    var fps: Int = 30
    var scale: Double = 1
    var showsCursor: Bool = true
    var codec: VideoCodec = .h264
}

enum Command {
    case record(RecordOptions)
    case list
    case version
    case help
}

/// A bad command line. Thrown rather than exiting on the spot so the parser can
/// be tested; main.swift turns it into exit code 20.
struct UsageError: Error {
    let message: String
    init(_ message: String) { self.message = message }
}

enum Options {
    static func parse(_ arguments: [String]) throws -> Command {
        if arguments.isEmpty {
            throw UsageError("no arguments given.\n\n\(usage)")
        }
        if arguments.contains("--help") || arguments.contains("-h") { return .help }
        if arguments.contains("--version") { return .version }
        if arguments.contains("--list") {
            guard arguments.count == 1 else {
                throw UsageError("--list takes no other arguments.\n\n\(usage)")
            }
            return .list
        }

        var display: String?
        var mic: String?
        var duration: Double?
        var output: String?
        var outputDir: String?
        var audio = AudioMode.system
        var fps = 30
        var scale = 1.0
        var showsCursor = true
        var codec = VideoCodec.h264

        var index = 0
        while index < arguments.count {
            let flag = arguments[index]

            func value() throws -> String {
                index += 1
                guard index < arguments.count else {
                    throw UsageError("\(flag) needs a value.\n\n\(usage)")
                }
                return arguments[index]
            }

            switch flag {
            case "--display": display = try value()
            case "--mic": mic = try value()
            case "--output": output = try value()
            case "--output-dir": outputDir = try value()
            case "--no-cursor": showsCursor = false
            case "--duration":
                let raw = try value()
                guard let parsed = Double(raw), parsed > 0 else {
                    throw UsageError("--duration must be a positive number of seconds, got '\(raw)'")
                }
                duration = parsed
            case "--audio":
                let raw = try value()
                guard let parsed = AudioMode(rawValue: raw) else {
                    throw UsageError("--audio must be one of: system, mic, both, none. Got '\(raw)'")
                }
                audio = parsed
            case "--codec":
                let raw = try value()
                guard let parsed = VideoCodec(rawValue: raw) else {
                    throw UsageError("--codec must be one of: h264, hevc. Got '\(raw)'")
                }
                codec = parsed
            case "--fps":
                let raw = try value()
                guard let parsed = Int(raw), (1...120).contains(parsed) else {
                    throw UsageError("--fps must be between 1 and 120, got '\(raw)'")
                }
                fps = parsed
            case "--scale":
                let raw = try value()
                guard let parsed = Double(raw), parsed > 0, parsed <= 1 else {
                    throw UsageError("--scale must be greater than 0 and at most 1, got '\(raw)'")
                }
                scale = parsed
            default:
                throw UsageError("unknown argument: \(flag)\n\n\(usage)")
            }
            index += 1
        }

        return .record(
            RecordOptions(
                display: display,
                mic: mic,
                duration: duration,
                output: try resolveOutput(output: output, outputDir: outputDir),
                audio: audio,
                fps: fps,
                scale: scale,
                showsCursor: showsCursor,
                codec: codec
            ))
    }

    /// `--output` is what the Python layer uses: it decides naming policy.
    /// `--output-dir` exists so the binary is usable by hand, and generates a
    /// timestamped name.
    private static func resolveOutput(output: String?, outputDir: String?) throws -> URL {
        if output != nil, outputDir != nil {
            throw UsageError("--output and --output-dir are mutually exclusive")
        }
        if let output { return URL(fileURLWithPath: (output as NSString).expandingTildeInPath) }

        guard let outputDir else {
            throw UsageError("one of --output or --output-dir is required.\n\n\(usage)")
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd-HHmmss"
        let directory = URL(fileURLWithPath: (outputDir as NSString).expandingTildeInPath)
        return directory.appendingPathComponent("cinta-\(formatter.string(from: Date())).mov")
    }
}

let usage = """
    cintarec - screen recorder backing `cinta record`

    Usage:
      cintarec --output FILE | --output-dir DIR [options]
      cintarec --list          Print capturable displays, windows and apps as JSON
      cintarec --version
      cintarec --help

    Recording options:
      --display INDEX|id:N Screen to record (default: the main display).
                           INDEX is the 1-based position from --list; id:N is the
                           display id. Indices shift when monitors are plugged in,
                           ids do not. Spelled differently because they collide.
      --mic INDEX|id:UID   Microphone to record (default: the system default).
                           Only meaningful with --audio mic or --audio both.
      --duration SECONDS   Stop after this long (default: until SIGINT).
      --audio MODE         system (default), mic, both, or none. `both` writes two
                           separate audio tracks; mixing is left to ffmpeg.
      --fps N              Frames per second, 1-120 (default: 30).
      --scale F            Scale the output down, 0 < F <= 1 (default: 1).
      --no-cursor          Do not draw the mouse pointer.
      --codec h264|hevc    Video codec (default: h264, for QuickTime).

    On completion a JSON report is written to stdout. Logs go to stderr.
    Arguments are parsed by hand so the binary has no SPM dependencies
    (DESIGN.md 4.2).
    """
