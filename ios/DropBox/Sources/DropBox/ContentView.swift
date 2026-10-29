#if canImport(SwiftUI)
import DropBoxCore
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @State private var showImporter = false
    @State private var photos: [PhotosPickerItem] = []
    @State private var pending: [URL] = []
    @State private var isCopying = false
    @State private var status: String?
    @State private var computerConnected = false

    var body: some View {
        VStack(spacing: 16) {
            if computerConnected {
                Text("Connected to the computer.")
                Text("Everything works.")
            } else {
                Text("Not connected to the computer.")
                    .font(.title2.bold())
                Text("Plug it in and unlock it.")
            }
            PhotosPicker("Photos", selection: $photos, maxSelectionCount: nil, matching: .images)
                .disabled(isCopying)
            Button("Add Files to Drop Box") {
                showImporter = true
            }
            .disabled(isCopying)
            Button("Send") {
                Task { await sendPending() }
            }
            .disabled(pending.isEmpty || isCopying)
            if !pending.isEmpty {
                Text(pending.count == 1 ? "1 ready." : "\(pending.count) ready.")
            } else if let status {
                Text(status)
            }
        }
        .padding()
        .task {
            while !Task.isCancelled {
                computerConnected = Self.computerIsConnected()
                try? await Task.sleep(for: .seconds(1))
            }
        }
        .onChange(of: photos) { _, items in
            guard !items.isEmpty else { return }
            photos = []
            Task { await stagePhotos(items) }
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            // Cancel leaves the previous status in place.
            guard case .success(let urls) = result else { return }
            Task { await stageFiles(urls) }
        }
    }

    private func stagePhotos(_ items: [PhotosPickerItem]) async {
        isCopying = true
        defer { isCopying = false }
        var failed = 0
        for item in items {
            do {
                guard let image = try await item.loadTransferable(type: GalleryImage.self) else {
                    failed += 1
                    continue
                }
                pending.append(image.url)
            } catch {
                failed += 1
            }
        }
        if failed > 0, let line = DocumentCopy.status(added: 0, failed: failed) {
            status = line
        }
    }

    private func stageFiles(_ urls: [URL]) async {
        isCopying = true
        defer { isCopying = false }
        var failed = 0
        for url in urls {
            let accessed = url.startAccessingSecurityScopedResource()
            defer {
                if accessed {
                    url.stopAccessingSecurityScopedResource()
                }
            }
            do {
                pending.append(try stageCopy(of: url))
            } catch {
                failed += 1
            }
        }
        if failed > 0, let line = DocumentCopy.status(added: 0, failed: failed) {
            status = line
        }
    }

    private func sendPending() async {
        let urls = pending
        guard !urls.isEmpty else { return }
        isCopying = true
        defer { isCopying = false }

        guard let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else {
            status = DocumentCopy.status(added: 0, failed: urls.count)
            return
        }

        var added = 0
        var failed = 0
        for url in urls {
            do {
                _ = try await Task.detached {
                    try DocumentCopy.copy(url, into: documents)
                }.value
                added += 1
            } catch {
                failed += 1
            }
            try? FileManager.default.removeItem(at: url.deletingLastPathComponent())
        }
        pending.removeAll()
        status = DocumentCopy.status(added: added, failed: failed)
    }

    private static func computerIsConnected(now: Date = Date()) -> Bool {
        guard let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else {
            return false
        }
        let stamp = caches.appendingPathComponent(ComputerLink.fileName)
        let modified = try? stamp.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate
        return ComputerLink.isConnected(modifiedAt: modified, now: now)
    }
}

private func stageCopy(of source: URL) throws -> URL {
    let folder = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString, isDirectory: true)
    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    let destination = folder.appendingPathComponent(source.lastPathComponent)
    try FileManager.default.copyItem(at: source, to: destination)
    return destination
}

/// The gallery hands us a temporary file. Copy it before that file disappears.
private struct GalleryImage: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .image) { image in
            SentTransferredFile(image.url)
        } importing: { received in
            GalleryImage(url: try stageCopy(of: received.file))
        }
    }
}
#endif
