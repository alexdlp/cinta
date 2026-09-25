import Foundation

/// Exit codes are part of the contract with the Python layer (DESIGN.md 5.5).
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

func emitJSON<T: Encodable>(_ value: T) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    do {
        var data = try encoder.encode(value)
        data.append(0x0A)
        FileHandle.standardOutput.write(data)
    } catch {
        fail(.writeFailure, "could not serialize output: \(error.localizedDescription)")
    }
}
