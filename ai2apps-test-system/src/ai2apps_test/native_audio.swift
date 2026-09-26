import AppKit
import AVFoundation
import CoreMedia
import ScreenCaptureKit

// No microphone input, screen output, global mix, or URL/network access.
private func writeJSON(_ value: [String: Any], _ url: URL) throws {
    try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .prettyPrinted])
        .write(to: url, options: .atomic)
}

final class AudioSink: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    let queue = DispatchQueue(label: "ai2apps.test.audio")
    let url: URL
    var file: AVAudioFile?
    var frames: Int64 = 0
    var failure: String?
    init(url: URL) { self.url = url }
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        queue.async { self.failure = "capture-stream-stopped" }
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .audio, sample.isValid, CMSampleBufferDataIsReady(sample),
              let description = sample.formatDescription else { return }
        let format = AVAudioFormat(cmAudioFormatDescription: description)
        var required = 0
        CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample,
            bufferListSizeNeededOut: &required, bufferListOut: nil, bufferListSize: 0,
            blockBufferAllocator: nil, blockBufferMemoryAllocator: nil, flags: 0,
            blockBufferOut: nil)
        guard required > 0 else { return }
        let memory = UnsafeMutableRawPointer.allocate(byteCount: required, alignment: 16)
        defer { memory.deallocate() }
        let list = memory.bindMemory(to: AudioBufferList.self, capacity: 1)
        var block: CMBlockBuffer?
        let status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample,
            bufferListSizeNeededOut: nil, bufferListOut: list, bufferListSize: required,
            blockBufferAllocator: nil, blockBufferMemoryAllocator: nil,
            flags: kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment,
            blockBufferOut: &block)
        guard status == noErr,
              let pcm = AVAudioPCMBuffer(pcmFormat: format, bufferListNoCopy: list) else {
            failure = "audio-buffer-conversion-failed"; return
        }
        do {
            if file == nil { file = try AVAudioFile(forWriting: url, settings: format.settings) }
            try file?.write(from: pcm)
            frames += Int64(pcm.frameLength)
        } catch { failure = "audio-file-write-failed" }
        withExtendedLifetime(block) {}
    }
}

@main struct Capture {
    static func main() async {
        let args = CommandLine.arguments
        if args.count == 2 && args[1] == "permission" {
            let granted = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
            print(granted ? "granted" : "permission-required")
            exit(granted ? 0 : 2)
        }
        guard args.count == 6, let seconds = Double(args[5]), seconds > 0, seconds <= 180 else { exit(2) }
        let target = URL(fileURLWithPath: args[1]).resolvingSymlinksInPath()
        let directory = URL(fileURLWithPath: args[2])
        let stateURL = URL(fileURLWithPath: args[3])
        let caseID = args[4]
        let manifestURL = directory.appendingPathComponent("capture.json")
        var manifest: [String: Any] = ["caseId": caseID, "targetPath": target.path,
            "bundleId": "com.ai2apps.desktop.test.shell", "scope": "application-only",
            "microphone": false, "screenSaved": false, "status": "starting"]
        do {
            guard CGPreflightScreenCaptureAccess() else { throw NSError(domain: "screen-audio-permission-required", code: 1) }
            guard target.path.contains("/AI2Apps-test.app/Contents/Applications/"),
                  Bundle(url: target)?.bundleIdentifier == "com.ai2apps.desktop.test.shell" else {
                throw NSError(domain: "invalid-test-shell", code: 1)
            }
            let matches = NSRunningApplication.runningApplications(withBundleIdentifier: "com.ai2apps.desktop.test.shell")
                .filter { !$0.isTerminated && $0.bundleURL?.resolvingSymlinksInPath() == target }
            guard matches.count == 1, let app = matches.first else { throw NSError(domain: "test-shell-not-unique-or-not-running", code: 1) }
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
            guard let captureApp = content.applications.first(where: { $0.processID == app.processIdentifier }),
                  let display = content.displays.first else { throw NSError(domain: "test-shell-not-capturable", code: 1) }
            let filter = SCContentFilter(display: display, including: [captureApp], exceptingWindows: [])
            let config = SCStreamConfiguration()
            config.capturesAudio = true
            config.excludesCurrentProcessAudio = true
            config.sampleRate = 16000
            config.channelCount = 1
            config.width = 2; config.height = 2
            config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
            let sink = AudioSink(url: directory.appendingPathComponent("output.wav"))
            let stream = SCStream(filter: filter, configuration: config, delegate: sink)
            try stream.addStreamOutput(sink, type: .audio, sampleHandlerQueue: sink.queue)
            try await stream.startCapture()
            manifest["status"] = "recording"
            manifest["targetPid"] = app.processIdentifier
            manifest["startedAt"] = ISO8601DateFormatter().string(from: Date())
            try writeJSON(manifest, manifestURL)
            let deadline = Date().addingTimeInterval(seconds)
            var reason = "duration-limit"
            while Date() < deadline {
                if FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop").path) { reason = "requested"; break }
                if app.isTerminated { reason = "target-exited"; break }
                if sink.queue.sync(execute: { sink.failure != nil }) { reason = "stream-error"; break }
                guard let data = try? Data(contentsOf: stateURL),
                      let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { reason = "run-state-unavailable"; break }
                if ["cancelled", "cancelling", "completed"].contains(state["status"] as? String ?? "") {
                    reason = "run-ended"; break
                }
                if (state["results"] as? [String: Any])?[caseID] != nil { reason = "case-ended"; break }
                try await Task.sleep(nanoseconds: 200_000_000)
            }
            try await stream.stopCapture()
            sink.queue.sync {
                sink.file = nil
                manifest["frames"] = sink.frames
                manifest["error"] = sink.failure
            }
            manifest["status"] = reason == "requested" && sink.frames > 0 && sink.failure == nil ? "captured" : "incomplete"
            manifest["stopReason"] = reason
            manifest["completedAt"] = ISO8601DateFormatter().string(from: Date())
            try writeJSON(manifest, manifestURL)
        } catch {
            manifest["status"] = "blocked"
            manifest["error"] = (error as NSError).domain
            try? writeJSON(manifest, manifestURL)
            exit(2)
        }
    }
}
