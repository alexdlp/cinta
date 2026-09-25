import AVFoundation

/// Wraps AVAssetWriter. The one rule that matters: video and audio share a
/// single timeline, started by the first video sample. Audio that arrives before
/// that is dropped, or the writer fails.
final class Writer {
    private let writer: AVAssetWriter
    private let videoInput: AVAssetWriterInput
    private let systemAudioInput: AVAssetWriterInput?
    private let micInput: AVAssetWriterInput?
    private let output: URL

    private let lock = NSLock()
    private var sessionStarted = false
    private var firstPTS = CMTime.zero

    init(
        output: URL, width: Int, height: Int, fps: Int, codec: VideoCodec,
        systemAudio: Bool, mic: Bool
    ) {
        self.output = output

        let directory = output.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true)
        } catch {
            fail(.writeFailure, "cannot create \(directory.path): \(error.localizedDescription)")
        }
        if FileManager.default.fileExists(atPath: output.path) {
            fail(.writeFailure, "\(output.path) already exists; refusing to overwrite it")
        }

        // Kept in a local: the nested helpers below must not touch self before
        // every stored property is initialized.
        let assetWriter: AVAssetWriter
        do {
            assetWriter = try AVAssetWriter(outputURL: output, fileType: .mov)
        } catch {
            fail(.writeFailure, "cannot write to \(output.path): \(error.localizedDescription)")
        }
        writer = assetWriter

        // ~0.12 bits per pixel per frame: visually clean for screen content,
        // which is mostly flat colour and text, without absurd file sizes.
        let bitrate = Int(Double(width * height * fps) * 0.12)
        videoInput = AVAssetWriterInput(
            mediaType: .video,
            outputSettings: [
                AVVideoCodecKey: codec == .hevc ? AVVideoCodecType.hevc : AVVideoCodecType.h264,
                AVVideoWidthKey: width,
                AVVideoHeightKey: height,
                AVVideoCompressionPropertiesKey: [
                    AVVideoAverageBitRateKey: bitrate,
                    AVVideoExpectedSourceFrameRateKey: fps,
                    AVVideoMaxKeyFrameIntervalKey: fps * 2,
                ],
                // Stated rather than inferred, and matching the sRGB conversion
                // asked of ScreenCaptureKit.
                AVVideoColorPropertiesKey: [
                    AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                    AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                    AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
                ],
            ])
        videoInput.expectsMediaDataInRealTime = true
        guard assetWriter.canAdd(videoInput) else {
            fail(.writeFailure, "the writer rejected the video input")
        }
        assetWriter.add(videoInput)

        // Two separate tracks rather than one mix: mixing in Swift would mean an
        // AVAudioEngine with resampling, and ffmpeg (already a dependency) does it
        // better downstream - while keeping the tracks separable if wanted.
        func makeAudioInput(channels: Int, bitrate: Int, label: String) -> AVAssetWriterInput {
            let input = AVAssetWriterInput(
                mediaType: .audio,
                outputSettings: [
                    AVFormatIDKey: kAudioFormatMPEG4AAC,
                    AVSampleRateKey: 48000,
                    AVNumberOfChannelsKey: channels,
                    AVEncoderBitRateKey: bitrate,
                ])
            input.expectsMediaDataInRealTime = true
            guard assetWriter.canAdd(input) else {
                fail(.writeFailure, "the writer rejected the \(label) input")
            }
            assetWriter.add(input)
            return input
        }

        systemAudioInput = systemAudio ? makeAudioInput(channels: 2, bitrate: 192_000, label: "system audio") : nil
        micInput = mic ? makeAudioInput(channels: 1, bitrate: 96_000, label: "microphone") : nil

        guard assetWriter.startWriting() else {
            fail(
                .writeFailure,
                assetWriter.error?.localizedDescription ?? "the writer would not start")
        }
    }

    func appendVideo(_ sampleBuffer: CMSampleBuffer) {
        lock.lock()
        defer { lock.unlock() }

        let pts = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        if !sessionStarted {
            writer.startSession(atSourceTime: pts)
            firstPTS = pts
            sessionStarted = true
        }

        guard videoInput.isReadyForMoreMediaData else { return }
        videoInput.append(sampleBuffer)
    }

    func appendSystemAudio(_ sampleBuffer: CMSampleBuffer) {
        append(sampleBuffer, to: systemAudioInput)
    }

    func appendMic(_ sampleBuffer: CMSampleBuffer) {
        append(sampleBuffer, to: micInput)
    }

    private func append(_ sampleBuffer: CMSampleBuffer, to input: AVAssetWriterInput?) {
        lock.lock()
        defer { lock.unlock() }

        // No video sample yet: there is no timeline to attach this to.
        guard sessionStarted, let input, input.isReadyForMoreMediaData else { return }
        input.append(sampleBuffer)
    }

    /// Must run before the process exits. A .mov without its moov atom is an
    /// unplayable file, which is what a bare Ctrl-C would leave behind.
    func finish() -> (started: Bool, duration: Double, bytes: Int) {
        lock.lock()
        // The end of the recording is now, on the host clock - not the timestamp
        // of the last video frame. ScreenCaptureKit stops delivering frames while
        // the screen is static, so a still display would otherwise report a
        // recording far shorter than it was. SCStream timestamps are host-clock
        // based, so the two are directly comparable.
        let end = CMClockGetTime(CMClockGetHostTimeClock())

        // Stopped before the first frame ever arrived. There is no session to
        // end and nothing to write, and finishWriting() would fail with an
        // opaque error. Throw the empty file away and say what happened.
        guard sessionStarted else {
            lock.unlock()
            writer.cancelWriting()
            try? FileManager.default.removeItem(at: output)
            return (started: false, duration: 0, bytes: 0)
        }

        let duration = max(0, CMTimeGetSeconds(end - firstPTS))

        videoInput.markAsFinished()
        systemAudioInput?.markAsFinished()
        micInput?.markAsFinished()
        writer.endSession(atSourceTime: end)
        lock.unlock()

        let semaphore = DispatchSemaphore(value: 0)
        writer.finishWriting { semaphore.signal() }
        semaphore.wait()

        if writer.status == .failed {
            fail(.writeFailure, writer.error?.localizedDescription ?? "the writer failed")
        }

        let attributes = try? FileManager.default.attributesOfItem(atPath: output.path)
        return (started: true, duration: duration, bytes: (attributes?[.size] as? Int) ?? 0)
    }
}
