// Type-check stub mirroring the UIKit + CoreGraphics APIs used by ProduceModelModule.swift.
@_exported import Foundation
open class CGImage { public var width: Int { 0 }; public var height: Int { 0 } }
public final class CGColorSpace {
  public static let sRGB = "kCGColorSpaceSRGB"
  public init?(name: String) {}
}
public enum CGImageAlphaInfo: UInt32 { case none = 0, premultipliedLast, premultipliedFirst, last, first, noneSkipLast, noneSkipFirst }
public enum CGInterpolationQuality: Int32 { case `default`, none, low, medium, high }
open class CGContext {
  public init?(data: UnsafeMutableRawPointer?, width: Int, height: Int, bitsPerComponent: Int, bytesPerRow: Int,
               space: CGColorSpace, bitmapInfo: UInt32) {}
  public var interpolationQuality: CGInterpolationQuality = .default
  public func draw(_ image: CGImage, in rect: CGRect) {}
}
open class UIImage {
  public init?(data: Data) {}
  open var size: CGSize { .zero }
  open var cgImage: CGImage? { nil }
  open func draw(at point: CGPoint) {}
}
open class UIGraphicsImageRendererFormat {
  public enum Range: Int { case unspecified, automatic, extended, standard }
  open class func `default`() -> UIGraphicsImageRendererFormat { UIGraphicsImageRendererFormat() }
  open var scale: CGFloat = 1
  open var preferredRange: Range = .automatic
}
open class UIGraphicsImageRendererContext {}
open class UIGraphicsImageRenderer {
  public init(size: CGSize, format: UIGraphicsImageRendererFormat) {}
  open func image(actions: (UIGraphicsImageRendererContext) -> Void) -> UIImage { UIImage(data: Data())! }
}
