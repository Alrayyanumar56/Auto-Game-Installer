"""
autoinstall.py - run a game installer automatically when a torrent finishes.

Called by qBittorrent like:
    autoinstall.exe "%N" "%F"
%N = torrent name, %F = path of the downloaded content (file or folder).

v0.2.0 adds:
  - an install queue (two torrents finishing together install one after another)
  - muting the installer's sound while keeping its window visible
  - an optional shutdown after the last queued install succeeds

config.json (next to the app) keys:
  install_root           folder games go into          (default D:\\Games)
  mute_installer         true/false                    (default true)
  shutdown_after_install true/false                    (default false)
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

try:
    import msvcrt  # Windows only
except ImportError:  # pragma: no cover
    msvcrt = None

# Same rule as app.py: the installed .exe keeps its settings and log beside
# itself (%LOCALAPPDATA%\\AutoGameInstaller); from source, use this folder.
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent
BASE.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=BASE / "autoinstall.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
log = logging.info

INSTALLER_NAMES = {"setup.exe", "install.exe", "installer.exe"}
LOCK_FILE = BASE / "install.lock"
PENDING_DIR = BASE / "pending"
PENDING_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------- config
def load_config():
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
        log("config.json missing or unreadable, using defaults.")
    cfg.setdefault("install_root", r"D:\Games")
    cfg.setdefault("mute_installer", True)
    cfg.setdefault("shutdown_after_install", False)
    return cfg


# ---------------------------------------------------------------- finding the installer
def find_installer(content_path: Path):
    """Return the shallowest setup.exe-like file in the downloaded content."""
    if content_path.is_file():
        return content_path if content_path.suffix.lower() == ".exe" else None
    matches = [
        p for p in content_path.rglob("*.exe") if p.name.lower() in INSTALLER_NAMES
    ]
    if not matches:
        return None
    return min(matches, key=lambda p: len(p.relative_to(content_path).parts))


def is_inno_setup(exe: Path) -> bool:
    try:
        with open(exe, "rb") as f:
            return b"Inno Setup" in f.read(8 * 1024 * 1024)
    except OSError:
        return False


# ---------------------------------------------------------------- queue
def mark_pending():
    (PENDING_DIR / f"{os.getpid()}.txt").write_text("pending")


def unmark_pending():
    (PENDING_DIR / f"{os.getpid()}.txt").unlink(missing_ok=True)


def others_pending() -> int:
    """How many other copies of this script are still waiting or installing."""
    count = 0
    for p in PENDING_DIR.glob("*.txt"):
        try:
            pid = int(p.stem)
        except ValueError:
            continue
        if pid == os.getpid():
            continue
        if psutil.pid_exists(pid):
            count += 1
        else:
            p.unlink(missing_ok=True)  # leftover from a crashed run
    return count


def acquire_queue_lock():
    """Block until no other install is running. Windows frees the lock
    automatically if a process dies, so a crash can't jam the queue."""
    f = open(LOCK_FILE, "a+b")
    announced = False
    while True:
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            if not announced:
                log("Another install is running. Waiting in the queue.")
                announced = True
            time.sleep(5)


def release_queue_lock(f):
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    f.close()


# ---------------------------------------------------------------- muting
def mute_loop(root_pid: int, stop: threading.Event):
    """Ten times a second, mute any audio session that belongs to the
    installer or to a process it started. The window stays visible."""
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()
    except Exception as e:  # noqa: BLE001
        log(f"Muting unavailable ({e}). Installer sound will play.")
        return
    while not stop.is_set():
        try:
            pids = {root_pid}
            pids.update(c.pid for c in psutil.Process(root_pid).children(recursive=True))
            for session in AudioUtilities.GetAllSessions():
                if session.Process and session.Process.pid in pids:
                    session.SimpleAudioVolume.SetMute(1, None)
        except Exception:  # noqa: BLE001
            pass
        stop.wait(0.1)


# ---------------------------------------------------------------- running
def run_installer(cmd, cwd, mute: bool) -> int:
    proc = subprocess.Popen(cmd, cwd=cwd)
    stop = threading.Event()
    if mute:
        threading.Thread(target=mute_loop, args=(proc.pid, stop), daemon=True).start()
    try:
        return proc.wait()
    finally:
        stop.set()


def shutdown_pc():
    log("Shutting down in 60 seconds. Run 'shutdown /a' to cancel.")
    subprocess.run(
        [
            "shutdown", "/s", "/t", "60",
            "/c", "Auto Game Installer finished. Run 'shutdown /a' to cancel.",
        ]
    )


def main():
    if len(sys.argv) < 3:
        print('usage: autoinstall "<torrent name>" "<content path>"')
        return 2

    name, content = sys.argv[1], Path(sys.argv[2])
    cfg = load_config()
    log(f"Torrent finished: {name} -> {content}")

    installer = find_installer(content)
    if not installer:
        log("No setup.exe found. Nothing to install (archive/ISO? extract it first).")
        return 1

    mark_pending()  # tells other runs "an install is queued"
    lock = None
    code = 1
    try:
        if msvcrt:
            lock = acquire_queue_lock()

        target = Path(cfg["install_root"]) / name
        log(f"Installer: {installer} | Install to: {target}")

        if is_inno_setup(installer):
            cmd = [str(installer), "/SILENT", f"/DIR={target}", "/NORESTART"]
            log("Detected Inno Setup: running unattended.")
        else:
            cmd = [str(installer)]
            log("Not Inno Setup: launching normally, you'll need to click through it.")

        try:
            code = run_installer(cmd, installer.parent, bool(cfg["mute_installer"]))
            log(f"Installer exited with code {code}")
        except Exception as e:  # noqa: BLE001
            log(f"Failed to run installer: {e}")
            code = 1
    finally:
        if lock:
            release_queue_lock(lock)
        unmark_pending()

    # Shut down only if this install worked and nothing else is queued.
    if code == 0 and cfg["shutdown_after_install"] and others_pending() == 0:
        shutdown_pc()
    return code


if __name__ == "__main__":
    sys.exit(main())
