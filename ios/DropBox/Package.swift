// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "DropBox",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        // One library product: the app.
        .library(
            name: "DropBox",
            targets: ["DropBox"]
        ),
    ],
    targets: [
        .target(name: "DropBoxCore"),
        // `swift test` builds this product on Linux, where SwiftUI does not exist.
        // The sources compile only when SwiftUI is present.
        .target(
            name: "DropBox",
            dependencies: ["DropBoxCore"]
        ),
        .testTarget(
            name: "DropBoxCoreTests",
            dependencies: ["DropBoxCore"]
        ),
    ]
)
