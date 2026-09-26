import Foundation

public enum NativeUILanguage {
    public static func resolve(
        settingsURL: URL?,
        preferredLanguages: [String] = Locale.preferredLanguages
    ) -> String {
        if let settingsURL,
           let data = try? Data(contentsOf: settingsURL),
           let settings = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let ui = settings["ui"] as? [String: Any],
           let language = ui["language"] as? String,
           ["en", "zh"].contains(language) {
            return language
        }
        let primary = (preferredLanguages.first ?? "en")
            .replacingOccurrences(of: "_", with: "-").lowercased()
        return primary == "zh" || primary.hasPrefix("zh-") ? "zh" : "en"
    }
}
