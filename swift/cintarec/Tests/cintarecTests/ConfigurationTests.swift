import CoreMedia
import Testing

@testable import cintarec

private let retina = DisplayInfo(
    index: 1, id: 1, name: "Built-in", width: 1512, height: 982, scale: 2,
    pixelWidth: 3024, pixelHeight: 1964, isMain: true)

private func options(_ change: (inout RecordOptions) -> Void = { _ in }) -> RecordOptions {
    var options = RecordOptions(output: URL(fileURLWithPath: "/tmp/a.mov"))
    change(&options)
    return options
}

@Test func sizedInPixelsNotPoints() {
    let configuration = Recorder.makeConfiguration(options: options(), display: retina)
    #expect(configuration.width == 3024)
    #expect(configuration.height == 1964)
}

@Test func scaledDimensionsStayEven() {
    // 3024 * 0.33 = 997.92 and 1964 * 0.33 = 648.12: H.264 needs both even.
    let configuration = Recorder.makeConfiguration(
        options: options { $0.scale = 0.33 }, display: retina)
    #expect(configuration.width == 998)
    #expect(configuration.height == 648)
}

@Test(arguments: [(0.4, 0), (1.0, 0), (2.6, 2), (3.4, 2), (3.6, 4)])
func even(value: Double, expected: Int) {
    #expect(Recorder.even(value) == expected)
}

@Test func frameRateAndCursor() {
    let configuration = Recorder.makeConfiguration(
        options: options {
            $0.fps = 60
            $0.showsCursor = false
        }, display: retina)
    #expect(configuration.minimumFrameInterval == CMTime(value: 1, timescale: 60))
    #expect(!configuration.showsCursor)
}

@Test(arguments: [(AudioMode.system, true), (.both, true), (.mic, false), (.none, false)])
func systemAudioOnlyWhenAsked(mode: AudioMode, captures: Bool) {
    let configuration = Recorder.makeConfiguration(
        options: options { $0.audio = mode }, display: retina)
    #expect(configuration.capturesAudio == captures)
    #expect(configuration.excludesCurrentProcessAudio)
}
