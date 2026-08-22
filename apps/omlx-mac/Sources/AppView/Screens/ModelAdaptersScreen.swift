import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ModelAdaptersScreen: View {
    @Environment(AppServices.self) private var services
    @Environment(\.omlxTheme) private var theme
    @State private var vm = ModelAdaptersScreenVM()
    @State private var pendingRemoval: ModelAdapterPackageDTO?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionHeader(
                String(localized: "model_adapters.catalog.title",
                       defaultValue: "Available adapters"),
                subtitle: String(localized: "model_adapters.catalog.subtitle",
                                 defaultValue: "Only releases verified by the signed oMLX catalog are shown")
            ) {
                Button {
                    Task { await vm.refreshCatalog(client: services.client) }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .disabled(vm.isWorking)
            }
            ListGroup {
                if vm.catalogItems.isEmpty {
                    Row(
                        label: String(localized: "model_adapters.catalog.empty",
                                      defaultValue: "No verified releases available"),
                        sublabel: vm.catalogError,
                        isLast: true
                    )
                } else {
                    ForEach(Array(vm.catalogItems.enumerated()), id: \.element.id) { index, item in
                        Row(
                            label: item.displayName,
                            sublabel: vm.catalogSubtitle(item),
                            isLast: index == vm.catalogItems.count - 1
                        ) {
                            HStack(spacing: 8) {
                                if item.installedVersion == nil || item.updateAvailable {
                                    Button(item.installedVersion == nil
                                           ? String(localized: "model_adapters.install", defaultValue: "Install")
                                           : String(localized: "model_adapters.update", defaultValue: "Update")) {
                                        Task { await vm.install(item, client: services.client) }
                                    }
                                    .buttonStyle(.omlx(.primary))
                                    .disabled(vm.isWorking)
                                }
                                if item.installedVersion != nil, item.checkpoints.count == 1,
                                   let checkpoint = item.checkpoints.first {
                                    Button(String(localized: "model_adapters.download_weights",
                                                  defaultValue: "Download Weights")) {
                                        Task { await vm.download(checkpoint, client: services.client) }
                                    }
                                    .disabled(vm.isWorking)
                                } else if item.installedVersion != nil, item.checkpoints.count > 1 {
                                    Menu(String(localized: "model_adapters.download_weights",
                                                defaultValue: "Download Weights")) {
                                        ForEach(item.checkpoints) { checkpoint in
                                            Button(checkpoint.displayName) {
                                                Task { await vm.download(checkpoint, client: services.client) }
                                            }
                                        }
                                    }
                                    .disabled(vm.isWorking)
                                }
                            }
                        }
                    }
                }
            }

            SectionHeader(
                String(localized: "model_adapters.install.title",
                       defaultValue: "Install model support"),
                subtitle: String(localized: "model_adapters.install.subtitle",
                                 defaultValue: "Install or upgrade a reviewed adapter wheel without updating the app")
            )
            ListGroup {
                Row(
                    label: String(localized: "model_adapters.wheel.label",
                                  defaultValue: "Adapter wheel"),
                    sublabel: vm.selectedWheel ?? String(
                        localized: "model_adapters.wheel.empty",
                        defaultValue: "Choose a local .whl package"
                    ),
                    isLast: true
                ) {
                    HStack(spacing: 8) {
                        Button(String(localized: "model_adapters.choose", defaultValue: "Choose…")) {
                            Task { await vm.chooseWheel(client: services.client) }
                        }
                        Button(String(localized: "model_adapters.install", defaultValue: "Install")) {
                            Task { await vm.install(client: services.client) }
                        }
                        .buttonStyle(.omlx(.primary))
                        .disabled(vm.inspectedWheel == nil || vm.isWorking)
                    }
                }
            }

            if vm.restartRequired {
                ListGroup {
                    Row(
                        label: String(localized: "model_adapters.restart.title",
                                      defaultValue: "Restart required"),
                        sublabel: String(localized: "model_adapters.restart.subtitle",
                                         defaultValue: "Restart the local server to activate the package change"),
                        isLast: true
                    ) {
                        Button(String(localized: "model_adapters.restart", defaultValue: "Restart Server")) {
                            Task { await vm.restart(services: services) }
                        }
                        .buttonStyle(.omlx(.primary))
                        .disabled(vm.isWorking)
                    }
                }
            }

            SectionHeader(
                String(localized: "model_adapters.installed.title",
                       defaultValue: "Installed adapters"),
                subtitle: String(localized: "model_adapters.installed.subtitle",
                                 defaultValue: "Active versions are loaded when the server starts")
            ) {
                if vm.isWorking { ProgressView().controlSize(.small) }
            }

            ListGroup {
                if vm.packages.isEmpty {
                    Row(
                        label: String(localized: "model_adapters.installed.empty",
                                      defaultValue: "No adapter packages installed"),
                        isLast: true
                    )
                } else {
                    ForEach(Array(vm.packages.enumerated()), id: \.element.id) { index, package in
                        Row(
                            label: package.name,
                            sublabel: "v\(package.version) · \(package.entryPoints.keys.sorted().joined(separator: ", "))",
                            isLast: index == vm.packages.count - 1
                        ) {
                            Button(role: .destructive) {
                                pendingRemoval = package
                            } label: {
                                Image(systemName: "trash")
                            }
                            .buttonStyle(.borderless)
                            .disabled(vm.isWorking)
                        }
                    }
                }
            }

            if let message = vm.statusMessage {
                Text(message)
                    .font(.omlxText(11.5))
                    .foregroundStyle(theme.textSecondary)
                    .padding(.horizontal, 18)
                    .padding(.top, 6)
            }
            if let error = vm.lastError {
                Text(error)
                    .font(.omlxText(11.5))
                    .foregroundStyle(.red)
                    .padding(.horizontal, 18)
                    .padding(.top, 6)
            }
        }
        .task { await vm.load(client: services.client) }
        .confirmationDialog(
            String(localized: "model_adapters.download_prompt.title",
                   defaultValue: "Download model weights now?"),
            isPresented: Binding(
                get: { vm.pendingCheckpoint != nil },
                set: { if !$0 { vm.pendingCheckpoint = nil } }
            ),
            titleVisibility: .visible
        ) {
            if let checkpoint = vm.pendingCheckpoint {
                Button(String(localized: "model_adapters.download_weights",
                              defaultValue: "Download Weights")) {
                    vm.pendingCheckpoint = nil
                    Task { await vm.download(checkpoint, client: services.client) }
                }
            }
            Button(String(localized: "model_adapters.download_later", defaultValue: "Later"), role: .cancel) {
                vm.pendingCheckpoint = nil
            }
        } message: {
            if let checkpoint = vm.pendingCheckpoint {
                Text("\(checkpoint.displayName) · \(checkpoint.repoId)")
            }
        }
        .confirmationDialog(
            String(localized: "model_adapters.remove.confirm",
                   defaultValue: "Remove this model adapter?"),
            isPresented: Binding(
                get: { pendingRemoval != nil },
                set: { if !$0 { pendingRemoval = nil } }
            ),
            titleVisibility: .visible
        ) {
            if let package = pendingRemoval {
                Button(String(localized: "model_adapters.remove", defaultValue: "Remove"), role: .destructive) {
                    pendingRemoval = nil
                    Task { await vm.uninstall(package, client: services.client) }
                }
            }
            Button(String(localized: "common.cancel", defaultValue: "Cancel"), role: .cancel) {
                pendingRemoval = nil
            }
        }
    }
}

@MainActor
@Observable
private final class ModelAdaptersScreenVM {
    var packages: [ModelAdapterPackageDTO] = []
    var catalogItems: [ModelAdapterCatalogItemDTO] = []
    var catalogError: String?
    var pendingCheckpoint: ModelAdapterCheckpointDTO?
    var selectedWheel: String?
    var inspectedWheel: ModelAdapterPackageDTO?
    var restartRequired = false
    var isWorking = false
    var statusMessage: String?
    var lastError: String?

    func chooseWheel(client: OMLXClient) async {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        if let wheelType = UTType(filenameExtension: "whl") {
            panel.allowedContentTypes = [wheelType]
        }
        if panel.runModal() == .OK {
            selectedWheel = panel.url?.path
            inspectedWheel = nil
            statusMessage = nil
            lastError = nil
            guard let selectedWheel else { return }
            isWorking = true
            defer { isWorking = false }
            do {
                let inspected = try await client.inspectModelAdapterPackage(
                    wheelPath: selectedWheel
                )
                inspectedWheel = inspected
                statusMessage = "Ready to install \(inspected.name) \(inspected.version)."
            } catch {
                lastError = error.omlxDescription
            }
        }
    }

    func load(client: OMLXClient) async {
        do {
            packages = try await client.listModelAdapterPackages().items
            lastError = nil
        } catch {
            lastError = error.omlxDescription
        }
        await refreshCatalog(client: client)
    }

    func refreshCatalog(client: OMLXClient) async {
        do {
            let response = try await client.listModelAdapterCatalog()
            var latest: [String: ModelAdapterCatalogItemDTO] = [:]
            for item in response.items where latest[item.packageId] == nil {
                latest[item.packageId] = item
            }
            catalogItems = latest.values.sorted { $0.displayName < $1.displayName }
            catalogError = nil
        } catch {
            catalogItems = []
            catalogError = error.omlxDescription
        }
    }

    func catalogSubtitle(_ item: ModelAdapterCatalogItemDTO) -> String {
        guard let installed = item.installedVersion else {
            return "v\(item.version) · signed catalog"
        }
        if item.updateAvailable {
            return "v\(item.version) available · v\(installed) installed"
        }
        return "v\(installed) installed"
    }

    func install(_ item: ModelAdapterCatalogItemDTO, client: OMLXClient) async {
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await client.installModelAdapterFromCatalog(
                packageName: item.packageId,
                version: item.version
            )
            restartRequired = result.restartRequired
            statusMessage = result.operation == "upgraded"
                ? "Upgraded \(result.name) to \(result.version) from the signed catalog."
                : "Installed \(result.name) \(result.version) from the signed catalog."
            await load(client: client)
            if item.checkpoints.count == 1 {
                pendingCheckpoint = item.checkpoints.first
            }
        } catch {
            lastError = error.omlxDescription
        }
    }

    func download(_ checkpoint: ModelAdapterCheckpointDTO, client: OMLXClient) async {
        isWorking = true
        defer { isWorking = false }
        do {
            if checkpoint.installMode == "cache-moe" {
                guard let recipeId = checkpoint.recipeId else {
                    lastError = "Cached-MoE recommendation is missing its recipe."
                    return
                }
                _ = try await client.installModelAdapterCheckpoint(
                    packageName: checkpoint.packageId,
                    packageVersion: checkpoint.packageVersion,
                    recipeId: recipeId
                )
                statusMessage = "Started downloading and preparing \(checkpoint.displayName). Track progress in Models."
                lastError = nil
                return
            }
            guard checkpoint.source == "huggingface" else {
                lastError = "Unsupported checkpoint source: \(checkpoint.source)"
                return
            }
            _ = try await client.startHFDownload(
                repoId: checkpoint.repoId,
                revision: checkpoint.revision
            )
            statusMessage = "Started downloading \(checkpoint.displayName). Track progress in Downloads."
            lastError = nil
        } catch {
            lastError = error.omlxDescription
        }
    }

    func install(client: OMLXClient) async {
        guard let selectedWheel, inspectedWheel != nil else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await client.installModelAdapterPackage(wheelPath: selectedWheel)
            restartRequired = result.restartRequired
            statusMessage = result.operation == "upgraded"
                ? "Upgraded \(result.name) to \(result.version)."
                : "Installed \(result.name) \(result.version)."
            self.selectedWheel = nil
            inspectedWheel = nil
            await load(client: client)
        } catch {
            lastError = error.omlxDescription
        }
    }

    func uninstall(_ package: ModelAdapterPackageDTO, client: OMLXClient) async {
        isWorking = true
        defer { isWorking = false }
        do {
            let result = try await client.uninstallModelAdapterPackage(name: package.normalizedName)
            restartRequired = result.restartRequired
            statusMessage = "Removed \(package.name)."
            await load(client: client)
        } catch {
            lastError = error.omlxDescription
        }
    }

    func restart(services: AppServices) async {
        isWorking = true
        defer { isWorking = false }
        do {
            try await services.restartServer()
            restartRequired = false
            statusMessage = "Server restarted. Adapter changes are active."
            await load(client: services.client)
        } catch {
            lastError = error.omlxDescription
        }
    }
}
