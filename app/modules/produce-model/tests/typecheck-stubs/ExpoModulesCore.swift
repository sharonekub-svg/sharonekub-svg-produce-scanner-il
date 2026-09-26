// Type-check stub: signatures copied from expo-modules-core 57 (ios/Core, ios/Api/Factories).
// Bodies are placeholders; only used to compile-check ProduceModelModule.swift on Linux.
@_exported import Foundation
public protocol AnyArgument {}
extension Int: AnyArgument {}
extension Double: AnyArgument {}
extension String: AnyArgument {}
extension Bool: AnyArgument {}
extension Array: AnyArgument {}
public protocol AnyDefinition {}
public struct ModuleDefinition { public init(definitions: [AnyDefinition]) {} }
@resultBuilder public struct ModuleDefinitionBuilder {
  public static func buildBlock(_ definitions: AnyDefinition...) -> ModuleDefinition { ModuleDefinition(definitions: definitions) }
}
public final class AppContext {}
public protocol AnyModule: AnyObject, AnyArgument {
  init(appContext: AppContext)
  @ModuleDefinitionBuilder func definition() -> ModuleDefinition
}
open class BaseModule { public required init(appContext: AppContext) {} }
public typealias Module = AnyModule & BaseModule
public struct Promise: AnyArgument, Sendable {
  public func resolve(_ value: Any? = nil) {}
  public func reject(_ error: Error) {}
  public func reject(_ code: String, _ description: String) {}
}
struct Def: AnyDefinition {}
public func Name(_ name: String) -> AnyDefinition { Def() }
public func Function<R>(_ name: String, @_implicitSelfCapture _ closure: @escaping () throws -> R) -> AnyDefinition { Def() }
public func Function<R, A0: AnyArgument, each A: AnyArgument>(_ name: String, @_implicitSelfCapture _ closure: @escaping (A0, repeat each A) throws -> R) -> AnyDefinition { Def() }
public func AsyncFunction<R>(_ name: String, @_implicitSelfCapture _ closure: @escaping () throws -> R) -> AnyDefinition { Def() }
public func AsyncFunction<R, A0: AnyArgument, each A: AnyArgument>(_ name: String, @_implicitSelfCapture _ closure: @escaping (A0, repeat each A) throws -> R) -> AnyDefinition { Def() }
