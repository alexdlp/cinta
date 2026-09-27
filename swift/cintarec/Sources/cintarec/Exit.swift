import Foundation

/// Exit codes are part of the contract with the Python layer (DESIGN.md 4.5).
/// core/recorder.py maps these to errors with useful messages; it never parses
/// free-form text.
enum ExitCode: Int32 {
    case ok = 0
    case noScreenPermission = 10
    case noMicPermission = 11
    case targetNotFound = 12
    case writeFailure = 13
    case invalidArguments = 20
}

/// stdout is data, stderr is logs. Never mix them.
func log(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func fail(_ code: ExitCode, _ message: String) -> Never {
    log("error: " + message)
    exit(code.rawValue)
}

/// Separate from emitJSON so tests can check the contract without capturing stdout.
func encodeJSON<T: Encodable>(_ value: T, oneLine: Bool = false) throws -> Data {
    let encoder = JSONEncoder()
    encoder.outputFormatting =
        oneLine ? [.sortedKeys, .withoutEscapingSlashes]
        : [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    return try encoder.encode(value)
}

/// An event mid-run: a single line, so a reader can act on it as it arrives
/// instead of waiting for the process to exit.
func emitEvent<T: Encodable>(_ value: T) {
    guard var data = try? encodeJSON(value, oneLine: true) else { return }
    data.append(0x0A)
    FileHandle.standardOutput.write(data)
}

func emitJSON<T: Encodable>(_ value: T) {
    do {
        var data = try encodeJSON(value)
        data.append(0x0A)
        FileHandle.standardOutput.write(data)
    } catch {
        fail(.writeFailure, "could not serialize output: \(error.localizedDescription)")
    }
}
