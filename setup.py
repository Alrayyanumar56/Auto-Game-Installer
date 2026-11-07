"""
setup.py - one-time setup for Auto Game Installer (Windows + qBittorrent).

Asks where games should be installed, copies the script to a permanent folder,
and wires it into qBittorrent's "Run external program on torrent finished".
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AutoGameInstaller"
QB_INI = Path(os.environ.get("APPDATA", "")) / "qBittorrent" / "qBittorrent.ini"


def qt_quote(s: str) -> str:
    """Quote a string the way Qt writes it in .ini files."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def qbittorrent_running() -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq qbittorrent.exe"],
        capture_output=True,
        text=True,
    ).stdout
    return "qbittorrent.exe" in out.lower()


def set_keys(lines, section, kv):
    header = f"[{section}]"
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        return lines + ["", header] + [f"{k}={v}" for k, v in kv.items()]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
        len(lines),
    )
    remaining = dict(kv)
    for i in range(start + 1, end):
        key = lines[i].split("=", 1)[0]
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines[end:end] = [f"{k}={v}" for k, v in remaining.items()]
    return lines


def main():
    if os.name != "nt":
        print("This tool is for Windows only.")
        return 1

    default = r"D:\Games"
    answer = input(f"Where should games be installed? [{default}]: ").strip().strip('"')
    install_root = answer or default
    Path(install_root).mkdir(parents=True, exist_ok=True)

    APP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "autoinstall.py", APP_DIR / "autoinstall.py")
    (APP_DIR / "config.json").write_text(
        json.dumps({"install_root": install_root}, indent=2), encoding="utf-8"
    )
    print(f"Installed script to {APP_DIR}")

    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    runner = str(pyw if pyw.exists() else py)
    program = f'"{runner}" "{APP_DIR / "autoinstall.py"}" "%N" "%F"'

    if not QB_INI.exists():
        print("\nCouldn't find qBittorrent's settings file. Set it up by hand:")
        print("qBittorrent > Options > Downloads > Run external program on torrent finished")
        print(program)
        return 0

    if qbittorrent_running():
        print("\nqBittorrent is running. Close it completely (check the system tray) and run setup again.")
        return 1

    backup = QB_INI.with_name("qBittorrent.ini.bak")
    shutil.copy2(QB_INI, backup)
    lines = QB_INI.read_text(encoding="utf-8").splitlines()
    value = qt_quote(program)
    # qBittorrent 4.x and 5.x use different key names, so write both.
    lines = set_keys(
        lines,
        "AutoRun",
        {
            "enabled": "true",
            "program": value,
            "OnTorrentFinished\\Enabled": "true",
            "OnTorrentFinished\\Program": value,
        },
    )
    QB_INI.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    print(f"\nqBittorrent configured (backup saved as {backup.name}).")
    print("Open qBittorrent > Options > Downloads and confirm the external program box is filled in.")
    print("Remember: run qBittorrent as administrator, or installers will wait on a UAC prompt.")
    print(f"Check results in: {APP_DIR / 'autoinstall.log'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
