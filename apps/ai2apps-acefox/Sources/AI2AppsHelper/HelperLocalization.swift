import AI2AppsContracts
import Foundation

@MainActor
enum HelperLocalization {
    static var settingsURL: URL?
    static var translations: [String: (String, String)] = [:]

    static func text(_ chinese: String, _ english: String) -> String {
        translations[chinese] = (chinese, english)
        translations[english] = (chinese, english)
        return NativeUILanguage.resolve(settingsURL: settingsURL) == "zh" ? chinese : english
    }

    static func refresh(_ text: String) -> String {
        guard let pair = translations[text] else { return text }
        return NativeUILanguage.resolve(settingsURL: settingsURL) == "zh" ? pair.0 : pair.1
    }
}

@MainActor
func L(_ chinese: String, _ english: String) -> String {
    HelperLocalization.text(chinese, english)
}
