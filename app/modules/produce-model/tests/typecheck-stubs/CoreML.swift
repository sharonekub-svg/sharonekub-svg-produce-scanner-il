// Type-check stub mirroring the CoreML APIs used by ProduceModelModule.swift.
@_exported import Foundation
public enum MLComputeUnits: Int { case cpuOnly, cpuAndGPU, all, cpuAndNeuralEngine }
public enum MLMultiArrayDataType: Int { case double, float64, float32, float16, int32 }
open class MLModelConfiguration { public init() {}; open var computeUnits: MLComputeUnits = .all }
public protocol MLFeatureProvider { func featureValue(for featureName: String) -> MLFeatureValue? }
open class MLFeatureValue { open var multiArrayValue: MLMultiArray? { nil } }
open class MLMultiArray {
  public init(shape: [NSNumber], dataType: MLMultiArrayDataType) throws {}
  open var dataPointer: UnsafeMutableRawPointer { fatalError() }
  open var count: Int { 0 }
  open subscript(idx: Int) -> NSNumber { NSNumber(value: 0) }
}
open class MLDictionaryFeatureProvider: MLFeatureProvider {
  public init(dictionary: [String: Any]) throws {}
  public func featureValue(for featureName: String) -> MLFeatureValue? { nil }
}
open class MLModel {
  public init(contentsOf url: URL, configuration: MLModelConfiguration) throws {}
  open class func compileModel(at modelURL: URL) throws -> URL { modelURL }
  open func prediction(from input: MLFeatureProvider) throws -> MLFeatureProvider { try MLDictionaryFeatureProvider(dictionary: [:]) }
}
