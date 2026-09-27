import Foundation
import Testing

@testable import cintarec

private func record(_ arguments: [String]) throws -> RecordOptions {
    guard case .record(let options) = try Options.parse(arguments) else {
        Issue.record("expected a recording command for \(arguments)")
        throw UsageError("not a recording")
    }
    return options
}

private func message(_ arguments: [String]) -> String? {
    do {
        _ = try Options.parse(arguments)
        return nil
    } catch let error as UsageError {
        return error.message
    } catch {
        return "\(error)"
    }
}

@Test func defaults() throws {
    let options = try record(["--output", "/tmp/a.mov"])
    #expect(options.output.path == "/tmp/a.mov")
    #expect(options.display == nil)
    #expect(options.mic == nil)
    #expect(options.duration == nil)
    #expect(options.audio == .system)
    #expect(options.fps == 30)
    #expect(options.scale == 1)
    #expect(options.showsCursor)
    #expect(options.codec == .h264)
}

@Test func everyFlag() throws {
    let options = try record([
        "--output", "/tmp/a.mov", "--display", "id:7", "--mic", "2", "--duration", "2.5",
        "--audio", "both", "--fps", "60", "--scale", "0.5", "--no-cursor", "--codec", "hevc",
    ])
    #expect(options.display == "id:7")
    #expect(options.mic == "2")
    #expect(options.duration == 2.5)
    #expect(options.audio == .both)
    #expect(options.fps == 60)
    #expect(options.scale == 0.5)
    #expect(!options.showsCursor)
    #expect(options.codec == .hevc)
}

@Test func tildeInOutputIsExpanded() throws {
    let options = try record(["--output", "~/a.mov"])
    #expect(options.output.path == NSHomeDirectory() + "/a.mov")
}

@Test func outputDirGeneratesATimestampedName() throws {
    let options = try record(["--output-dir", "/tmp"])
    #expect(options.output.deletingLastPathComponent().path == "/tmp")
    #expect(options.output.lastPathComponent.range(
        of: #"^cinta-\d{4}-\d{2}-\d{2}-\d{6}\.mov$"#, options: .regularExpression) != nil)
}

@Test func helpVersionAndList() throws {
    guard case .help = try Options.parse(["--output", "/tmp/a.mov", "--help"]) else {
        Issue.record("--help wins over everything else")
        return
    }
    guard case .version = try Options.parse(["--version"]) else {
        Issue.record("--version")
        return
    }
    guard case .list = try Options.parse(["--list"]) else {
        Issue.record("--list")
        return
    }
}

@Test(arguments: [
    ([String](), "no arguments given"),
    (["--list", "--fps", "30"], "--list takes no other arguments"),
    (["--output", "/tmp/a.mov", "--output-dir", "/tmp"], "mutually exclusive"),
    (["--fps", "30"], "one of --output or --output-dir is required"),
    (["--output"], "--output needs a value"),
    (["--output", "/tmp/a.mov", "--bogus"], "unknown argument: --bogus"),
    (["--output", "/tmp/a.mov", "--fps", "0"], "--fps must be between 1 and 120"),
    (["--output", "/tmp/a.mov", "--fps", "121"], "--fps must be between 1 and 120"),
    (["--output", "/tmp/a.mov", "--fps", "thirty"], "--fps must be between 1 and 120"),
    (["--output", "/tmp/a.mov", "--scale", "0"], "--scale must be greater than 0"),
    (["--output", "/tmp/a.mov", "--scale", "1.5"], "--scale must be greater than 0"),
    (["--output", "/tmp/a.mov", "--duration", "-1"], "--duration must be a positive"),
    (["--output", "/tmp/a.mov", "--duration", "0"], "--duration must be a positive"),
    (["--output", "/tmp/a.mov", "--audio", "stereo"], "--audio must be one of"),
    (["--output", "/tmp/a.mov", "--codec", "av1"], "--codec must be one of"),
])
func rejected(arguments: [String], expected: String) {
    let error = message(arguments)
    #expect(error?.contains(expected) == true, "\(arguments) gave: \(error ?? "no error")")
}
