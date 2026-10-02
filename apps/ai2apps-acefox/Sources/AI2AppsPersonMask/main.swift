import AVFoundation
import CoreImage
import Foundation
import Vision

enum PersonMaskError: Error, CustomStringConvertible {
    case usage
    case message(String)

    var description: String {
        switch self {
        case .usage:
            return "usage: ai2apps-person-mask --input <video> --output <mask.mp4>"
        case .message(let value):
            return value
        }
    }
}

func argument(_ name: String) throws -> String {
    guard let index = CommandLine.arguments.firstIndex(of: name),
          index + 1 < CommandLine.arguments.count else {
        throw PersonMaskError.usage
    }
    return CommandLine.arguments[index + 1]
}

func renderPersonMask(input: URL, output: URL) throws {
    let asset = AVURLAsset(url: input)
    guard let track = asset.tracks(withMediaType: .video).first else {
        throw PersonMaskError.message("The source has no video track")
    }
    // Preserve encoded pixel coordinates. Composer and Package masks are
    // aligned to decoded source frames; display rotation is handled later.
    let sourceSize = track.naturalSize
    let width = max(2, Int(abs(sourceSize.width)).roundedUpToEven)
    let height = max(2, Int(abs(sourceSize.height)).roundedUpToEven)

    let reader = try AVAssetReader(asset: asset)
    let readerOutput = AVAssetReaderTrackOutput(
        track: track,
        outputSettings: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
    )
    readerOutput.alwaysCopiesSampleData = false
    guard reader.canAdd(readerOutput) else {
        throw PersonMaskError.message("Cannot decode the source video")
    }
    reader.add(readerOutput)

    try? FileManager.default.removeItem(at: output)
    let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
    let writerInput = AVAssetWriterInput(
        mediaType: .video,
        outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 2_000_000,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            ],
        ]
    )
    writerInput.expectsMediaDataInRealTime = false
    let adaptor = AVAssetWriterInputPixelBufferAdaptor(
        assetWriterInput: writerInput,
        sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: width,
            kCVPixelBufferHeightKey as String: height,
        ]
    )
    guard writer.canAdd(writerInput) else {
        throw PersonMaskError.message("Cannot encode the person mask")
    }
    writer.add(writerInput)
    guard reader.startReading(), writer.startWriting() else {
        throw PersonMaskError.message(reader.error?.localizedDescription ?? writer.error?.localizedDescription ?? "Cannot start video processing")
    }
    writer.startSession(atSourceTime: .zero)

    let request = VNGeneratePersonSegmentationRequest()
    request.qualityLevel = .balanced
    request.outputPixelFormat = kCVPixelFormatType_OneComponent8
    let context = CIContext(options: [.cacheIntermediates: false])
    var frameCount = 0

    while let sample = readerOutput.copyNextSampleBuffer() {
        try autoreleasepool {
            guard let imageBuffer = CMSampleBufferGetImageBuffer(sample) else { return }
            let handler = VNImageRequestHandler(cvPixelBuffer: imageBuffer, options: [:])
            try handler.perform([request])
            guard let observation = request.results?.first else {
                throw PersonMaskError.message("Apple Vision did not return a person mask")
            }
            guard let pool = adaptor.pixelBufferPool else {
                throw PersonMaskError.message("Mask encoder pixel buffer pool is unavailable")
            }
            var destination: CVPixelBuffer?
            guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &destination) == kCVReturnSuccess,
                  let destination else {
                throw PersonMaskError.message("Cannot allocate a mask frame")
            }
            let mask = CIImage(cvPixelBuffer: observation.pixelBuffer)
            let scale = CGAffineTransform(
                scaleX: CGFloat(width) / mask.extent.width,
                y: CGFloat(height) / mask.extent.height
            )
            let grayscale = mask.transformed(by: scale).applyingFilter(
                "CIFalseColor",
                parameters: [
                    "inputColor0": CIColor(red: 0, green: 0, blue: 0),
                    "inputColor1": CIColor(red: 1, green: 1, blue: 1),
                ]
            )
            context.render(
                grayscale,
                to: destination,
                bounds: CGRect(x: 0, y: 0, width: width, height: height),
                colorSpace: CGColorSpaceCreateDeviceRGB()
            )
            while !writerInput.isReadyForMoreMediaData {
                if writer.status == .failed {
                    throw PersonMaskError.message(writer.error?.localizedDescription ?? "Mask encoding failed")
                }
                Thread.sleep(forTimeInterval: 0.002)
            }
            let timestamp = CMSampleBufferGetPresentationTimeStamp(sample)
            guard adaptor.append(destination, withPresentationTime: timestamp) else {
                throw PersonMaskError.message(writer.error?.localizedDescription ?? "Cannot append a mask frame")
            }
            frameCount += 1
        }
    }
    guard reader.status == .completed, frameCount > 0 else {
        throw PersonMaskError.message(reader.error?.localizedDescription ?? "No video frames were decoded")
    }
    writerInput.markAsFinished()
    let semaphore = DispatchSemaphore(value: 0)
    writer.finishWriting { semaphore.signal() }
    semaphore.wait()
    guard writer.status == .completed else {
        throw PersonMaskError.message(writer.error?.localizedDescription ?? "Person mask encoding failed")
    }
}

extension Int {
    var roundedUpToEven: Int { isMultiple(of: 2) ? self : self + 1 }
}

do {
    try renderPersonMask(
        input: URL(fileURLWithPath: try argument("--input")),
        output: URL(fileURLWithPath: try argument("--output"))
    )
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(64)
}
