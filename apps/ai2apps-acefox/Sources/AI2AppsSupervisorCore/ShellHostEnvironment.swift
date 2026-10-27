/// The App Shell also owns native background Browser Tasks. Both interactive
/// Launcher startup and Helper cold-host startup must retain rendering while
/// covered; ordinary Firefox processes do not receive this host contract.
public enum ShellHostEnvironment {
    public static func required(token: String, showShell: Bool = false) -> [String: String] {
        ["AI2APPS_APP_SHELL": "1",
         "AI2APPS_DISABLE_REMOTE_SERVER": "1",
         "AI2APPS_REMOTE_AGENT_TOKEN": token,
         "AI2APPS_BROWSER_ROLE": "shell",
         "AI2APPS_BACKGROUND_HOST": "1",
         "AI2APPS_SHOW_SHELL": showShell ? "1" : "0"]
    }
}
