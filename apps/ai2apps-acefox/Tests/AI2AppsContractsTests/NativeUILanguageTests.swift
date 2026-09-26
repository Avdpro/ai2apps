import Foundation
import XCTest
@testable import AI2AppsContracts

final class NativeUILanguageTests: XCTestCase {
    func testSystemPrimaryLanguage() {
        for language in ["zh", "zh-Hans-CN", "zh-Hant-TW", "zh_CN"] {
            XCTAssertEqual(NativeUILanguage.resolve(settingsURL: nil, preferredLanguages: [language]), "zh")
        }
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: nil, preferredLanguages: ["en-US", "zh"]), "en")
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: nil, preferredLanguages: ["ja"]), "en")
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: nil, preferredLanguages: []), "en")
    }

    func testSavedChoiceAndReset() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: url) }
        try Data(#"{"ui":{"language":"en"}}"#.utf8).write(to: url)
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: url, preferredLanguages: ["zh"]), "en")
        try Data(#"{"ui":{"language":"zh"}}"#.utf8).write(to: url)
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: url, preferredLanguages: ["en"]), "zh")
        try Data("invalid".utf8).write(to: url)
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: url, preferredLanguages: ["zh"]), "zh")
        try FileManager.default.removeItem(at: url)
        XCTAssertEqual(NativeUILanguage.resolve(settingsURL: url, preferredLanguages: ["zh"]), "zh")
    }
}
