import AI2AppsContracts
import Foundation

enum ContractKind: String {
    case instance = "validate-instance"
    case config = "validate-config"
    case run = "validate-run"
    case runtime = "validate-runtime"
}

func validate(kind: ContractKind, path: String) throws {
    let url = URL(fileURLWithPath: path)
    switch kind {
    case .instance:
        _ = try ContractCodec.load(InstanceManifest.self, from: url)
    case .config:
        _ = try ContractCodec.load(LocalConfiguration.self, from: url)
    case .run:
        _ = try ContractCodec.load(LocalRunDescriptor.self, from: url)
    case .runtime:
        _ = try ContractCodec.load(RuntimeManifest.self, from: url)
    }
}

let arguments = CommandLine.arguments
guard arguments.count == 3, let kind = ContractKind(rawValue: arguments[1]) else {
    FileHandle.standardError.write(Data("usage: ai2apps-contract <validate-instance|validate-config|validate-run|validate-runtime> <path>\n".utf8))
    exit(64)
}

do {
    try validate(kind: kind, path: arguments[2])
    print("valid")
} catch {
    FileHandle.standardError.write(Data("invalid: \(error)\n".utf8))
    exit(1)
}
