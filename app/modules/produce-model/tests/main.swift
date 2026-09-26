// Parity test for ProduceCore.swift against Python fixtures (scripts/gen_swift_fixtures.py).
// Built and run on Linux by scripts/test_swift_core.sh; exits non-zero on any mismatch.
import Foundation

struct Case: Decodable {
  struct Q: Decodable { let reason: String?; let mean_luma: Double; let laplacian_var: Double; let clipped_frac: Double }
  let name: String; let width: Int; let height: Int; let quality: Q
}
struct Input: Decodable { let size: Int; let resize_ratio: Double; let mean: [Double]; let std: [Double] }
struct Index: Decodable { let input: Input; let cases: [Case] }

let dir = URL(fileURLWithPath: CommandLine.arguments[1])
let index = try JSONDecoder().decode(Index.self, from: Data(contentsOf: dir.appendingPathComponent("index.json")))
var failures = 0
for c in index.cases {
  let raw = try Data(contentsOf: dir.appendingPathComponent("\(c.name).rgb"))
  let img = PixelBuffer(width: c.width, height: c.height, channels: 3, data: [UInt8](raw))
  let t0 = Date()
  let tensor = modelTensor(img, size: index.input.size, resizeRatio: index.input.resize_ratio, mean: index.input.mean, std: index.input.std)
  let ms = Date().timeIntervalSince(t0) * 1000
  let refData = try Data(contentsOf: dir.appendingPathComponent("\(c.name).tensor.f32"))
  let ref: [Float] = refData.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
  var maxDiff: Float = 0, sumDiff: Float = 0
  for i in 0..<ref.count { let d = abs(ref[i] - tensor[i]); maxDiff = max(maxDiff, d); sumDiff += d }
  let meanDiff = sumDiff / Float(ref.count)
  let q = assessQuality(img)
  let lumaOK = abs(q.meanLuma - c.quality.mean_luma) < 0.05
  let lapOK = abs(q.laplacianVar - c.quality.laplacian_var) <= max(0.01 * c.quality.laplacian_var, 0.5)
  let clipOK = abs(q.clippedFrac - c.quality.clipped_frac) < 1e-3
  let reasonOK = q.reason == c.quality.reason
  // One 8-bit step after normalisation is 1/255/0.225 ≈ 0.0175; allow rounding-level differences only.
  let tensorOK = tensor.count == ref.count && maxDiff <= 0.036 && meanDiff < 0.001
  let ok = tensorOK && lumaOK && lapOK && clipOK && reasonOK
  if !ok { failures += 1 }
  print(String(format: "%@ %-28@ tensor max %.4f mean %.6f (%.0f ms) | luma %.2f/%.2f lapvar %.1f/%.1f clip %.4f/%.4f reason %@/%@",
               ok ? "PASS" : "FAIL", c.name, maxDiff, meanDiff, ms, q.meanLuma, c.quality.mean_luma,
               q.laplacianVar, c.quality.laplacian_var, q.clippedFrac, c.quality.clipped_frac,
               q.reason ?? "nil", c.quality.reason ?? "nil"))
}
print(failures == 0 ? "ALL \(index.cases.count) CASES PASS" : "\(failures) FAILURE(S)")
exit(failures == 0 ? 0 : 1)
