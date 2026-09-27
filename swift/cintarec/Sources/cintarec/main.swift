import Foundation

// Keep in sync with src/cinta/__init__.py (tests/unit/test_contract.py checks).
let cintarecVersion = "0.1.1"

let command: Command
do {
    command = try Options.parse(Array(CommandLine.arguments.dropFirst()))
} catch let error as UsageError {
    fail(.invalidArguments, error.message)
} catch {
    fail(.invalidArguments, "\(error)")
}

switch command {
case .help:
    print(usage)
case .version:
    print(cintarecVersion)
case .list:
    Permissions.preflightScreenCapture()
    await Shareable.dump()
case .record(let options):
    Permissions.preflightScreenCapture()
    await Recorder.run(options)
}
