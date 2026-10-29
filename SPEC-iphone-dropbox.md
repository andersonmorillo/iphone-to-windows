# Spec: iphone-dropbox

## Objective

A one-screen iPhone app. The owner taps **Add Files to Drop Box**, picks one or more files, and the app copies those files into its Documents folder. USB file sharing is on, so a Mac (Finder) or a Windows PC (iTunes or Apple Devices) can see that folder, and the later `windows-sync` module can read it with libimobiledevice.

The person using it is the phone's owner, moving their own files to a computer over a USB cable. The app does not sync by itself, does not upload anywhere, and does not need to stay open after the copy. Documents remain in the app container when the app is suspended.

### Contract for windows-sync

- Bundle id: `com.andersonlabs.iphone-dropbox`
- Display name: `Drop Box`
- Files are regular files at the root of Documents. There is no subfolder protocol and no manifest file.
- The stored name is the source file's last path component. The only rename is the collision suffix below. This app does not sanitize names for Windows.
- `windows-sync` must tolerate names Windows cannot store (`:`, `*`, `?`, `"`, `<`, `>`, `|`) and names that differ only by case.

### Acceptance

- Tapping the button presents a multi-select picker that accepts any file type.
- Each selected regular file is copied into Documents. An existing file with the same name is left untouched. The new file is stored as `<stem> 2.<ext>`, then `<stem> 3.<ext>`, and so on. A name with no extension uses the same suffix before the end (`notes`, `notes 2`).
- A failure on one file does not discard files already copied in that batch.
- Cancelling the picker does not change Documents.
- Folders are not copied and are not recursed into.
- After at least one file is in Documents, connecting the iPhone shows those files in this app's file-sharing folder.

## Tech Stack

- Swift 6 and SwiftUI
- iOS 17.0 minimum. The package declares `.iOS(.v17)`.
- iPhone only. `Info.plist` sets `UIDeviceFamily` to `1` (iPhone).
- No third-party Swift packages
- Sign and install with your usual iOS toolchain. Credentials stay outside this repo.

File sharing keys live in `ios/DropBox/Info.plist`. Both values are true:

- `UIFileSharingEnabled`
- `LSSupportsOpeningDocumentsInPlace`

Do not set `UISupportsDocumentBrowser`. That is a different feature.

## Commands

Run these from `ios/DropBox`.

```
Test: swift test -Xswiftc -warnings-as-errors
Lint: swift test -Xswiftc -warnings-as-errors
```

Build and install the iOS app from this package with your usual toolchain.

## Project Structure

```
CAPABILITY-MAP.md
SPEC-iphone-dropbox.md
ios/DropBox/
  Package.swift
  Info.plist                 display name, file sharing, iPhone-only
  Sources/DropBoxCore/
    DocumentCopy.swift       copy and collision names (Foundation only)
  Sources/DropBox/
    DropBoxApp.swift         app entry
    ContentView.swift        button, picker, status line
  Tests/DropBoxCoreTests/
    DocumentCopyTests.swift
```

The package has one library product, and that product is the app. `DropBoxCore` is a second target, not a second product, so `swift test` can build the copy logic without compiling SwiftUI. The `DropBox` target depends on `DropBoxCore`. The test target depends only on `DropBoxCore`.

## Code Style

Swift API Design Guidelines. Type and file names are UpperCamelCase. Indent with 4 spaces. No force unwrap. No `try?` on the copy path. Comments only for a platform limit that the code itself cannot show.

The picker is SwiftUI `fileImporter`, not the UIKit sample. `fileImporter` does not take `asCopy`, and its URLs are not readable until security-scoped access starts. Start that access, copy, then stop it, including when the copy throws.

```swift
enum DocumentCopy {
    /// Copies one regular file into `documents`.
    /// A name that already exists gets a " 2", " 3", … suffix. Never overwrites.
    static func copy(_ source: URL, into documents: URL, fileManager: FileManager = .default) throws -> URL {
        let destination = try uniqueDestination(for: source.lastPathComponent, in: documents, fileManager: fileManager)
        try fileManager.copyItem(at: source, to: destination)
        return destination
    }
}
```

`ContentView` owns the button and the status line. It calls `startAccessingSecurityScopedResource` on each picked URL, calls `DocumentCopy.copy` off the main actor, then stops access and updates the status on the main actor. The button is disabled while a batch is copying.

Status strings, exact:

- `Added 1 file.`
- `Added 3 files.`
- `Added 1 file. 2 failed.`
- `Added 3 files. 1 failed.`
- `Nothing copied. 1 failed.`

Cancel leaves the previous status in place. The first screen has no status line.

## Testing Strategy

XCTest, in `ios/DropBox/Tests/DropBoxCoreTests/DocumentCopyTests.swift`. No coverage percentage. No UI test and no USB test. Those two checks are manual on a device.

The unit tests use a temporary directory and cover:

- a new file keeps its name and its bytes
- a second copy of the same name creates `<stem> 2.<ext>` and leaves the first file's bytes unchanged
- a third copy uses `3`
- a directory is refused and the destination is unchanged
- an unreadable source throws and writes nothing

Manual, on a real iPhone, once the unit tests pass:

1. Run the app. Tap **Add Files to Drop Box**. Add two files.
2. Confirm the status line. Force-quit is optional. The files must still be in Documents.
3. Connect the phone to a computer and open file sharing for **Drop Box**. Both files are listed.
4. Add a file whose name already exists. The original bytes are still there, and a ` 2` file appears.

## Boundaries

- Always: copy into Documents before reporting success. Never overwrite an existing Documents file. Keep files at the Documents root. Run the Test command on this machine before calling this module done. Treat Swift warnings as errors on that run.
- Ask first: any dependency, a deployment target other than iOS 17, a bundle id change after `windows-sync` has been specified against `com.andersonlabs.iphone-dropbox`, App Store submission, CI config.
- Never: commit certificates, provisioning profiles, or Apple IDs. Delete or overwrite a file the user already put in Documents. Add a background mode. Add a manifest for the desktop app to parse. Set `UISupportsDocumentBrowser`. Add a second library product.

## Success Criteria

1. The built app `Info.plist` has `UIFileSharingEnabled` and `LSSupportsOpeningDocumentsInPlace` both true, `CFBundleDisplayName` of `Drop Box`, `UIDeviceFamily` of iPhone only, and no `UISupportsDocumentBrowser`.
2. The only control is **Add Files to Drop Box**. It presents a multi-select picker for `UTType.item`.
3. Selected regular files land in Documents under the collision rule above. Folders are counted as failed and are not walked.
4. One bad file in a batch does not roll back files already copied. The status line matches the strings in Code Style.
5. Cancelling the picker does not change Documents or the previous status line.
6. With a file present, Finder (Mac) or iTunes / Apple Devices (Windows) lists this app and shows that file in its Documents folder.
7. The Test command passes on this machine.
8. The app has no background modes, no file list, and no network entitlement.

## Open Questions

None. The bundle id is `com.andersonlabs.iphone-dropbox`, the home screen name is `Drop Box`, and the minimum system is iOS 17.0.
