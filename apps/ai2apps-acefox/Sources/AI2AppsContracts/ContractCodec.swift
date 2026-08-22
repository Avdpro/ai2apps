import Darwin
import Foundation

public enum ContractCodec {
    public static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        // Python's ``datetime.isoformat`` emits fractional seconds while the
        // exact strings accepted by Foundation's built-in ``.iso8601``
        // strategy have varied across supported macOS releases. Decode both
        // forms explicitly so macOS 13/14 can read a freshly-written Local
        // run descriptor during first launch.
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)

            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [
                .withInternetDateTime,
                .withFractionalSeconds,
            ]
            if let date = fractional.date(from: value) {
                return date
            }

            let wholeSeconds = ISO8601DateFormatter()
            wholeSeconds.formatOptions = [.withInternetDateTime]
            if let date = wholeSeconds.date(from: value) {
                return date
            }

            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Expected an ISO-8601 timestamp with optional fractional seconds"
            )
        }
        return decoder
    }

    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return encoder
    }

    public static func load<T: ValidatedContract>(_ type: T.Type, from url: URL) throws -> T {
        let value = try decoder().decode(type, from: Data(contentsOf: url))
        try value.validate()
        return value
    }

    public static func save<T: ValidatedContract>(_ value: T, to url: URL, mode: mode_t = 0o600) throws {
        try value.validate()
        let directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = try encoder().encode(value)
        try data.write(to: url, options: [.atomic])
        guard chmod(url.path, mode) == 0 else {
            throw ContractError.invalidField(field: "file_mode", reason: String(cString: strerror(errno)))
        }
    }
}
