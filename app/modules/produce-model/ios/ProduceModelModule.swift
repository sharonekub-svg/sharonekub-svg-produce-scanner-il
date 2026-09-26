// Expo module: on-device inference with Core ML.
//
// All numerics (resize, crop, normalisation, quality gate) live in ProduceCore.swift, which is
// compiled and parity-tested on Linux against the Python server (scripts/test_swift_core.sh:
// max tensor difference = one 8-bit rounding step; identical quality decisions). This file only
// does the iOS-specific parts: decode + orientation, Core ML model loading and prediction.
// API usage checked against ExpoModulesCore 57 sources (variadic AsyncFunction with trailing
// Promise; Promise.reject(code, description); Function returning Bool).
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
          guard let rgb = Self.decodeRGB(uri) else {
            promise.reject("E_IMAGE", "cannot decode image")
            return
          }
          let q = assessQuality(rgb)
          let tensor = modelTensor(rgb, size: size, resizeRatio: resizeRatio, mean: mean, std: std)
          let input = try MLMultiArray(shape: [1, 3, NSNumber(value: size), NSNumber(value: size)], dataType: .float32)
          tensor.withUnsafeBufferPointer { src in
            input.dataPointer.bindMemory(to: Float32.self, capacity: tensor.count)
              .update(from: src.baseAddress!, count: tensor.count)
          }
          let out = try self.loadModel().prediction(from: MLDictionaryFeatureProvider(dictionary: ["image": input]))
          var logits: [String: [Double]] = [:]
          for head in ["produce", "ripeness", "freshness", "visual_spoilage"] {
            guard let arr = out.featureValue(for: head)?.multiArrayValue else {
              promise.reject("E_MODEL_OUTPUT", "missing output \(head)")
              return
            }
            logits[head] = (0..<arr.count).map { arr[$0].doubleValue }
          }
          let quality: [String: Any] = [
            "ok": q.ok, "reason": q.reason ?? NSNull(), "mean_luma": q.meanLuma,
            "laplacian_var": q.laplacianVar, "clipped_frac": q.clippedFrac,
          ]
          promise.resolve(["logits": logits, "quality": quality])
        } catch {
          promise.reject("E_INFERENCE", error.localizedDescription)
        }
      }
    }
  }

  /// The raw .mlpackage shipped by the podspec's resource bundle (scripts/sync_model_to_app.sh).
  private static func packageURL() -> URL? {
    guard let bundleURL = Bundle(for: ProduceModelModule.self).url(forResource: "ProduceModelAssets", withExtension: "bundle"),
          let assets = Bundle(url: bundleURL) else { return nil }
    return assets.url(forResource: "ProduceScanner", withExtension: "mlpackage")
  }

  /// Compile once on first use and cache the .mlmodelc in Application Support. The cache key is
  /// derived from the package manifest so a new model shipped in an app update is recompiled.
  private func loadModel() throws -> MLModel {
    if let m = model { return m }
    guard let pkg = Self.packageURL() else {
      throw NSError(domain: "ProduceModel", code: 1, userInfo: [NSLocalizedDescriptionKey: "model package missing"])
    }
    let manifest = (try? Data(contentsOf: pkg.appendingPathComponent("Manifest.json"))) ?? Data()
    let key = manifest.reduce(UInt64(1469598103934665603)) { ($0 ^ UInt64($1)) &* 1099511628211 }  // FNV-1a (stable across launches)
    let support = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
    let cached = support.appendingPathComponent("ProduceScanner-\(String(key, radix: 16)).mlmodelc")
    if !FileManager.default.fileExists(atPath: cached.path) {
      let compiled = try MLModel.compileModel(at: pkg)
      try? FileManager.default.removeItem(at: cached)
      try FileManager.default.moveItem(at: compiled, to: cached)
    }
    let cfg = MLModelConfiguration()
    cfg.computeUnits = .all  // Neural Engine where the graph allows it
    let m = try MLModel(contentsOf: cached, configuration: cfg)
    model = m
    return m
  }

  /// Decode (file:// URI from expo-camera), apply EXIF orientation (Python: ImageOps.exif_transpose),
  /// and return full-resolution sRGB pixels. No resampling here — ProduceCore does it, like Pillow.
  private static func decodeRGB(_ uri: String) -> PixelBuffer? {
    guard let url = URL(string: uri), let data = try? Data(contentsOf: url), let img = UIImage(data: data) else { return nil }
    let fmt = UIGraphicsImageRendererFormat.default()
    fmt.scale = 1
    fmt.preferredRange = .standard  // 8-bit sRGB
    guard let cg = UIGraphicsImageRenderer(size: img.size, format: fmt).image(actions: { _ in img.draw(at: .zero) }).cgImage,
          let srgb = CGColorSpace(name: CGColorSpace.sRGB) else { return nil }
    let w = cg.width, h = cg.height
    var rgba = [UInt8](repeating: 0, count: w * h * 4)
    let drawn: Bool = rgba.withUnsafeMutableBytes { buf in
      guard let ctx = CGContext(data: buf.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                                space: srgb, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return false }
      ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
      return true
    }
    guard drawn else { return nil }
    var rgb = [UInt8](repeating: 0, count: w * h * 3)
    for i in 0..<(w * h) {
      rgb[i * 3] = rgba[i * 4]; rgb[i * 3 + 1] = rgba[i * 4 + 1]; rgb[i * 3 + 2] = rgba[i * 4 + 2]
    }
    return PixelBuffer(width: w, height: h, channels: 3, data: rgb)
  }
}
