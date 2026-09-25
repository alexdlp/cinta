import Foundation

// Keep in sync with src/cinta/__init__.py.
let cintarecVersion = "0.1.0"

switch Options.parse(Array(CommandLine.arguments.dropFirst())) {
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
