import Foundation
import Vision
import AppKit

// Reads text from an image using the OCR built into macOS. No third-party
// dependency and no network call -- the alternative was a ~100 MB Tesseract
// install that this project would otherwise never need.
let args = CommandLine.arguments
guard args.count > 1, let image = NSImage(contentsOfFile: args[1]),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot read image\n".data(using: .utf8)!)
    exit(2)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
print(lines.joined(separator: "\n"))
