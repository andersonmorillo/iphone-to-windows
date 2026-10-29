# Capability Map: iPhone to Windows

| Module id | Responsibility | Depends on |
|---|---|---|
| iphone-dropbox | Pick files into the app Documents folder and expose that folder over USB file sharing | — |
| windows-sync | When the trusted iPhone is plugged in, copy new Documents files to a PC folder, skip ones already copied, optionally delete them on the phone, then notify | iphone-dropbox |

Build order: iphone-dropbox → windows-sync

The contract between the apps (bundle id, files at the Documents root) lives in `SPEC-iphone-dropbox.md`. Specs, plans, and tasks select work by these module ids.
