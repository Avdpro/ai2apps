import AppKit
import ApplicationServices
import Foundation

private let bundleID = "com.ai2apps.desktop.test.shell"

private struct Request: Decodable {
    let operation: String
    let email: String?
    let password: String?
}

private func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else {
        return nil
    }
    return value
}

private func stringAttribute(_ element: AXUIElement, _ name: String) -> String {
    attribute(element, name) as? String ?? ""
}

private func elements(_ root: AXUIElement) -> [AXUIElement] {
    var result = [root]
    var pending = [root]
    var visited = 0
    while !pending.isEmpty && visited < 1000 {
        let current = pending.removeFirst()
        visited += 1
        if let children = attribute(current, kAXChildrenAttribute) as? [AXUIElement] {
            result.append(contentsOf: children)
            pending.append(contentsOf: children)
        }
    }
    return result
}

private func label(_ element: AXUIElement) -> String {
    [kAXTitleAttribute, kAXDescriptionAttribute, kAXPlaceholderValueAttribute]
        .map { stringAttribute(element, $0) }
        .first { !$0.isEmpty } ?? ""
}

private func loginFields(_ nodes: [AXUIElement]) -> (AXUIElement?, AXUIElement?) {
    var email: AXUIElement?
    var password: AXUIElement?
    for node in nodes where stringAttribute(node, kAXRoleAttribute) == kAXTextFieldRole {
        let nodeLabel = label(node)
        let subrole = stringAttribute(node, kAXSubroleAttribute)
        if nodeLabel.hasPrefix("Email") {
            email = node
        }
        if subrole == "AXSecureTextField" || nodeLabel.hasPrefix("Password") {
            password = node
        }
    }
    return (email, password)
}

private func button(_ nodes: [AXUIElement], named name: String) -> AXUIElement? {
    let matches = nodes.filter {
        stringAttribute($0, kAXRoleAttribute) == kAXButtonRole && label($0) == name
    }
    return matches.max { left, right in
        func positionY(_ element: AXUIElement) -> CGFloat {
            guard let raw = attribute(element, kAXPositionAttribute),
                  CFGetTypeID(raw) == AXValueGetTypeID() else { return 0 }
            var position = CGPoint.zero
            AXValueGetValue(raw as! AXValue, .cgPoint, &position)
            return position.y
        }
        func width(_ element: AXUIElement) -> CGFloat {
            guard let raw = attribute(element, kAXSizeAttribute),
                  CFGetTypeID(raw) == AXValueGetTypeID() else { return 0 }
            var size = CGSize.zero
            AXValueGetValue(raw as! AXValue, .cgSize, &size)
            return size.width
        }
        let leftY = positionY(left)
        let rightY = positionY(right)
        if leftY != rightY {
            return leftY < rightY
        }
        return width(left) < width(right)
    }
}

private func snapshot(_ appElement: AXUIElement) -> [AXUIElement] {
    elements(appElement)
}

private func submitLoginWithReturn(_ passwordField: AXUIElement, pid: pid_t) -> Bool {
    guard AXUIElementSetAttributeValue(
        passwordField,
        kAXFocusedAttribute as CFString,
        kCFBooleanTrue
    ) == .success else {
        return false
    }
    guard let source = CGEventSource(stateID: .combinedSessionState),
          let keyDown = CGEvent(
              keyboardEventSource: source,
              virtualKey: CGKeyCode(36),
              keyDown: true
          ),
          let keyUp = CGEvent(
              keyboardEventSource: source,
              virtualKey: CGKeyCode(36),
              keyDown: false
          ) else {
        return false
    }
    keyDown.postToPid(pid)
    keyUp.postToPid(pid)
    return true
}

private func loginSubmissionStarted(_ appElement: AXUIElement) -> Bool {
    let deadline = Date().addingTimeInterval(2)
    while Date() < deadline {
        let nodes = snapshot(appElement)
        let fields = loginFields(nodes)
        if fields.0 == nil || fields.1 == nil || button(nodes, named: "Confirm Core binding") != nil {
            return true
        }
        if let submit = button(nodes, named: "Sign in"),
           let enabled = attribute(submit, kAXEnabledAttribute) as? Bool,
           !enabled {
            return true
        }
        Thread.sleep(forTimeInterval: 0.1)
    }
    return false
}

private func finish(_ value: String, code: Int32 = 0) -> Never {
    print(value)
    exit(code)
}

guard let data = FileHandle.standardInput.readDataToEndOfFile() as Data?,
      let request = try? JSONDecoder().decode(Request.self, from: data) else {
    finish("invalid-request", code: 2)
}

if request.operation == "quit" {
    let bundleIDs = [
        "com.ai2apps.desktop.test.shell",
        "com.ai2apps.desktop.test",
        "com.ai2apps.desktop.test.helper",
    ]
    let targets = bundleIDs.flatMap {
        NSRunningApplication.runningApplications(withBundleIdentifier: $0)
    }
    for target in targets where !target.isTerminated {
        target.terminate()
    }
    let deadline = Date().addingTimeInterval(10)
    while targets.contains(where: { !$0.isTerminated }) && Date() < deadline {
        Thread.sleep(forTimeInterval: 0.1)
    }
    for target in targets where !target.isTerminated {
        target.forceTerminate()
    }
    finish("quit")
}

if request.operation == "quit-shell" {
    let targets = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
    for target in targets where !target.isTerminated {
        target.terminate()
    }
    let deadline = Date().addingTimeInterval(10)
    while targets.contains(where: { !$0.isTerminated }) && Date() < deadline {
        Thread.sleep(forTimeInterval: 0.1)
    }
    for target in targets where !target.isTerminated {
        target.forceTerminate()
    }
    finish("quit-shell")
}

guard AXIsProcessTrusted() else { finish("accessibility-permission", code: 2) }

let apps = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
guard apps.count == 1, let app = apps.first else { finish("test-shell-count", code: 2) }
app.activate()
let appElement = AXUIElementCreateApplication(app.processIdentifier)

var nodes = snapshot(appElement)
var fields = loginFields(nodes)
if request.operation == "probe" {
    finish("email=\(fields.0 != nil),password=\(fields.1 != nil)")
}

guard request.operation == "login", let emailValue = request.email,
      let passwordValue = request.password else { finish("invalid-request", code: 2) }

let fieldDeadline = Date().addingTimeInterval(20)
while (fields.0 == nil || fields.1 == nil) && Date() < fieldDeadline {
    Thread.sleep(forTimeInterval: 0.2)
    nodes = snapshot(appElement)
    fields = loginFields(nodes)
}
guard let emailField = fields.0, let passwordField = fields.1 else {
    finish("fields-unavailable", code: 2)
}
guard AXUIElementSetAttributeValue(emailField, kAXValueAttribute as CFString, emailValue as CFString) == .success,
      AXUIElementSetAttributeValue(passwordField, kAXValueAttribute as CFString, passwordValue as CFString) == .success else {
    finish("fields-not-settable", code: 2)
}

let returnSubmitted = submitLoginWithReturn(passwordField, pid: app.processIdentifier)
if !returnSubmitted || !loginSubmissionStarted(appElement) {
    nodes = snapshot(appElement)
    guard let submit = button(nodes, named: "Sign in") else {
        finish("submit-unavailable", code: 2)
    }
    guard AXUIElementPerformAction(submit, kAXPressAction as CFString) == .success else {
        finish("submit-failed", code: 2)
    }
}

var bindingSubmitted = false
let loginDeadline = Date().addingTimeInterval(60)
Thread.sleep(forTimeInterval: 0.5)
while Date() < loginDeadline {
    nodes = snapshot(appElement)
    fields = loginFields(nodes)
    if let bind = button(nodes, named: "Confirm Core binding"), !bindingSubmitted {
        guard AXUIElementPerformAction(bind, kAXPressAction as CFString) == .success else {
            finish("binding-submit-failed", code: 2)
        }
        bindingSubmitted = true
        Thread.sleep(forTimeInterval: 0.5)
    } else if fields.0 == nil && fields.1 == nil && button(nodes, named: "Confirm Core binding") == nil {
        finish("authenticated")
    }
    Thread.sleep(forTimeInterval: 0.2)
}
finish("timeout", code: 2)
