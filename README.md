# Drop Box

Move your own files from an iPhone to a computer over a USB cable.

On the phone, open **Drop Box**, choose photos or other files, then tap **Send**. Send stays off until something is chosen. The files are copied into the app's Documents folder, which stays visible over USB file sharing.

On the computer, run the desktop app, pick one folder, and plug the phone in. New files are copied there. A name already in the folder is skipped. Nothing on the phone is deleted or overwritten.

## iPhone app

Swift package in `ios/DropBox`. iOS 17, iPhone only. Bundle id `com.andersonlabs.iphone-dropbox`. No third-party packages.

```
cd ios/DropBox
swift test
```

Sign and install with your usual iOS toolchain. File sharing is already on in `Info.plist`.

## Desktop app

`windows/sync.py` is one Python 3 program. It uses GTK 4 (PyGObject) for the folder window, and `idevice_id` plus `afcclient` from [libimobiledevice](https://libimobiledevice.org/) to read the phone. Those are the same tools on Linux and Windows. The phone needs to be unlocked and trusted.

```
python3 windows/sync.py
```

The chosen folder is remembered in `~/.config/iphone-to-windows/destination`.

```
python3 windows/sync.py --check
DROPBOX_DEST=/path python3 windows/sync.py --once
```

If the installed app uses another bundle id, list extra ids, one per line, in `~/.config/iphone-to-windows/bundles`.

## Layout

- `ios/DropBox` — the iPhone app and its copy tests
- `windows/sync.py` — the desktop copier
- `SPEC-iphone-dropbox.md` and `SPEC-windows-sync.md` — the behavior each side keeps

## License

[MIT](LICENSE)
