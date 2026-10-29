import Foundation

public enum DocumentCopyError: Error, Equatable {
    case notAFile
    case unreadable
}

public enum DocumentCopy {
    /// Copies one regular file into `documents`.
    /// A name that already exists gets a " 2", " 3", … suffix. Never overwrites.
    public static func copy(_ source: URL, into documents: URL, fileManager: FileManager = .default) throws -> URL {
        try requireRegularFile(source, fileManager: fileManager)
        let destination = uniqueDestination(for: source.lastPathComponent, in: documents, fileManager: fileManager)
        do {
            try fileManager.copyItem(at: source, to: destination)
        } catch {
            throw DocumentCopyError.unreadable
        }
        return destination
    }

    public static func status(added: Int, failed: Int) -> String? {
        if added == 0, failed == 0 {
            return nil
        }
        if added == 0 {
            return "Nothing copied. \(failed) failed."
        }
        let files = added == 1 ? "1 file" : "\(added) files"
        if failed == 0 {
            return "Added \(files)."
        }
        return "Added \(files). \(failed) failed."
    }

    private static func requireRegularFile(_ source: URL, fileManager: FileManager) throws {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: source.path, isDirectory: &isDirectory) else {
            throw DocumentCopyError.unreadable
        }
        if isDirectory.boolValue {
            throw DocumentCopyError.notAFile
        }
        guard fileManager.isReadableFile(atPath: source.path) else {
            throw DocumentCopyError.unreadable
        }
    }

    private static func uniqueDestination(for name: String, in documents: URL, fileManager: FileManager) -> URL {
        let original = documents.appendingPathComponent(name)
        if !fileManager.fileExists(atPath: original.path) {
            return original
        }
        let parsed = URL(fileURLWithPath: name)
        let stem = parsed.deletingPathExtension().lastPathComponent
        let ext = parsed.pathExtension
        var number = 2
        while true {
            let nextName = ext.isEmpty ? "\(stem) \(number)" : "\(stem) \(number).\(ext)"
            let candidate = documents.appendingPathComponent(nextName)
            if !fileManager.fileExists(atPath: candidate.path) {
                return candidate
            }
            number += 1
        }
    }
}

public enum ComputerLink {
    public static let fileName = "pc-seen"
    /// The desktop app refreshes this about every 2 seconds.
    public static let maxAge: TimeInterval = 8

    public static func isConnected(modifiedAt: Date?, now: Date) -> Bool {
        guard let modifiedAt else { return false }
        return now.timeIntervalSince(modifiedAt) < maxAge
    }
}
