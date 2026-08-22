// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "AI2AppsAceFox",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "AI2AppsContracts", targets: ["AI2AppsContracts"]),
        .library(name: "AI2AppsSupervisorCore", targets: ["AI2AppsSupervisorCore"]),
        .library(name: "AI2AppsUpdateCore", targets: ["AI2AppsUpdateCore"]),
        .executable(name: "ai2apps-contract", targets: ["AI2AppsContractTool"]),
        .executable(name: "ai2apps-helper", targets: ["AI2AppsHelper"]),
        .executable(name: "ai2apps-launcher", targets: ["AI2AppsLauncher"]),
        .executable(name: "ai2apps-updater", targets: ["AI2AppsUpdater"]),
    ],
    targets: [
        .target(name: "AI2AppsContracts"),
        .target(
            name: "AI2AppsSupervisorCore",
            dependencies: ["AI2AppsContracts"]
        ),
        .target(name: "AI2AppsUpdateCore"),
        .executableTarget(
            name: "AI2AppsContractTool",
            dependencies: ["AI2AppsContracts"]
        ),
        .executableTarget(
            name: "AI2AppsHelper",
            dependencies: [
                "AI2AppsContracts",
                "AI2AppsSupervisorCore",
            ]
        ),
        .executableTarget(
            name: "AI2AppsLauncher",
            dependencies: ["AI2AppsContracts", "AI2AppsSupervisorCore"]
        ),
        .executableTarget(
            name: "AI2AppsUpdater",
            dependencies: ["AI2AppsUpdateCore"]
        ),
        .testTarget(
            name: "AI2AppsContractsTests",
            dependencies: ["AI2AppsContracts"]
        ),
        .testTarget(
            name: "AI2AppsSupervisorCoreTests",
            dependencies: ["AI2AppsContracts", "AI2AppsSupervisorCore"]
        ),
        .testTarget(
            name: "AI2AppsUpdateCoreTests",
            dependencies: ["AI2AppsUpdateCore"]
        ),
    ]
)
