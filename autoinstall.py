"""
autoinstall.py - run a game installer automatically when a torrent finishes.

Called by qBittorrent like:
    pythonw autoinstall.py "%N" "%F"
%N = torrent name, %F = path of the downloaded content (file or folder).
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
logging.basicConfig(
    filename=BASE / "autoinstall.log",
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
)
log = logging.info

INSTALLER_NAMES = {"setup.exe", "install.exe", "installer.exe"}


def load_config():
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    cfg.setdefault("install_root", r"D:\Games")
    return cfg


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
    """Inno Setup installers carry a recognizable marker near the start."""
    try:
        with open(exe, "rb") as f:
            return b"Inno Setup" in f.read(8 * 1024 * 1024)
    except OSError:
        return False


def main():
    if len(sys.argv) < 3:
        print('usage: autoinstall.py "<torrent name>" "<content path>"')
        return 2

    name, content = sys.argv[1], Path(sys.argv[2])
    cfg = load_config()
    log(f"Torrent finished: {name} -> {content}")

    installer = find_installer(content)
    if not installer:
        log("No setup.exe found. Nothing to install (archive/ISO? extract it first).")
        return 1

    target = Path(cfg["install_root"]) / name
    log(f"Installer: {installer}  |  Install to: {target}")

    if is_inno_setup(installer):
        cmd = [str(installer), "/SILENT", f"/DIR={target}", "/NORESTART"]
        log("Detected Inno Setup: running unattended.")
    else:
        cmd = [str(installer)]
        log("Not Inno Setup: launching normally, you'll need to click through it.")

    try:
        result = subprocess.run(cmd, cwd=installer.parent)
        log(f"Installer exited with code {result.returncode}")
        return result.returncode
    except Exception as e:  # noqa: BLE001
        log(f"Failed to run installer: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
