import AppKit
import Foundation
import LocalAuthentication
import Security
import Darwin

private struct CredentialPeer: Sendable {
    let instance: String
    let name: String
    let helperPath: String
    let requirement: String
}

private enum CredentialBrokerError: LocalizedError {
    var errorDescription: String? { message }
    case rejected(String)
    var message: String {
        if case .rejected(let value) = self { return value }
        return "Credential import rejected"
    }
}

/// Only Helpers exchange credentials. Local HTML receives metadata and receipts.
final class CredentialImportBroker: NSObject, @unchecked Sendable {
    private let instance: String
    private let name: String
    private let token: String
    private let port: @Sendable () async -> Int?
    private var listener: Int32 = -1
    private let acceptQueue = DispatchQueue(label: "com.ai2apps.credential-import")
    private let directory: URL
    private let helperPath = Bundle.main.executableURL!.standardizedFileURL.path
    private let lock = NSLock()
    private var consentBusy = false

    init(instance: String, name: String, token: String, port: @escaping @Sendable () async -> Int?) {
        self.instance = instance
        self.name = name
        self.token = token
        self.port = port
        directory = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/AI2Apps/credential-import", isDirectory: true)
        super.init()
    }

    func start() throws {
        let fm = FileManager.default
        try fm.createDirectory(at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        guard Self.canonicalPath(directory.path) == directory.path else {
            throw CredentialBrokerError.rejected("Credential directory must not be a symbolic link")
        }
        let attributes = try fm.attributesOfItem(atPath: directory.path)
        guard (attributes[.ownerAccountID] as? NSNumber)?.uint32Value == geteuid(),
              ((attributes[.posixPermissions] as? NSNumber)?.intValue ?? 0) & 0o077 == 0 else {
            throw CredentialBrokerError.rejected("Credential directory permissions are unsafe")
        }
        let file = directory.appendingPathComponent(instance + ".sock")
        if fm.fileExists(atPath:file.path) {
            let old = try fm.attributesOfItem(atPath:file.path)
            guard old[.type] as? FileAttributeType == .typeSocket,
                  (old[.ownerAccountID] as? NSNumber)?.uint32Value == geteuid() else {
                throw CredentialBrokerError.rejected("Unsafe existing credential socket")
            }
            try fm.removeItem(at:file)
        }
        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { throw CredentialBrokerError.rejected("Cannot create credential socket") }
        do {
            try Self.address(file.path) { address, size in
                guard Darwin.bind(fd,address,size) == 0 else { throw CredentialBrokerError.rejected("Cannot bind credential socket") }
            }
            guard chmod(file.path,0o600) == 0, listen(fd,8) == 0 else { throw CredentialBrokerError.rejected("Cannot protect credential socket") }
            _ = fcntl(fd,F_SETFD,FD_CLOEXEC)
            listener = fd
            acceptQueue.async { [weak self] in
                while self != nil {
                    let connection = accept(fd,nil,nil)
                    if connection < 0 { if errno == EINTR { continue }; return }
                    Self.configure(connection, timeout:180)
                    Task.detached { [weak self] in
                        defer { close(connection) }
                        do {
                            guard let self else { return }
                            let peer = try Self.socketPeer(connection)
                            let request = try Self.readMessage(connection)
                            let response = try await self.servePeer(request, peer:peer, connection:connection)
                            try Self.writeMessage(connection,response)
                        } catch {
                            try? Self.writeMessage(connection,Self.failure(Self.safeMessage(error)))
                        }
                    }
                }
            }
        } catch { close(fd); throw error }
    }

    private static func address<T>(_ path: String, _ action: (UnsafePointer<sockaddr>,socklen_t) throws -> T) throws -> T {
        var value = sockaddr_un()
        value.sun_family = sa_family_t(AF_UNIX)
        value.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
        let bytes = Array(path.utf8) + [0]
        guard bytes.count <= MemoryLayout.size(ofValue:value.sun_path) else { throw CredentialBrokerError.rejected("Credential socket path is too long") }
        withUnsafeMutableBytes(of:&value.sun_path) { buffer in buffer.copyBytes(from:bytes) }
        return try withUnsafePointer(to:&value) { pointer in
            try pointer.withMemoryRebound(to:sockaddr.self,capacity:1) { address in try action(address,socklen_t(MemoryLayout<sockaddr_un>.size)) }
        }
    }
    private static func configure(_ fd: Int32, timeout: Int) {
        _ = fcntl(fd,F_SETFD,FD_CLOEXEC)
        var duration = timeval(tv_sec:timeout,tv_usec:0)
        _ = setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&duration,socklen_t(MemoryLayout<timeval>.size))
        _ = setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&duration,socklen_t(MemoryLayout<timeval>.size))
        var one: Int32 = 1
        _ = setsockopt(fd,SOL_SOCKET,SO_NOSIGPIPE,&one,socklen_t(MemoryLayout<Int32>.size))
    }
    private static func readMessage(_ fd: Int32) throws -> String {
        var bytes = Data(), buffer = [UInt8](repeating:0,count:4096)
        while bytes.count <= 256*1024 {
            let count = Darwin.read(fd,&buffer,buffer.count)
            guard count > 0 else { throw CredentialBrokerError.rejected("Source Helper disconnected or timed out") }
            bytes.append(buffer,count:count)
            if let newline = bytes.firstIndex(of:0x0A) {
                guard let text = String(data:bytes.prefix(upTo:newline),encoding:.utf8) else { break }
                return text
            }
        }
        throw CredentialBrokerError.rejected("Invalid credential message size")
    }
    private static func writeMessage(_ fd: Int32, _ text: String) throws {
        let bytes = Array((text + "\n").utf8)
        guard bytes.count <= 256*1024 else { throw CredentialBrokerError.rejected("Credential message is too large") }
        try bytes.withUnsafeBytes { buffer in
            var offset = 0
            while offset < bytes.count {
                let count = Darwin.write(fd,buffer.baseAddress!.advanced(by:offset),bytes.count-offset)
                guard count > 0 else { throw CredentialBrokerError.rejected("Credential peer disconnected") }
                offset += count
            }
        }
    }

    /// Called only through this instance's authenticated Helper control channel.
    func perform(ticket: String) async throws -> String {
        let target = try await local("context", ["ticket":ticket])
        guard let identity = target["identity"] as? [String:Any],
              let action = target["action"] as? [String:Any] else {
            throw CredentialBrokerError.rejected("Invalid import context")
        }
        let destination: [String:Any] = ["identity":identity,"instance":instance,"name":name,"language":action["language"] as? String ?? "en"]
        if action["action"] as? String == "list" {
            var sources: [[String:Any]] = []
            let files = (try? FileManager.default.contentsOfDirectory(at:directory, includingPropertiesForKeys:nil)) ?? []
            for file in files.sorted(by:{$0.path < $1.path}).prefix(32) where file.lastPathComponent != instance + ".sock" {
                do {
                    let (connection, peer) = try connect(file)
                    defer { close(connection) }
                    let result = try await ask(connection, ["op":"list","destination":destination], timeout: 18)
                    if result["ok"] as? Bool == true, let offer = result["offer"] as? [String:Any] {
                        sources.append(["id":peer.instance,"name":peer.name,"offer_id":offer["offer_id"] ?? "",
                                        "providers":offer["providers"] ?? []])
                    }
                } catch { continue } // Other accounts and stale endpoints are not disclosed.
            }
            return try Self.encode(["sources":sources])
        }
        guard let source = action["source"] as? String,
              source.range(of:"^[a-z0-9][a-z0-9-]{0,63}$",options:.regularExpression) != nil,
              source != instance else { throw CredentialBrokerError.rejected("Choose another running instance") }
        let (connection, peer) = try connect(directory.appendingPathComponent(source + ".sock"))
        defer { close(connection) }
        guard peer.instance == source else { throw CredentialBrokerError.rejected("Source identity mismatch") }
        let response = try await ask(connection, ["op":"export","destination":destination,
            "offer_id":action["offer_id"] ?? "", "selected":action["selected"] ?? [],
            "replace_existing":action["replace_existing"] ?? false,
            "target_versions":target["target_versions"] ?? [:]])
        if response["ok"] as? Bool == false, response["status"] as? String == "cancelled" {
            return try Self.encode(["status":"cancelled","items":[]])
        }
        guard response["ok"] as? Bool == true, let payload = response["payload"] as? [String:Any] else {
            throw CredentialBrokerError.rejected(response["error"] as? String ?? "Source import was rejected")
        }
        // Local revalidates account/boot, selected providers and destination versions before consuming the ticket.
        return try Self.encode(try await local("install", ["ticket":ticket,"payload":payload]))
    }

    private func servePeer(_ text: String, peer: CredentialPeer, connection: Int32) async throws -> String {
        let request = try Self.decode(text)
        guard let destination = request["destination"] as? [String:Any],
              destination["instance"] as? String == peer.instance,
              let targetIdentity = destination["identity"] as? [String:Any] else {
            throw CredentialBrokerError.rejected("Destination identity mismatch")
        }
        let state = try await local("context", [:])
        guard let identity = state["identity"] as? [String:Any],
              Self.sameAccount(identity,targetIdentity), identity["security_id"] as? String != targetIdentity["security_id"] as? String else {
            throw CredentialBrokerError.rejected("Both instances must be signed in to the same AI2Apps account")
        }
        if request["op"] as? String == "list" {
            return try Self.encode(["ok":true,"offer":state])
        }
        guard request["op"] as? String == "export",
              let selected = request["selected"] as? [String], !selected.isEmpty, selected.count <= 16,
              let offer = request["offer_id"] as? String else { throw CredentialBrokerError.rejected("Invalid provider selection") }
        let entries = (state["providers"] as? [[String:Any]] ?? []).filter { selected.contains($0["key"] as? String ?? "") }
        guard entries.count == selected.count else { throw CredentialBrokerError.rejected("Source providers changed; refresh the list") }
        let acquired = lock.withLock { if consentBusy { return false }; consentBusy = true; return true }
        guard acquired else { throw CredentialBrokerError.rejected("Another credential confirmation is open") }
        defer { lock.withLock { consentBusy = false } }
        let labels = Self.labels(destination["language"] as? String ?? "en")
        let targets = request["target_versions"] as? [String:Any] ?? [:]
        let details = entries.map { entry -> String in
            let config = entry["config"] as? [String:Any] ?? [:]
            let legacy = entry["ownership"] as? String == "unclaimed" ? " [\(labels[4])]" : ""
            let overwrite = targets[entry["key"] as? String ?? ""] == nil ? "" : " [\(labels[5])]"
            return "• \(config["name"] as? String ?? "Provider")\n  \(config["base_url"] as? String ?? "")\(legacy)\(overwrite)"
        }.joined(separator:"\n")
        if entries.contains(where:{targets[$0["key"] as? String ?? ""] != nil}) && request["replace_existing"] as? Bool != true {
            throw CredentialBrokerError.rejected("Explicitly select replacement before importing an existing provider")
        }
        let description = "\(labels[1]): \(name) [\(instance)]\n\(labels[2]): \(peer.name) [\(peer.instance)]\n\(labels[3]): \(identity["user_id"] as? String ?? "")\n\n\(details)\n\n\(labels[6]): \(peer.helperPath)\n\n\(labels[7])"
        let confirmed = await MainActor.run {
            NSApp.activate(ignoringOtherApps:true)
            let alert = NSAlert()
            alert.messageText = labels[0]
            alert.informativeText = description
            alert.addButton(withTitle:labels[8])
            alert.addButton(withTitle:labels[9])
            return alert.runModal() == .alertFirstButtonReturn
        }
        guard confirmed else { return try Self.encode(["ok":false,"status":"cancelled"]) }
        let auth = LAContext()
        var authError: NSError?
        guard auth.canEvaluatePolicy(.deviceOwnerAuthentication, error:&authError) else {
            throw CredentialBrokerError.rejected("System owner authentication is unavailable")
        }
        let (granted, failureCode) = await withCheckedContinuation { (continuation: CheckedContinuation<(Bool,Int?),Never>) in
            auth.evaluatePolicy(.deviceOwnerAuthentication, localizedReason:String(format:labels[10],peer.name)) { ok,error in
                continuation.resume(returning:(ok,(error as? LAError)?.code.rawValue))
            }
        }
        defer { auth.invalidate() }
        guard granted else {
            if let failureCode, [LAError.userCancel.rawValue, LAError.appCancel.rawValue, LAError.systemCancel.rawValue].contains(failureCode) {
                return try Self.encode(["ok":false,"status":"cancelled"])
            }
            throw CredentialBrokerError.rejected("System authentication failed")
        }
        guard try Self.socketPeer(connection).requirement == peer.requirement else {
            throw CredentialBrokerError.rejected("Destination process changed during authentication")
        }
        let payload = try await local("export", ["offer_id":offer,"selected":selected,"destination":targetIdentity])
        return try Self.encode(["ok":true,"payload":payload])
    }

    private func local(_ operation: String, _ body: [String:Any]) async throws -> [String:Any] {
        guard let number = await port(), (1024...65535).contains(number) else { throw CredentialBrokerError.rejected("Local is not ready") }
        var request = URLRequest(url:URL(string:"http://127.0.0.1:\(number)/v1/platform/credential-import/native/\(operation)")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 25
        request.setValue("Bearer " + token, forHTTPHeaderField:"Authorization")
        request.setValue("application/json",forHTTPHeaderField:"Content-Type")
        request.httpBody = Data(try Self.encode(body).utf8)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.httpCookieStorage = nil
        configuration.connectionProxyDictionary = [:]
        let session = URLSession(configuration:configuration)
        defer { session.invalidateAndCancel() }
        let (data,response) = try await session.data(for:request)
        guard data.count <= 256*1024, let http = response as? HTTPURLResponse else {
            throw CredentialBrokerError.rejected("Invalid Local credential response")
        }
        if http.statusCode != 200 {
            if let object = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
               let detail = object["detail"] as? String, detail.count <= 300 {
                throw CredentialBrokerError.rejected(detail)
            }
            throw CredentialBrokerError.rejected("Local account or provider state is unavailable; sign in again")
        }
        guard let text = String(data:data,encoding:.utf8) else { throw CredentialBrokerError.rejected("Invalid Local response") }
        return try Self.decode(text)
    }

    private func connect(_ file: URL) throws -> (Int32, CredentialPeer) {
        guard file.pathExtension == "sock", Self.canonicalPath(file.path) == file.path else { throw CredentialBrokerError.rejected("Invalid source descriptor") }
        let attrs = try FileManager.default.attributesOfItem(atPath:file.path)
        guard attrs[.type] as? FileAttributeType == .typeSocket,
              (attrs[.ownerAccountID] as? NSNumber)?.uint32Value == geteuid(),
              ((attrs[.posixPermissions] as? NSNumber)?.intValue ?? 0) & 0o077 == 0 else { throw CredentialBrokerError.rejected("Unsafe source socket") }
        let fd = socket(AF_UNIX,SOCK_STREAM,0)
        guard fd >= 0 else { throw CredentialBrokerError.rejected("Source Helper unavailable") }
        Self.configure(fd,timeout:180)
        do {
            try Self.address(file.path) { address,size in
                guard Darwin.connect(fd,address,size) == 0 else { throw CredentialBrokerError.rejected("Source Helper must be upgraded and running") }
            }
            let peer = try Self.socketPeer(fd)
            guard peer.instance + ".sock" == file.lastPathComponent else { throw CredentialBrokerError.rejected("Source instance mismatch") }
            return (fd,peer)
        } catch { close(fd); throw error }
    }

    private func ask(_ connection: Int32, _ body: [String:Any], timeout: Double = 150) async throws -> [String:Any] {
        let text = try Self.encode(body)
        let result = try await Task.detached {
            Self.configure(connection,timeout:Int(timeout))
            try Self.writeMessage(connection,text)
            return try Self.readMessage(connection)
        }.value
        return try Self.decode(result)
    }

    private static func canonicalPath(_ path: String) -> String? {
        guard let pointer = realpath(path,nil) else { return nil }
        defer { free(pointer) }
        return String(cString:pointer)
    }

    private static func staticPeer(_ raw: String) throws -> CredentialPeer {
        let executable = URL(fileURLWithPath:raw)
        guard canonicalPath(executable.path) == executable.path,
              executable.lastPathComponent == "AI2AppsHelper" else { throw CredentialBrokerError.rejected("Invalid Helper executable") }
        let helper = executable.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let outer = helper.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        guard let bundle = Bundle(url:outer), let helperBundle = Bundle(url:helper),
              let bid = bundle.bundleIdentifier,
              ["com.ai2apps.desktop","com.ai2apps.desktop.dev","com.ai2apps.desktop.appdev","com.ai2apps.desktop.test"].contains(bid),
              helperBundle.bundleIdentifier == bid + ".helper",
              let instance = bundle.object(forInfoDictionaryKey:"AI2AppsInstanceID") as? String else { throw CredentialBrokerError.rejected("Not an AI2Apps Helper") }
        var code: SecStaticCode?
        guard SecStaticCodeCreateWithPath(executable as CFURL, [], &code) == errSecSuccess,
              let code, SecStaticCodeCheckValidity(code, [], nil) == errSecSuccess else { throw CredentialBrokerError.rejected("Helper signature is invalid") }
        var info: CFDictionary?
        guard SecCodeCopySigningInformation(code, SecCSFlags(rawValue:kSecCSSigningInformation), &info) == errSecSuccess,
              let values = info as? [String:Any], let hash = values[kSecCodeInfoUnique as String] as? Data else { throw CredentialBrokerError.rejected("Cannot verify Helper identity") }
        if values[kSecCodeInfoTeamIdentifier as String] as? String != "84XL5V265N" {
            // Ad-hoc builds are accepted only at fixed sibling development/test paths,
            // never by a spoofable bundle ID alone. Consent shows the exact target path.
            let ownOuter = Bundle.main.bundleURL.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            guard canonicalPath(outer.deletingLastPathComponent().path) == canonicalPath(ownOuter.deletingLastPathComponent().path),
                  ["AI2Apps-dev.app","AI2Apps-app-dev.app","AI2Apps-test.app"].contains(outer.lastPathComponent),
                  outer.deletingLastPathComponent().lastPathComponent == ".build" else { throw CredentialBrokerError.rejected("Untrusted Helper signing team") }
        }
        return CredentialPeer(instance:instance,name:bundle.object(forInfoDictionaryKey:"CFBundleDisplayName") as? String ?? instance,
                              helperPath:executable.path,requirement:"cdhash " + hash.map{String(format:"%02x",$0)}.joined())
    }

    private static func socketPeer(_ fd: Int32) throws -> CredentialPeer {
        var uid: uid_t = 0, gid: gid_t = 0
        guard getpeereid(fd,&uid,&gid) == 0, uid == geteuid() else { throw CredentialBrokerError.rejected("Credential peer has a different macOS user") }
        var token = audit_token_t()
        var length = socklen_t(MemoryLayout<audit_token_t>.size)
        guard getsockopt(fd,SOL_LOCAL,LOCAL_PEERTOKEN,&token,&length) == 0,
              length == MemoryLayout<audit_token_t>.size else { throw CredentialBrokerError.rejected("Cannot verify credential peer audit token") }
        let audit = withUnsafeBytes(of:token) { Data($0) }
        var code: SecCode?
        guard SecCodeCopyGuestWithAttributes(nil,[kSecGuestAttributeAudit as String:audit] as CFDictionary,[],&code) == errSecSuccess, let code,
              SecCodeCheckValidity(code, [], nil) == errSecSuccess else { throw CredentialBrokerError.rejected("Untrusted process") }
        var staticCode: SecStaticCode?
        guard SecCodeCopyStaticCode(code, [], &staticCode) == errSecSuccess, let staticCode else {
            throw CredentialBrokerError.rejected("Untrusted executable")
        }
        var info: CFDictionary?
        guard SecCodeCopySigningInformation(staticCode,SecCSFlags(rawValue:kSecCSSigningInformation),&info) == errSecSuccess,
              let values = info as? [String:Any], let url = values[kSecCodeInfoMainExecutable as String] as? URL else { throw CredentialBrokerError.rejected("Untrusted executable") }
        return try staticPeer(url.path)
    }
    private static func labels(_ language: String) -> [String] {
        let localized: [String:[String]] = [
            "en":["Import API keys", "From", "To", "Account", "Confirm legacy key belongs to this account", "Replace destination key", "Destination app", "One-time copy; removing the source does not revoke the destination.", "Authenticate", "Cancel", "Copy the selected AI2Apps API keys once to %@"],
            "zh":["导入 API-Key", "来源", "目标", "账号", "确认旧密钥属于当前账号", "替换目标密钥", "目标程序", "一次性复制；删除来源不会撤销目标副本。", "继续系统验证", "取消", "将选中的 AI2Apps API-Key 一次性导入 %@"],
            "zh-TW":["匯入 API-Key", "來源", "目標", "帳號", "確認舊金鑰屬於目前帳號", "取代目標金鑰", "目標程式", "一次性複製；刪除來源不會撤銷目標副本。", "繼續系統驗證", "取消", "將選取的 AI2Apps API-Key 一次性匯入 %@"],
            "es":["Importar claves API", "Origen", "Destino", "Cuenta", "Confirmar que la clave anterior pertenece a esta cuenta", "Reemplazar la clave de destino", "Aplicación de destino", "Copia única; eliminar el origen no revoca la copia de destino.", "Autenticar", "Cancelar", "Copiar una vez las claves API de AI2Apps seleccionadas a %@"],
            "fr":["Importer des clés API", "Source", "Destination", "Compte", "Confirmer que la clé existante appartient à ce compte", "Remplacer la clé de destination", "Application de destination", "Copie unique ; supprimer la source ne révoque pas la copie de destination.", "Authentifier", "Annuler", "Copier une fois les clés API AI2Apps sélectionnées vers %@"],
            "ja":["API キーをインポート", "コピー元", "コピー先", "アカウント", "既存のキーが現在のアカウントに属することを確認", "コピー先のキーを置き換える", "コピー先アプリ", "一度だけコピーします。コピー元を削除してもコピー先は失効しません。", "システム認証に進む", "キャンセル", "選択した AI2Apps API キーを %@ に一度だけコピーします"],
            "ko":["API 키 가져오기", "원본", "대상", "계정", "기존 키가 현재 계정에 속함을 확인", "대상 키 교체", "대상 앱", "한 번만 복사합니다. 원본을 삭제해도 대상 사본은 취소되지 않습니다.", "시스템 인증 계속", "취소", "선택한 AI2Apps API 키를 %@에 한 번 복사합니다"],
            "pt-BR":["Importar chaves de API", "Origem", "Destino", "Conta", "Confirmar que a chave existente pertence a esta conta", "Substituir a chave de destino", "Aplicativo de destino", "Cópia única; remover a origem não revoga a cópia de destino.", "Autenticar", "Cancelar", "Copiar uma vez as chaves de API AI2Apps selecionadas para %@"],
            "ru":["Импорт API-ключей", "Источник", "Назначение", "Аккаунт", "Подтвердить принадлежность старого ключа этому аккаунту", "Заменить ключ назначения", "Приложение назначения", "Однократное копирование; удаление источника не отзывает копию.", "Пройти проверку", "Отмена", "Однократно скопировать выбранные API-ключи AI2Apps в %@"],
        ]
        return localized[language] ?? localized["en"]!
    }

    private static func sameAccount(_ a: [String:Any], _ b: [String:Any]) -> Bool {
        guard let user = a["user_id"] as? String, !user.isEmpty,
              let cloud = a["cloud_origin"] as? String else { return false }
        return user == b["user_id"] as? String && cloud == b["cloud_origin"] as? String
    }
    private static func encode(_ value: [String:Any]) throws -> String {
        let data = try JSONSerialization.data(withJSONObject:value,options:[.sortedKeys])
        guard data.count <= 256*1024 else { throw CredentialBrokerError.rejected("Credential request is too large") }
        return String(data:data,encoding:.utf8)!
    }
    private static func decode(_ text: String) throws -> [String:Any] {
        guard text.utf8.count <= 256*1024, let data = text.data(using:.utf8),
              let value = try JSONSerialization.jsonObject(with:data) as? [String:Any] else { throw CredentialBrokerError.rejected("Invalid credential message") }
        return value
    }
    private static func failure(_ message: String) -> String { (try? encode(["ok":false,"error":message])) ?? "{}" }
    private static func safeMessage(_ error: Error) -> String { (error as? CredentialBrokerError)?.message ?? "Credential transfer failed; refresh and try again" }
}

