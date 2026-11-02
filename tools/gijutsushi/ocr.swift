// Usage: swift ocr.swift <image.png> ...  → JSON lines: {"file":..., "w":W, "h":H, "lines":[{"t":text,"x":..,"y":..,"w":..,"h":..,"c":conf}]}
import Foundation
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("{\"file\":\"\(path)\",\"error\":\"load\"}"); continue }
    let req = VNRecognizeTextRequest()
    req.revision = 3
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["ja-JP"]
    req.usesLanguageCorrection = true
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    var lines: [[String: Any]] = []
    for o in ((req.results as? [VNRecognizedTextObservation]) ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox  // normalized, origin bottom-left
        lines.append(["t": c.string, "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height, "c": c.confidence])
    }
    let obj: [String: Any] = ["file": path, "w": cg.width, "h": cg.height, "lines": lines]
    let d = try! JSONSerialization.data(withJSONObject: obj, options: [])
    print(String(data: d, encoding: .utf8)!)
}
