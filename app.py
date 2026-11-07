"""
Auto Game Installer

  - Double-click (no arguments): opens the one-time setup window.
  - Called by qBittorrent as  AutoGameInstaller.exe "%N" "%F"  : installs the
    finished download.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "AutoGameInstaller"
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
# Settings and log sit next to whatever runs the hook (the installed .exe, or
# this folder when running from source).
CFG_DIR = APP_DIR if FROZEN else Path(__file__).resolve().parent
QB_INI = Path(os.environ.get("APPDATA", "")) / "qBittorrent" / "qBittorrent.ini"
NO_WINDOW = 0x08000000  # keep console windows from flashing on Windows


def qt_quote(s: str) -> str:
    """Quote a string the way Qt writes it in .ini files."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_keys(lines, section, kv):
    """Set key=value pairs inside [section] of an .ini file (list of lines)."""
    header = f"[{section}]"
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        return lines + ["", header] + [f"{k}={v}" for k, v in kv.items()]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
        len(lines),
    )
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1  # insert new keys before the blank line that ends the section
    remaining = dict(kv)
    for i in range(start + 1, end):
        key = lines[i].split("=", 1)[0]
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines[end:end] = [f"{k}={v}" for k, v in remaining.items()]
    return lines


def qbittorrent_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq qbittorrent.exe"],
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW,
        ).stdout
    except OSError:
        return False
    return "qbittorrent.exe" in out.lower()


def find_qbittorrent():
    roots = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"),
    ]
    for root in roots:
        if root:
            exe = Path(root) / "qBittorrent" / "qbittorrent.exe"
            if exe.exists():
                return exe
    return None


def hook_command() -> str:
    """The command qBittorrent runs when a torrent finishes."""
    if FROZEN:
        return f'"{APP_DIR / (APP_NAME + ".exe")}" "%N" "%F"'
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    runner = pyw if pyw.exists() else py
    return f'"{runner}" "{Path(__file__).resolve()}" "%N" "%F"'


def set_run_as_admin(qb_exe: Path):
    """Mark qbittorrent.exe 'run as administrator' (same as the Compatibility tab)."""
    import winreg

    path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        try:
            current = winreg.QueryValueEx(key, str(qb_exe))[0]
        except FileNotFoundError:
            current = ""
        if "RUNASADMIN" in current:
            return
        flags = f"{current} RUNASADMIN" if current else "~ RUNASADMIN"
        winreg.SetValueEx(key, str(qb_exe), 0, winreg.REG_SZ, flags)


def apply_setup(install_root: str, qb_exe: str, run_admin: bool):
    """Do every setup step. Returns a list of (ok, message)."""
    results = []

    def ok(msg):
        results.append((True, msg))

    def bad(msg):
        results.append((False, msg))

    # 1. Save settings and install the app files.
    try:
        Path(install_root).mkdir(parents=True, exist_ok=True)
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        (CFG_DIR / "config.json").write_text(
            json.dumps({"install_root": install_root}, indent=2), encoding="utf-8"
        )
        if FROZEN:
            target = APP_DIR / f"{APP_NAME}.exe"
            if Path(sys.executable).resolve() != target.resolve():
                shutil.copy2(sys.executable, target)
        ok(f"Games will be installed to: {install_root}")
    except OSError as e:
        bad(f"Could not save settings: {e}")
        return results

    # 2. Tell qBittorrent to run us when a download finishes.
    if not QB_INI.exists():
        bad(
            "Couldn't find qBittorrent's settings file. Open qBittorrent once, "
            "close it, then click Set Up again (or use the manual command below)."
        )
    elif qbittorrent_running():
        bad(
            "qBittorrent is still running. Close it completely (check the system "
            "tray), then click Set Up again."
        )
    else:
        try:
            shutil.copy2(QB_INI, QB_INI.with_name("qBittorrent.ini.bak"))
            lines = QB_INI.read_text(encoding="utf-8").splitlines()
            value = qt_quote(hook_command())
            # Older and newer qBittorrent versions use different key names.
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
            ok("qBittorrent will run the installer when a download finishes.")
        except OSError as e:
            bad(f"Could not update qBittorrent's settings: {e}")

    # 3. Make qBittorrent start as administrator so installers don't hit UAC.
    if run_admin:
        if qb_exe and Path(qb_exe).exists():
            try:
                set_run_as_admin(Path(qb_exe))
                ok(
                    "qBittorrent will always start as administrator "
                    "(Windows asks for permission each time it opens)."
                )
            except OSError as e:
                bad(f"Could not set run-as-administrator: {e}")
        else:
            bad("qbittorrent.exe wasn't found. Pick it with Browse so it can run as admin.")
    return results


def gui():
    import tkinter as tk
    from tkinter import filedialog, ttk

    root = tk.Tk()
    root.title("Auto Game Installer")
    root.resizable(False, False)
    pad = {"padx": 12, "pady": 6}

    games_var = tk.StringVar(value=r"D:\Games" if os.path.exists("D:\\") else r"C:\Games")
    qb = find_qbittorrent()
    qb_var = tk.StringVar(value=str(qb) if qb else "")
    admin_var = tk.BooleanVar(value=True)

    def pick_folder():
        chosen = filedialog.askdirectory(initialdir=games_var.get() or None)
        if chosen:
            games_var.set(os.path.normpath(chosen))

    def pick_qb():
        chosen = filedialog.askopenfilename(
            title="Select qbittorrent.exe", filetypes=[("qBittorrent", "qbittorrent.exe")]
        )
        if chosen:
            qb_var.set(os.path.normpath(chosen))

    ttk.Label(root, text="Install games to:").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(root, textvariable=games_var, width=50).grid(row=0, column=1, **pad)
    ttk.Button(root, text="Browse...", command=pick_folder).grid(row=0, column=2, **pad)

    ttk.Label(root, text="qBittorrent location:").grid(row=1, column=0, sticky="w", **pad)
    ttk.Entry(root, textvariable=qb_var, width=50).grid(row=1, column=1, **pad)
    ttk.Button(root, text="Browse...", command=pick_qb).grid(row=1, column=2, **pad)

    ttk.Checkbutton(
        root,
        text="Start qBittorrent as administrator (needed so installs run unattended)",
        variable=admin_var,
    ).grid(row=2, column=0, columnspan=3, sticky="w", **pad)

    status = tk.Text(root, height=9, width=78, state="disabled", wrap="word")
    status.grid(row=4, column=0, columnspan=3, **pad)

    def show(lines):
        status.configure(state="normal")
        status.delete("1.0", "end")
        status.insert("end", "\n".join(lines))
        status.configure(state="disabled")

    def on_setup():
        results = apply_setup(games_var.get().strip(), qb_var.get().strip(), admin_var.get())
        lines = [("[OK]  " if good else "[!!]  ") + msg for good, msg in results]
        lines.append("")
        if all(good for good, _ in results):
            lines.append("All done. Start qBittorrent and download a game. Check 'Open log' later.")
        else:
            lines.append("Some steps need attention (see [!!] above). You can also use the manual command below.")
        show(lines)

    def open_log():
        log = CFG_DIR / "autoinstall.log"
        if log.exists():
            os.startfile(str(log))  # noqa: S606
        else:
            show(["No log yet. It appears after the first download finishes."])

    buttons = ttk.Frame(root)
    buttons.grid(row=3, column=0, columnspan=3, sticky="w", **pad)
    ttk.Button(buttons, text="Set Up", command=on_setup).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Open log", command=open_log).pack(side="left")

    ttk.Label(
        root,
        text="Manual fallback: paste this into qBittorrent > Options > Downloads >\n"
        "'Run external program on torrent finished'",
    ).grid(row=5, column=0, columnspan=3, sticky="w", **pad)
    cmd_var = tk.StringVar(value=hook_command())
    ttk.Entry(root, textvariable=cmd_var, width=62, state="readonly").grid(
        row=6, column=0, columnspan=2, sticky="w", **pad
    )

    def copy_cmd():
        root.clipboard_clear()
        root.clipboard_append(cmd_var.get())

    ttk.Button(root, text="Copy", command=copy_cmd).grid(row=6, column=2, **pad)

    root.mainloop()


def main():
    if len(sys.argv) >= 3:  # called by qBittorrent
        import autoinstall

        return autoinstall.main()
    if os.name != "nt":
        print("Auto Game Installer is for Windows only.")
        return 1
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
