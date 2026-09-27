// Platform-independent core of on-device inference: resampling, model-input tensor and the
// image-quality gate. Foundation only (no UIKit / CoreML / Expo), so it is compiled and tested on
// Linux against the Python reference (server/app.py Engine.preprocess, ml/inference/quality.py):
//   scripts/test_swift_core.sh
// Numerics deliberately mirror Pillow: antialiased BILINEAR resample with 8-bit rounding after
// each pass, ITU-R 601 integer luma ("L" mode) and Python's round-half-to-even.
import Foundation

public struct PixelBuffer {
  public let width: Int
  public let height: Int
  public let channels: Int   // 1 (luma) or 3 (RGB)
  public var data: [UInt8]   // row-major, interleaved

  public init(width: Int, height: Int, channels: Int, data: [UInt8]) {
    precondition(data.count == width * height * channels, "buffer size mismatch")
    self.width = width; self.height = height; self.channels = channels; self.data = data
  }
}

/// Python's round(): ties to even.
@inline(__always) func pyRound(_ x: Double) -> Int { Int(x.rounded(.toNearestOrEven)) }

@inline(__always) private func clip8(_ v: Double) -> UInt8 {
  // Pillow rounds half up on the 8-bit store (fixed-point + 0.5).
  let r = (v + 0.5).rounded(.down)
  return UInt8(max(0, min(255, r)))
}

/// Pillow-compatible separable resample with a triangle (bilinear) filter whose support scales
/// with the downscale factor (i.e. antialiased), horizontal pass first, 8-bit between passes.
public func resampleBilinear(_ src: PixelBuffer, to outW: Int, _ outH: Int) -> PixelBuffer {
  func coefficients(inSize: Int, outSize: Int) -> [(start: Int, weights: [Double])] {
    let scale = Double(inSize) / Double(outSize)
    let filterScale = max(scale, 1.0)
    let support = 1.0 * filterScale
    var result: [(Int, [Double])] = []
    result.reserveCapacity(outSize)
    for x in 0..<outSize {
      let center = (Double(x) + 0.5) * scale
      var xmin = Int((center - support + 0.5).rounded(.towardZero)); if xmin < 0 { xmin = 0 }
      var xmax = Int((center + support + 0.5).rounded(.towardZero)); if xmax > inSize { xmax = inSize }
      var w = [Double](); w.reserveCapacity(max(0, xmax - xmin))
      var total = 0.0
      for i in xmin..<max(xmin, xmax) {
        let t = abs((Double(i) - center + 0.5) / filterScale)
        let v = t < 1.0 ? 1.0 - t : 0.0
        w.append(v); total += v
      }
      if total != 0 { for k in 0..<w.count { w[k] /= total } }
      result.append((xmin, w))
    }
    return result
  }

  let c = src.channels
  var cur = src
  if outW != cur.width {
    let coeffs = coefficients(inSize: cur.width, outSize: outW)
    var out = [UInt8](repeating: 0, count: outW * cur.height * c)
    cur.data.withUnsafeBufferPointer { s in
      for y in 0..<cur.height {
        let row = y * cur.width * c
        for x in 0..<outW {
          let (start, w) = coeffs[x]
          for ch in 0..<c {
            var acc = 0.0
            for k in 0..<w.count { acc += Double(s[row + (start + k) * c + ch]) * w[k] }
            out[(y * outW + x) * c + ch] = clip8(acc)
          }
        }
      }
    }
    cur = PixelBuffer(width: outW, height: cur.height, channels: c, data: out)
  }
  if outH != cur.height {
    let coeffs = coefficients(inSize: cur.height, outSize: outH)
    var out = [UInt8](repeating: 0, count: cur.width * outH * c)
    let w0 = cur.width
    cur.data.withUnsafeBufferPointer { s in
      for y in 0..<outH {
        let (start, w) = coeffs[y]
        for x in 0..<w0 {
          for ch in 0..<c {
            var acc = 0.0
            for k in 0..<w.count { acc += Double(s[((start + k) * w0 + x) * c + ch]) * w[k] }
            out[(y * w0 + x) * c + ch] = clip8(acc)
          }
        }
      }
    }
    cur = PixelBuffer(width: w0, height: outH, channels: c, data: out)
  }
  return cur
}

/// Model input, identical to server/app.py Engine.preprocess:
/// short side -> Int(size*ratio), centre crop size×size, (x/255 - mean)/std, NCHW Float32.
public func modelTensor(_ rgb: PixelBuffer, size: Int, resizeRatio: Double, mean: [Double], std: [Double]) -> [Float] {
  precondition(rgb.channels == 3)
  let target = Double(Int(Double(size) * resizeRatio))
  let s = target / Double(min(rgb.width, rgb.height))
  let rw = max(1, pyRound(Double(rgb.width) * s)), rh = max(1, pyRound(Double(rgb.height) * s))
  let r = resampleBilinear(rgb, to: rw, rh)
  let left = (rw - size) / 2, top = (rh - size) / 2
  var out = [Float](repeating: 0, count: 3 * size * size)
  for y in 0..<size {
    for x in 0..<size {
      let i = ((top + y) * rw + (left + x)) * 3
      for ch in 0..<3 {
        let v = (Double(r.data[i + ch]) / 255.0 - mean[ch]) / std[ch]
        out[ch * size * size + y * size + x] = Float(v)
      }
    }
  }
  return out
}

/// Pillow "L" conversion: (R*19595 + G*38470 + B*7471 + 0x8000) >> 16.
public func luma(_ rgb: PixelBuffer) -> PixelBuffer {
  precondition(rgb.channels == 3)
  var out = [UInt8](repeating: 0, count: rgb.width * rgb.height)
  rgb.data.withUnsafeBufferPointer { s in
    for i in 0..<(rgb.width * rgb.height) {
      let v = (Int(s[i * 3]) * 19595 + Int(s[i * 3 + 1]) * 38470 + Int(s[i * 3 + 2]) * 7471 + 0x8000) >> 16
      out[i] = UInt8(min(255, v))
    }
  }
  return PixelBuffer(width: rgb.width, height: rgb.height, channels: 1, data: out)
}

public struct QualityConfig {
  public var minMeanLuma = 40.0, maxMeanLuma = 235.0, minLaplacianVar = 30.0, maxClippedFrac = 0.35
  public var analysisSize = 256
  public init() {}
}

public struct QualityResult {
  public let reason: String?   // too_dark | too_bright | overexposed | blurry | nil
  public let meanLuma: Double
  public let laplacianVar: Double
  public let clippedFrac: Double
  public var ok: Bool { reason == nil }
}

/// Port of ml/inference/quality.py::assess (same order of checks, same thresholds).
public func assessQuality(_ rgb: PixelBuffer, _ cfg: QualityConfig = QualityConfig()) -> QualityResult {
  var g = luma(rgb)
  let scale = Double(cfg.analysisSize) / Double(max(g.width, g.height))
  if scale < 1 {
    g = resampleBilinear(g, to: max(1, pyRound(Double(g.width) * scale)), max(1, pyRound(Double(g.height) * scale)))
  }
  let n = Double(g.data.count)
  var sum = 0.0, clipped = 0
  for v in g.data { sum += Double(v); if v <= 3 || v >= 252 { clipped += 1 } }
  let mean = sum / n
  var lsum = 0.0, lsq = 0.0, cnt = 0.0
  if g.width >= 3 && g.height >= 3 {
    for y in 1..<(g.height - 1) {
      for x in 1..<(g.width - 1) {
        let c = Double(g.data[y * g.width + x])
        let lap = -4 * c + Double(g.data[(y - 1) * g.width + x]) + Double(g.data[(y + 1) * g.width + x])
          + Double(g.data[y * g.width + x - 1]) + Double(g.data[y * g.width + x + 1])
        lsum += lap; lsq += lap * lap; cnt += 1
      }
    }
  }
  let lmean = cnt > 0 ? lsum / cnt : 0
  let lvar = cnt > 0 ? max(0, lsq / cnt - lmean * lmean) : 0
  let clippedFrac = Double(clipped) / n
  var reason: String? = nil
  if mean < cfg.minMeanLuma { reason = "too_dark" }
  else if mean > cfg.maxMeanLuma { reason = "too_bright" }
  else if clippedFrac > cfg.maxClippedFrac { reason = "overexposed" }
  else if lvar < cfg.minLaplacianVar { reason = "blurry" }
  return QualityResult(reason: reason, meanLuma: mean, laplacianVar: lvar, clippedFrac: clippedFrac)
}
