# Spec: windows-sync

## Objective

When the iPhone is plugged in, copy new files from Drop Box into one folder the person picked. The window has that path and nothing else to configure. Files already in the folder stay. Nothing is deleted on the phone.

The phone side is `iphone-dropbox`. Files are regular files at the Documents root. This machine is Linux; the same program is the desktop app here and on Windows. Both use `idevice_id` and `afcclient`.

## Tech Stack

- Python 3, already installed. No new packages.
- GTK 4 through PyGObject, already installed, for the folder window.
- `idevice_id` and `afcclient` from libimobiledevice.
- A new file notifies with `notify-send` on Linux, or a Windows balloon if that is the OS.

The bundle id is `com.andersonlabs.iphone-dropbox`. Extra ids, one per line, can be listed in `~/.config/iphone-to-windows/bundles`.

`afcclient --container` is rooted at the app container, so a file is `Documents/<name>`.

## Commands

From the repo root:

```
Test: python3 windows/sync.py --check
Once: DROPBOX_DEST=/path python3 windows/sync.py --once
Dev:  python3 windows/sync.py
```

The chosen folder is saved in `~/.config/iphone-to-windows/destination`.

## Project Structure

```
SPEC-windows-sync.md
windows/sync.py    window, copy, and the self-check
```

## Code Style

One Python file. The name rules and the listing parser are pure functions. Device calls sit behind them. A name Windows cannot store (`: * ? " < > |`, trailing dots and spaces, `CON` and the other reserved names) is rewritten. A name already in the folder, ignoring case, is skipped. Two names that differ only by case in one pass save the second as `name 2`.

## Testing Strategy

`python3 windows/sync.py --check` asserts the name rules, the listing parser, and the status lines. Plugging in the phone is manual: pick a folder, add a file on the phone, see it appear in the folder.

## Boundaries

- Always: copy into the chosen folder only. Never overwrite a file already there. Never delete a file on the phone. One failed file does not undo files already copied.
- Ask first: a new dependency, deleting phone files after copy, watching any folder other than Drop Box Documents.
- Never: store Apple credentials. Write a manifest onto the phone. Follow subfolders.

## Success Criteria

1. The window's only choice is the folder. That choice is remembered.
2. With the phone unplugged, the window says `Waiting for iPhone.`
3. Plugging in the phone copies regular files from Drop Box Documents that are not already in the folder.
4. A second pass does not overwrite those files.
5. `--check` passes.

## Open Questions

None. Delete-after-copy stays off.
