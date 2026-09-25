import AVFoundation

struct MicrophoneInfo: Encodable {
    let index: Int
    let id: String
    let name: String
    let isDefault: Bool
}

enum Microphones {
    /// `--list` has to enumerate input devices, because unlike system audio the
    /// microphone is a choice: there can be several.
    static func all() -> [MicrophoneInfo] {
        let defaultID = AVCaptureDevice.default(for: .audio)?.uniqueID
        return AVCaptureDevice.DiscoverySession(
            deviceTypes: deviceTypes, mediaType: .audio, position: .unspecified
        )
        .devices
        .enumerated()
        .map { index, device in
            MicrophoneInfo(
                index: index + 1,
                id: device.uniqueID,
                name: device.localizedName,
                isDefault: device.uniqueID == defaultID
            )
        }
    }

    static func device(matching spec: String?) -> AVCaptureDevice {
        let devices = AVCaptureDevice.DiscoverySession(
            deviceTypes: deviceTypes, mediaType: .audio, position: .unspecified
        ).devices

        guard !devices.isEmpty else {
            fail(.targetNotFound, "no microphones found")
        }

        guard let spec else {
            guard let device = AVCaptureDevice.default(for: .audio) ?? devices.first else {
                fail(.targetNotFound, "no default microphone")
            }
            return device
        }

        let available = all()
            .map { "  --mic \($0.index)   (id:\($0.id))  \($0.name)" }
            .joined(separator: "\n")

        if spec.hasPrefix("id:") {
            let id = String(spec.dropFirst(3))
            guard let device = devices.first(where: { $0.uniqueID == id }) else {
                fail(.targetNotFound, "no microphone with \(spec). Available:\n\(available)")
            }
            return device
        }

        guard let index = Int(spec) else {
            fail(.invalidArguments, "--mic takes an index or id:UID, got '\(spec)'. Available:\n\(available)")
        }
        guard index >= 1, index <= devices.count else {
            fail(.targetNotFound, "there is no microphone \(index). Available:\n\(available)")
        }
        return devices[index - 1]
    }

    /// `.microphone` and `.external` only exist from macOS 14. The raw values of
    /// the pre-14 spellings are used directly so the macOS 13 path does not drag
    /// deprecation warnings into every build.
    private static var deviceTypes: [AVCaptureDevice.DeviceType] {
        if #available(macOS 14.0, *) {
            return [.microphone, .external]
        }
        return [
            AVCaptureDevice.DeviceType(rawValue: "AVCaptureDeviceTypeBuiltInMicrophone"),
            AVCaptureDevice.DeviceType(rawValue: "AVCaptureDeviceTypeExternalUnknown"),
        ]
    }
}

/// Captures one microphone into CMSampleBuffers. Forced to mono 16-bit 48 kHz on
/// the capture side so the writer's AAC settings always match the source, whatever
/// the device reports (the built-in MacBook mic advertises 3 channels).
final class MicrophoneCapture: NSObject, AVCaptureAudioDataOutputSampleBufferDelegate {
    private let session = AVCaptureSession()
    private let onSample: (CMSampleBuffer) -> Void

    init(device: AVCaptureDevice, queue: DispatchQueue, onSample: @escaping (CMSampleBuffer) -> Void) {
        self.onSample = onSample
        super.init()

        let input: AVCaptureDeviceInput
        do {
            input = try AVCaptureDeviceInput(device: device)
        } catch {
            fail(.noMicPermission, "cannot open \(device.localizedName): \(error.localizedDescription)")
        }
        guard session.canAddInput(input) else {
            fail(.targetNotFound, "cannot capture from \(device.localizedName)")
        }
        session.addInput(input)

        let output = AVCaptureAudioDataOutput()
        output.audioSettings = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 48000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]
        output.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(output) else {
            fail(.targetNotFound, "cannot add the microphone output")
        }
        session.addOutput(output)
    }

    func start() { session.startRunning() }
    func stop() { session.stopRunning() }

    func captureOutput(
        _ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        onSample(sampleBuffer)
    }
}
