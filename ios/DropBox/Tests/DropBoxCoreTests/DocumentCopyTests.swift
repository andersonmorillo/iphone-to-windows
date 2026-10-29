import XCTest
@testable import DropBoxCore

final class DocumentCopyTests: XCTestCase {
    private var root: URL!
    private var documents: URL!

    override func setUpWithError() throws {
        let fileManager = FileManager.default
        root = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        documents = root.appendingPathComponent("Documents", isDirectory: true)
        try fileManager.createDirectory(at: documents, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: root)
    }

    func testNewFileKeepsNameAndBytes() throws {
        let source = try write("photo", named: "photo.jpg")
        let destination = try DocumentCopy.copy(source, into: documents)
        XCTAssertEqual(destination.lastPathComponent, "photo.jpg")
        XCTAssertEqual(try Data(contentsOf: destination), Data("photo".utf8))
    }

    func testCollisionKeepsOriginalAndNumbersCopies() throws {
        let first = try write("one", named: "photo.jpg")
        _ = try DocumentCopy.copy(first, into: documents)
        try Data("changed".utf8).write(to: first)

        let second = try DocumentCopy.copy(first, into: documents)
        let third = try DocumentCopy.copy(first, into: documents)

        XCTAssertEqual(try Data(contentsOf: documents.appendingPathComponent("photo.jpg")), Data("one".utf8))
        XCTAssertEqual(second.lastPathComponent, "photo 2.jpg")
        XCTAssertEqual(try Data(contentsOf: second), Data("changed".utf8))
        XCTAssertEqual(third.lastPathComponent, "photo 3.jpg")
    }

    func testNameWithoutExtensionGetsNumericSuffix() throws {
        let source = try write("notes", named: "notes")
        _ = try DocumentCopy.copy(source, into: documents)
        let second = try DocumentCopy.copy(source, into: documents)
        XCTAssertEqual(second.lastPathComponent, "notes 2")
    }

    func testDirectoryIsRefusedAndDestinationStaysEmpty() throws {
        let source = root.appendingPathComponent("folder", isDirectory: true)
        try FileManager.default.createDirectory(at: source, withIntermediateDirectories: true)
        try Data("inside".utf8).write(to: source.appendingPathComponent("inside.txt"))

        XCTAssertThrowsError(try DocumentCopy.copy(source, into: documents)) { error in
            XCTAssertEqual(error as? DocumentCopyError, .notAFile)
        }
        XCTAssertEqual(try listedNames(), [])
    }

    func testUnreadableSourceWritesNothing() throws {
        let missing = root.appendingPathComponent("missing.bin")
        XCTAssertThrowsError(try DocumentCopy.copy(missing, into: documents)) { error in
            XCTAssertEqual(error as? DocumentCopyError, .unreadable)
        }

        let locked = try write("secret", named: "locked.bin")
        try FileManager.default.setAttributes([.posixPermissions: 0], ofItemAtPath: locked.path)
        defer {
            try? FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: locked.path)
        }
        XCTAssertThrowsError(try DocumentCopy.copy(locked, into: documents)) { error in
            XCTAssertEqual(error as? DocumentCopyError, .unreadable)
        }
        XCTAssertEqual(try listedNames(), [])
    }

    func testStatusLines() {
        XCTAssertEqual(DocumentCopy.status(added: 1, failed: 0), "Added 1 file.")
        XCTAssertEqual(DocumentCopy.status(added: 3, failed: 0), "Added 3 files.")
        XCTAssertEqual(DocumentCopy.status(added: 1, failed: 2), "Added 1 file. 2 failed.")
        XCTAssertEqual(DocumentCopy.status(added: 3, failed: 1), "Added 3 files. 1 failed.")
        XCTAssertEqual(DocumentCopy.status(added: 0, failed: 1), "Nothing copied. 1 failed.")
        XCTAssertNil(DocumentCopy.status(added: 0, failed: 0))
    }

    private func write(_ text: String, named name: String) throws -> URL {
        let url = root.appendingPathComponent(name)
        try Data(text.utf8).write(to: url)
        return url
    }

    private func listedNames() throws -> [String] {
        try FileManager.default.contentsOfDirectory(at: documents, includingPropertiesForKeys: nil)
            .map(\.lastPathComponent)
            .sorted()
    }
}
