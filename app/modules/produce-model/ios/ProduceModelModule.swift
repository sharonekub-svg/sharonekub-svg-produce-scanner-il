// On-device inference with Core ML. Mirrors server/app.py::Engine.preprocess and
// ml/inference/quality.py so on-device results match the Python reference.
// NOTE: written against ExpoModulesCore's Swift API; not compiled in the Linux build
// environment — first macOS build must run `npx expo run:ios` and the parity checklist in
// docs/mobile.md.
import CoreML
import ExpoModulesCore
import UIKit

public final class ProduceModelModule: Module {
  private var model: MLModel?
  private let queue = DispatchQueue(label: "produce-model", qos: .userInitiated)

  public func definition() -> ModuleDefinition {
    Name("ProduceModel")

    Function("isAvailable") { () -> Bool in
      return Self.packageURL() != nil
    }

    AsyncFunction("analyze") { (uri: String, size: Int, resizeRatio: Double, mean: [Double], std: [Double], promise: Promise) in
      self.queue.async {
        do {
          let model = try self.loadModel()
          guard let url = URL(string: uri), let data = try? Data(contentsOf: url), let img = UIImage(data: data),
                let cg = Self.upright(img) else {
            promise.reject("E_IMAGE", "cannot decode image")
            return
          }
          let quality = Self.quality(cg)
          let input = try Self.tensor(cg, size: size, ratio: resizeRatio, mean: mean, std: std)
          let out = try model.prediction(from: MLDictionaryFeatureProvider(dictionary: ["image": input]))
          var logits: [String: [Double]] = [:]
          for head in ["produce", "ripeness", "freshness", "visual_spoilage"] {
            guard let arr = out.featureValue(for: head)?.multiArrayValue else { continue }
            logits[head] = (0..<arr.count).map { arr[$0].doubleValue }
          }
          promise.resolve(["logits": logits, "quality": quality])
        } catch {
          promise.reject("E_INFERENCE", error.localizedDescription)
        }
      }
    }
  }

  private static func packageURL() -> URL? {
    guard let bundleURL = Bundle(for: ProduceModelModule.self).url(forResource: "ProduceModelAssets", withExtension: "bundle"),
          let assets = Bundle(url: bundleURL) else { return nil }
    return assets.url(forResource: "ProduceScanner", withExtension: "mlpackage")
  }

  private func loadModel() throws -> MLModel {
    if let m = model { return m }
    guard let pkg = Self.packageURL() else { throw NSError(domain: "ProduceModel", code: 1) }
    let support = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
    let cached = support.appendingPathComponent("ProduceScanner.mlmodelc")
    if !FileManager.default.fileExists(atPath: cached.path) {
      let compiled = try MLModel.compileModel(at: pkg)
      try? FileManager.default.removeItem(at: cached)
      try FileManager.default.moveItem(at: compiled, to: cached)
    }
    let cfg = MLModelConfiguration()
    cfg.computeUnits = .all  // Neural Engine when the graph allows it
    let m = try MLModel(contentsOf: cached, configuration: cfg)
    model = m
    return m
  }

  /// Bake EXIF orientation into pixels (Python: ImageOps.exif_transpose).
  private static func upright(_ img: UIImage) -> CGImage? {
    let fmt = UIGraphicsImageRendererFormat.default()
    fmt.scale = 1
    return UIGraphicsImageRenderer(size: img.size, format: fmt).image { _ in img.draw(at: .zero) }.cgImage
  }

  private static func rgba(_ cg: CGImage, width: Int, height: Int) -> [UInt8] {
    var buf = [UInt8](repeating: 0, count: width * height * 4)
    let ctx = CGContext(data: &buf, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
                        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.interpolationQuality = .medium
    ctx.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
    return buf
  }

  /// Short side -> size*ratio, centre crop size x size, normalise; NCHW Float32 [1,3,size,size].
  /// The model graph takes normalised input (ONNX-equivalent path).
  private static func tensor(_ cg: CGImage, size: Int, ratio: Double, mean: [Double], std: [Double]) throws -> MLMultiArray {
    let w = Double(cg.width), h = Double(cg.height)
    let s = (Double(size) * ratio).rounded(.down) / min(w, h)
    let rw = max(1, Int((w * s).rounded())), rh = max(1, Int((h * s).rounded()))
    let px = rgba(cg, width: rw, height: rh)
    let left = (rw - size) / 2, top = (rh - size) / 2
    let arr = try MLMultiArray(shape: [1, 3, NSNumber(value: size), NSNumber(value: size)], dataType: .float32)
    let ptr = arr.dataPointer.bindMemory(to: Float32.self, capacity: 3 * size * size)
    for y in 0..<size {
      for x in 0..<size {
        let i = ((top + y) * rw + (left + x)) * 4
        for c in 0..<3 {
          ptr[c * size * size + y * size + x] = Float32((Double(px[i + c]) / 255.0 - mean[c]) / std[c])
        }
      }
    }
    return arr
  }

  /// Port of ml/inference/quality.py (thresholds must stay identical).
  private static func quality(_ cg: CGImage) -> [String: Any] {
    let scale = 256.0 / Double(max(cg.width, cg.height))
    let w = max(3, Int(Double(cg.width) * min(1, scale))), h = max(3, Int(Double(cg.height) * min(1, scale)))
    let px = rgba(cg, width: w, height: h)
    var g = [Double](repeating: 0, count: w * h)
    for i in 0..<(w * h) {  // ITU-R 601 luma, as PIL "L"
      g[i] = 0.299 * Double(px[i * 4]) + 0.587 * Double(px[i * 4 + 1]) + 0.114 * Double(px[i * 4 + 2])
    }
    let mean = g.reduce(0, +) / Double(g.count)
    let clipped = Double(g.filter { $0 <= 3 || $0 >= 252 }.count) / Double(g.count)
    var lap = [Double]()
    lap.reserveCapacity((w - 2) * (h - 2))
    for y in 1..<(h - 1) {
      for x in 1..<(w - 1) {
        let c = g[y * w + x]
        lap.append(-4 * c + g[(y - 1) * w + x] + g[(y + 1) * w + x] + g[y * w + x - 1] + g[y * w + x + 1])
      }
    }
    let lm = lap.reduce(0, +) / Double(lap.count)
    let lv = lap.reduce(0) { $0 + ($1 - lm) * ($1 - lm) } / Double(lap.count)
    var reason: Any = NSNull()
    if mean < 40 { reason = "too_dark" } else if mean > 235 { reason = "too_bright" }
    else if clipped > 0.35 { reason = "overexposed" } else if lv < 60 { reason = "blurry" }
    return ["ok": reason is NSNull, "reason": reason, "mean_luma": mean, "laplacian_var": lv, "clipped_frac": clipped]
  }
}
