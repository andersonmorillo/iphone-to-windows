#!/usr/bin/env python3
"""Copy new Drop Box files off a plugged-in iPhone into one chosen folder."""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

BUNDLE_ID = "com.andersonlabs.iphone-dropbox"
CONFIG_DIR = Path.home() / ".config" / "iphone-to-windows"
CONFIG = CONFIG_DIR / "destination"
_INVALID = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"}
_RESERVED.update(f"COM{i}" for i in range(1, 10))
_RESERVED.update(f"LPT{i}" for i in range(1, 10))
_TIME = re.compile(r"\d{2}:\d{2}:\d{2}\s+(.*)$")


def local_name(remote: str) -> str:
    cleaned = "".join("_" if c in _INVALID or ord(c) < 32 else c for c in remote)
    cleaned = cleaned.rstrip(" .")
    if cleaned in ("", ".", ".."):
        return "file"
    stem, ext = _stem_ext(cleaned)
    if stem.upper() in _RESERVED:
        stem += "_"
    return stem + ext


def _stem_ext(name: str) -> tuple[str, str]:
    if "." in name and not name.startswith("."):
        stem, ext = name.rsplit(".", 1)
        return stem, "." + ext
    return name, ""


def _with_suffix(name: str, n: int) -> str:
    stem, ext = _stem_ext(name)
    return f"{stem} {n}{ext}"


def plan_copies(remotes: list[str], existing_names: list[str]) -> list[tuple[str, str]]:
    """Names to copy. An existing name, ignoring case, is already copied.

    ponytail: a file that shows up later and differs only by case from one
    already in the folder is skipped. Two twins in the same pass get a
    " 2" suffix. Remember remote names if a later twin must be kept.
    """
    existing = {name.casefold() for name in existing_names}
    taken = set(existing)
    fresh: set[str] = set()
    planned: list[tuple[str, str]] = []
    for remote in remotes:
        if not remote or remote in (".", "..") or "/" in remote:
            continue
        base = local_name(remote)
        fold = base.casefold()
        if fold in existing:
            continue
        if fold in fresh:
            n = 2
            while True:
                candidate = _with_suffix(base, n)
                if candidate.casefold() not in taken:
                    local = candidate
                    break
                n += 1
        else:
            local = base
        fresh.add(fold)
        taken.add(local.casefold())
        planned.append((remote, local))
    return planned


def parse_listing(text: str) -> list[str]:
    """Regular files from `afcclient ls -l`. Directories are skipped."""
    names = []
    for line in text.splitlines():
        if not line.strip():
            continue
        mode = line.split(None, 1)[0]
        if not mode.startswith("-"):
            continue
        match = _TIME.search(line)
        if match:
            names.append(match.group(1))
    return names


def status_text(copied: int, failed: int) -> str:
    if copied == 0 and failed == 0:
        return "iPhone connected. No new files."
    if copied == 0:
        return f"Nothing copied. {failed} failed."
    copied_bit = "Copied 1 file." if copied == 1 else f"Copied {copied} files."
    if failed == 0:
        return copied_bit
    return f"{copied_bit} {failed} failed."


def _afc(udid: str, bundle: str, *args: str) -> str:
    env = os.environ.copy()
    env["POSIXLY_CORRECT"] = "1"
    env.pop("LD_LIBRARY_PATH", None)
    try:
        proc = subprocess.run(
            ["afcclient", "-u", udid, "--container", bundle, *args],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    except FileNotFoundError:
        raise RuntimeError("afcclient is not installed.") from None
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if "ApplicationLookupFailed" in text:
        raise LookupError(bundle)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Error:") or stripped.startswith("ERROR:"):
            raise RuntimeError(stripped)
    return proc.stdout or ""


def device_udid() -> str | None:
    try:
        proc = subprocess.run(
            ["idevice_id", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        raise RuntimeError("idevice_id is not installed.") from None
    ids = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if ids:
        return ids[0]
    if proc.returncode != 0:
        err = ((proc.stderr or proc.stdout) or "idevice_id failed").strip()
        raise RuntimeError(err)
    return None


def bundle_ids() -> list[str]:
    ids = [BUNDLE_ID]
    try:
        lines = (CONFIG_DIR / "bundles").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ids
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and line not in ids:
            ids.append(line)
    return ids


def list_phone_files(udid: str) -> tuple[str, list[str]]:
    for bundle in bundle_ids():
        try:
            text = _afc(udid, bundle, "ls", "-l", "Documents")
        except LookupError:
            continue
        return bundle, parse_listing(text)
    raise LookupError("Drop Box is not on this iPhone.")


def _download(udid: str, bundle: str, remote: str, dest: Path) -> None:
    tmp = dest.with_name("." + dest.name + ".partial")
    try:
        _afc(udid, bundle, "get", f"Documents/{remote}", str(tmp))
        if dest.exists():
            return
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def sync_once(dest: Path) -> str:
    if not dest.is_dir():
        return "That folder is not there."
    for partial in dest.glob(".*.partial"):
        partial.unlink(missing_ok=True)
    udid = device_udid()
    if not udid:
        return "Waiting for iPhone."
    bundle, names = list_phone_files(udid)
    existing = [item.name for item in dest.iterdir() if not item.name.endswith(".partial")]
    copied = 0
    failed = 0
    for remote, local in plan_copies(names, existing):
        try:
            _download(udid, bundle, remote, dest / local)
            copied += 1
        except (OSError, RuntimeError, LookupError):
            failed += 1
    text = status_text(copied, failed)
    if copied:
        _notify(text)
    return text


def _notify(body: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "Drop Box", body], check=False)
        return
    if os.name != "nt":
        return
    env = os.environ.copy()
    env["DROPBOX_MSG"] = body
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.Visible = $true; "
            "$n.ShowBalloonTip(4000, 'Drop Box', $env:DROPBOX_MSG, 'Info'); "
            "Start-Sleep -Seconds 4; $n.Dispose()",
        ],
        env=env,
        check=False,
    )


def load_dest() -> str | None:
    override = os.environ.get("DROPBOX_DEST", "").strip()
    if override:
        return override
    try:
        text = CONFIG.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return text or None


def save_dest(path: str) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(path + "\n", encoding="utf-8")


def _check() -> None:
    listing = (
        "-rw-r--r--    1 mobile mobile         12 28 Oct 2026 19:54:17 my file.jpg\n"
        "drwxr-xr-x    2 mobile mobile         64 28 Oct 2026 19:54:17 Sub\n"
    )
    assert parse_listing(listing) == ["my file.jpg"]
    assert parse_listing("") == []
    assert local_name("a:b?.jpg") == "a_b_.jpg"
    assert local_name("notes") == "notes"
    assert local_name("CON.txt") == "CON_.txt"
    assert local_name("...") == "file"
    assert plan_copies(["photo.jpg"], []) == [("photo.jpg", "photo.jpg")]
    assert plan_copies(["photo.jpg"], ["photo.jpg"]) == []
    assert plan_copies(["Photo.JPG"], ["photo.jpg"]) == []
    assert plan_copies(["photo.jpg", "Photo.JPG"], []) == [
        ("photo.jpg", "photo.jpg"),
        ("Photo.JPG", "Photo 2.JPG"),
    ]
    assert plan_copies(["notes"], ["notes"]) == []
    assert plan_copies(["dir/nope"], []) == []
    assert status_text(1, 0) == "Copied 1 file."
    assert status_text(3, 1) == "Copied 3 files. 1 failed."
    assert status_text(0, 1) == "Nothing copied. 1 failed."
    assert status_text(0, 0) == "iPhone connected. No new files."
    print("ok")


class _Watcher:
    def __init__(self, on_status) -> None:
        self.dest: str | None = None
        self.stop = False
        self._on_status = on_status
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        while not self.stop:
            dest = self.dest
            if dest:
                try:
                    message = sync_once(Path(dest))
                except (OSError, RuntimeError, LookupError) as exc:
                    message = str(exc)
                self._on_status(message)
            for _ in range(20):
                if self.stop:
                    return
                time.sleep(0.1)


def run_gui() -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, Gtk, Pango

    class App(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id="com.andersonlabs.iphone-dropbox.sync")
            self.dest: str | None = None
            self.watcher: _Watcher | None = None

        def do_activate(self) -> None:
            win = Gtk.ApplicationWindow(application=self, title="Drop Box")
            win.set_default_size(560, 180)
            # Hyprland tiles this window. Keep the form a fixed width in the middle.
            outer = Gtk.Box()
            outer.set_halign(Gtk.Align.CENTER)
            outer.set_valign(Gtk.Align.CENTER)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_size_request(480, -1)
            heading = Gtk.Label(label="Save phone files to", xalign=0)

            row = Gtk.Box(spacing=8)
            self.path_label = Gtk.Label(label="No folder yet", xalign=0, selectable=True)
            self.path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            self.path_label.set_hexpand(True)
            choose = Gtk.Button(label="Choose folder")
            choose.connect("clicked", self._choose)
            row.append(self.path_label)
            row.append(choose)

            self.status = Gtk.Label(label="Choose a folder.", xalign=0)
            self.status.set_wrap(True)
            box.append(heading)
            box.append(row)
            box.append(self.status)
            outer.append(box)
            win.set_child(outer)
            win.present()

            self.watcher = _Watcher(self._post_status)
            saved = load_dest()
            if saved:
                self._set_dest(saved)
            else:
                GLib.idle_add(self._choose)
            self.watcher.start()

        def do_shutdown(self) -> None:
            if self.watcher:
                self.watcher.stop = True
            Gtk.Application.do_shutdown(self)

        def _post_status(self, message: str) -> None:
            GLib.idle_add(self.status.set_text, message)

        def _set_dest(self, path: str) -> None:
            self.dest = path
            if self.watcher:
                self.watcher.dest = path
            self.path_label.set_text(path)
            self.status.set_text("Waiting for iPhone.")

        def _choose(self, *_args) -> bool:
            dialog = Gtk.FileDialog()
            dialog.set_title("Save phone files to")
            if self.dest and Path(self.dest).is_dir():
                dialog.set_initial_folder(Gio.File.new_for_path(self.dest))
            dialog.select_folder(self.get_active_window(), None, self._chosen)
            return False

        def _chosen(self, dialog, result) -> None:
            try:
                folder = dialog.select_folder_finish(result)
            except GLib.Error:
                return
            path = folder.get_path()
            if not path:
                return
            save_dest(path)
            self._set_dest(path)

    app = App()
    app.run(None)


def main(argv: list[str]) -> None:
    if "--check" in argv:
        _check()
        return
    if "--once" in argv:
        dest = load_dest()
        if not dest:
            raise SystemExit("Choose a folder first, or set DROPBOX_DEST.")
        print(sync_once(Path(dest)))
        return
    run_gui()


if __name__ == "__main__":
    main(sys.argv[1:])
