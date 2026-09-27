import AVFoundation
import ScreenCaptureKit

final class Recorder: NSObject, SCStreamOutput, SCStreamDelegate {
    private let options: RecordOptions
    private let writer: Writer
    private let sampleQueue = DispatchQueue(label: "ai.cinta.cintarec.samples")
    private let micQueue = DispatchQueue(label: "ai.cinta.cintarec.mic")
    private let stopped = DispatchSemaphore(value: 0)

    private let stateLock = NSLock()
    private var stopReason = "unknown"
    private var streamError: String?
    private var signalSource: DispatchSourceSignal?
    private var stdinSource: DispatchSourceRead?

    private init(options: RecordOptions, writer: Writer) {
        self.options = options
        self.writer = writer
    }

    static func run(_ options: RecordOptions) async {
        let content: SCShareableContent
        do {
            content = try await SCShareableContent.excludingDesktopWindows(
                false, onScreenWindowsOnly: true)
        } catch {
            fail(.noScreenPermission, "could not query shareable content: \(error.localizedDescription)")
        }

        let (display, info) = selectDisplay(options.display, from: content)
        let configuration = makeConfiguration(options: options, display: info)

        // Resolve the microphone before creating any file: a bad --mic should
        // fail immediately, not halfway through a recording.
        var microphone: AVCaptureDevice?
        if options.audio.capturesMic {
            Permissions.preflightMicrophone()
            microphone = Microphones.device(matching: options.mic)
        }

        let writer = Writer(
            output: options.output,
            width: configuration.width,
            height: configuration.height,
            fps: options.fps,
            codec: options.codec,
            systemAudio: options.audio.capturesSystem,
            mic: options.audio.capturesMic)

        let recorder = Recorder(options: options, writer: writer)
        writer.onStart = {
            let now = ISO8601DateFormatter()
            now.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            emitEvent(StartedEvent(path: options.output.path, startedAt: now.string(from: Date())))
            log("first frame written")
        }
        let filter = SCContentFilter(
            display: display, excludingApplications: [], exceptingWindows: [])
        let stream = SCStream(filter: filter, configuration: configuration, delegate: recorder)

        do {
            try stream.addStreamOutput(
                recorder, type: .screen, sampleHandlerQueue: recorder.sampleQueue)
            if options.audio.capturesSystem {
                try stream.addStreamOutput(
                    recorder, type: .audio, sampleHandlerQueue: recorder.sampleQueue)
            }
            try await stream.startCapture()
        } catch {
            fail(.writeFailure, "could not start the capture: \(error.localizedDescription)")
        }

        var micCapture: MicrophoneCapture?
        if let microphone {
            let capture = MicrophoneCapture(
                device: microphone, queue: recorder.micQueue, onSample: writer.appendMic)
            capture.start()
            micCapture = capture
        }

        let audioSummary = [
            options.audio.capturesSystem ? "system audio" : nil,
            microphone.map { "mic: \($0.localizedName)" },
        ].compactMap { $0 }.joined(separator: " + ")
        log(
            "recording \(info.name) (\(configuration.width)x\(configuration.height))"
                + (audioSummary.isEmpty ? " without audio" : " with \(audioSummary)")
                + " to \(options.output.path)")
        recorder.installSignalHandler()
        recorder.installStdinHandler()
        recorder.waitForStop()

        try? await stream.stopCapture()
        micCapture?.stop()
        let result = writer.finish()

        guard result.started else {
            fail(
                .writeFailure,
                "the recording was stopped before the first frame arrived, so nothing was written."
            )
        }

        if let error = recorder.streamError {
            fail(.writeFailure, "the capture stream failed: \(error)")
        }

        emitJSON(
            Report(
                path: options.output.path,
                durationSeconds: result.duration,
                fps: options.fps,
                width: configuration.width,
                height: configuration.height,
                codec: options.codec.rawValue,
                display: info,
                audioTracks: [
                    options.audio.capturesSystem ? AudioTrack(kind: "system", channels: 2) : nil,
                    microphone.map { AudioTrack(kind: "mic", channels: 1, device: $0.localizedName) },
                ].compactMap { $0 },
                bytes: result.bytes,
                stoppedBy: recorder.stopReason
            ))
    }

    // MARK: - Target selection

    /// `--display 2` is the 1-based index from --list; `--display id:2` is the raw
    /// display id. They are spelled differently on purpose: on a three-monitor
    /// setup index 1 and id 1 routinely refer to different screens.
    private static func selectDisplay(
        _ spec: String?, from content: SCShareableContent
    ) -> (SCDisplay, DisplayInfo) {
        let infos = Shareable.displays(from: content)
        guard !infos.isEmpty else {
            fail(.targetNotFound, "no capturable displays found")
        }

        func display(withID id: UInt32) -> SCDisplay? {
            content.displays.first { $0.displayID == id }
        }

        guard let spec else {
            let main = infos.first { $0.isMain } ?? infos[0]
            return (display(withID: main.id)!, main)
        }

        let available = infos
            .map { "  --display \($0.index)   (id:\($0.id))  \($0.name)" }
            .joined(separator: "\n")

        if spec.hasPrefix("id:") {
            guard let id = UInt32(spec.dropFirst(3)), let info = infos.first(where: { $0.id == id })
            else {
                fail(.targetNotFound, "no display with \(spec). Available:\n\(available)")
            }
            return (display(withID: info.id)!, info)
        }

        guard let index = Int(spec) else {
            fail(.invalidArguments, "--display takes an index or id:N, got '\(spec)'. Available:\n\(available)")
        }
        guard let info = infos.first(where: { $0.index == index }) else {
            fail(.targetNotFound, "there is no display \(index). Available:\n\(available)")
        }
        return (display(withID: info.id)!, info)
    }

    static func makeConfiguration(options: RecordOptions, display: DisplayInfo)
        -> SCStreamConfiguration
    {
        let configuration = SCStreamConfiguration()

        // SCDisplay reports points; the buffers have to be sized in pixels or a
        // Retina screen records at half resolution. H.264 wants even dimensions.
        configuration.width = even(Double(display.pixelWidth) * options.scale)
        configuration.height = even(Double(display.pixelHeight) * options.scale)

        // ScreenCaptureKit delivers frames in the display's own colour space. The
        // built-in XDR panel is Display P3, so without this the file ends up
        // holding P3 pixel values while the container declares Rec.709, and every
        // player reads those numbers as the wrong colours. Converting at capture
        // time makes the Rec.709 tag written by Writer truthful.
        configuration.colorSpaceName = CGColorSpace.sRGB

        configuration.minimumFrameInterval = CMTime(
            value: 1, timescale: CMTimeScale(options.fps))
        configuration.queueDepth = 6
        configuration.showsCursor = options.showsCursor

        configuration.capturesAudio = options.audio.capturesSystem
        configuration.sampleRate = 48000
        configuration.channelCount = 2
        // Without this, cintarec's own output would be captured back into the mix.
        configuration.excludesCurrentProcessAudio = true

        return configuration
    }

    static func even(_ value: Double) -> Int {
        let rounded = Int(value.rounded())
        return rounded % 2 == 0 ? rounded : rounded - 1
    }

    // MARK: - Lifecycle

    /// SIGINT must not kill the process outright: finishWriting() has to run or
    /// the .mov is left without its moov atom and is unplayable.
    private func installSignalHandler() {
        signal(SIGINT, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: SIGINT, queue: .global())
        source.setEventHandler { [weak self] in
            log("stopping (interrupted)")
            self?.stop(reason: "signal")
        }
        source.resume()
        signalSource = source
    }

    /// Enter is the gentle way to stop: Ctrl-C works, but asking someone to
    /// interrupt a process to end a recording normally is the wrong shape.
    ///
    /// Only when stdin is a terminal. Piped or redirected input reaches EOF
    /// immediately, and treating that as "stop" would end every scripted
    /// recording the instant it began.
    private func installStdinHandler() {
        guard isatty(STDIN_FILENO) == 1 else { return }

        let source = DispatchSource.makeReadSource(fileDescriptor: STDIN_FILENO, queue: .global())
        source.setEventHandler { [weak self] in
            var buffer = [UInt8](repeating: 0, count: 256)
            let count = read(STDIN_FILENO, &buffer, buffer.count)
            self?.stop(reason: count <= 0 ? "eof" : "keypress")
        }
        source.resume()
        stdinSource = source
    }

    private func waitForStop() {
        guard let duration = options.duration else {
            stopped.wait()
            return
        }
        if stopped.wait(timeout: .now() + duration) == .timedOut {
            stop(reason: "duration")
        }
    }

    private func stop(reason: String) {
        stateLock.lock()
        if stopReason == "unknown" { stopReason = reason }
        stateLock.unlock()
        stopped.signal()
    }

    // MARK: - SCStreamOutput

    func stream(
        _ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of type: SCStreamOutputType
    ) {
        guard CMSampleBufferIsValid(sampleBuffer) else { return }

        switch type {
        case .screen:
            guard isComplete(sampleBuffer) else { return }
            writer.appendVideo(sampleBuffer)
        case .audio:
            writer.appendSystemAudio(sampleBuffer)
        default:
            break
        }
    }

    /// ScreenCaptureKit keeps delivering buffers when nothing on screen changed.
    /// Appending those inflates the duration and produces black frames.
    private func isComplete(_ sampleBuffer: CMSampleBuffer) -> Bool {
        guard
            let attachments = CMSampleBufferGetSampleAttachmentsArray(
                sampleBuffer, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
            let raw = attachments.first?[.status] as? Int,
            let status = SCFrameStatus(rawValue: raw)
        else { return false }
        return status == .complete
    }

    // MARK: - SCStreamDelegate

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        stateLock.lock()
        streamError = error.localizedDescription
        stateLock.unlock()
        stop(reason: "error")
    }
}
