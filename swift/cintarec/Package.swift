// swift-tools-version:5.9
import PackageDescription

// No external dependencies on purpose: Homebrew builds run in a sandbox with no
// network, and an SPM dependency would have to be declared as a formula resource.
let package = Package(
    name: "cintarec",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "cintarec",
            path: "Sources/cintarec",
            linkerSettings: [
                // A bare executable has no bundle, so it has nowhere to put
                // NSMicrophoneUsageDescription - and without that key, asking for
                // microphone access crashes the process instead of prompting.
                // The plist is embedded into the __TEXT segment instead.
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Info.plist",
                ])
            ]
        ),
        // swift-testing rather than XCTest: it ships with the Command Line Tools,
        // while XCTest needs a full Xcode install.
        .testTarget(
            name: "cintarecTests",
            dependencies: ["cintarec"],
            path: "Tests/cintarecTests"
        ),
    ]
)
