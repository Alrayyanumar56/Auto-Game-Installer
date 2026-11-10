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
APP_VERSION = "0.2.0"
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
# Settings and log sit next to whatever runs the hook (the installed .exe, or
# this folder when running from source).
CFG_DIR = APP_DIR if FROZEN else Path(__file__).resolve().parent
QB_INI = Path(os.environ.get("APPDATA", "")) / "qBittorrent" / "qBittorrent.ini"
NO_WINDOW = 0x08000000  # keep console windows from flashing on Windows
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"

# One colour scheme everywhere (app, README, videos): night navy + mint.
BG = "#0B1020"
SURFACE = "#141B2E"
BORDER = "#232C47"
TEXT = "#E8EEFF"
MUTED = "#8A94B2"
MINT = "#3DDC97"
MINT_HOVER = "#63E8AF"
RED = "#FF6B6B"


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


def apply_setup(
    install_root: str, qb_exe: str, run_admin: bool, mute: bool = True, shutdown: bool = False
):
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
            json.dumps(
                {
                    "install_root": install_root,
                    "mute_installer": mute,
                    "shutdown_after_install": shutdown,
                },
                indent=2,
            ),
            encoding="utf-8",
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
    from tkinter import filedialog

    root = tk.Tk()
    root.title("Auto Game Installer")
    root.configure(bg=BG)
    root.resizable(False, False)
    try:
        logo = tk.PhotoImage(file=str(ASSETS / "icon_512.png"))
        root.iconphoto(True, logo)
        header_logo = logo.subsample(8, 8)  # 64 px
    except tk.TclError:
        header_logo = None

    F = "Segoe UI"
    games_var = tk.StringVar(value=r"D:\Games" if os.path.exists("D:\\") else r"C:\Games")
    qb = find_qbittorrent()
    qb_var = tk.StringVar(value=str(qb) if qb else "")
    admin_var = tk.BooleanVar(value=True)
    mute_var = tk.BooleanVar(value=True)
    shutdown_var = tk.BooleanVar(value=False)

    # ---- small styled widgets -------------------------------------------
    def button(parent, text, command, primary=False):
        bg, fg, hover = (MINT, BG, MINT_HOVER) if primary else (BORDER, TEXT, "#2D3858")
        b = tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
            activeforeground=fg, relief="flat", bd=0, cursor="hand2",
            font=(F, 10, "bold" if primary else "normal"), padx=16, pady=7,
        )
        b.bind("<Enter>", lambda _e: b.configure(bg=hover))
        b.bind("<Leave>", lambda _e: b.configure(bg=bg))
        return b

    def entry(parent, var):
        return tk.Entry(
            parent, textvariable=var, bg=BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=(F, 10), highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=MINT,
        )

    def check(parent, text, var):
        return tk.Checkbutton(
            parent, text=text, variable=var, bg=SURFACE, fg=TEXT, selectcolor=BG,
            activebackground=SURFACE, activeforeground=TEXT, font=(F, 10),
            anchor="w", bd=0, highlightthickness=0, cursor="hand2",
        )

    def label(parent, text, size=10, color=TEXT, bold=False, bg=None):
        return tk.Label(
            parent, text=text, bg=bg or parent["bg"], fg=color,
            font=(F, size, "bold" if bold else "normal"), anchor="w", justify="left",
        )

    # ---- header ---------------------------------------------------------
    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=24, pady=(22, 14))
    if header_logo:
        tk.Label(head, image=header_logo, bg=BG).pack(side="left", padx=(0, 14))
    titles = tk.Frame(head, bg=BG)
    titles.pack(side="left")
    label(titles, "Auto Game Installer", 17, TEXT, True).pack(anchor="w")
    label(titles, "Download at night. Wake up to a game that's ready to play.", 10, MUTED).pack(anchor="w")

    # ---- paths card -----------------------------------------------------
    card = tk.Frame(root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="x", padx=24)
    inner = tk.Frame(card, bg=SURFACE)
    inner.pack(fill="x", padx=16, pady=14)
    inner.columnconfigure(0, weight=1)

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

    label(inner, "Install games to", 9, MUTED).grid(row=0, column=0, sticky="w")
    entry(inner, games_var).grid(row=1, column=0, sticky="ew", ipady=6, pady=(2, 10))
    button(inner, "Browse", pick_folder).grid(row=1, column=1, padx=(8, 0), pady=(2, 10))
    label(inner, "qBittorrent location", 9, MUTED).grid(row=2, column=0, sticky="w")
    entry(inner, qb_var).grid(row=3, column=0, sticky="ew", ipady=6, pady=(2, 0))
    button(inner, "Browse", pick_qb).grid(row=3, column=1, padx=(8, 0), pady=(2, 0))

    # ---- options card ---------------------------------------------------
    opts = tk.Frame(root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
    opts.pack(fill="x", padx=24, pady=(12, 0))
    oi = tk.Frame(opts, bg=SURFACE)
    oi.pack(fill="x", padx=12, pady=10)
    check(oi, "Start qBittorrent as administrator (installs run without prompts)", admin_var).pack(fill="x", pady=2)
    check(oi, "Mute installer sound (window stays visible)", mute_var).pack(fill="x", pady=2)
    check(oi, "Shut down the PC after the last queued install finishes", shutdown_var).pack(fill="x", pady=2)

    # ---- status ---------------------------------------------------------
    status = tk.Text(
        root, height=6, width=64, bg=BG, fg=TEXT, relief="flat", wrap="word", state="disabled",
        font=(F, 10), highlightthickness=1, highlightbackground=BORDER, padx=10, pady=8,
    )
    status.tag_configure("ok", foreground=MINT)
    status.tag_configure("bad", foreground=RED)
    status.tag_configure("dim", foreground=MUTED)

    def show(items):
        status.configure(state="normal")
        status.delete("1.0", "end")
        for tag, text in items:
            status.insert("end", text + "\n", tag)
        status.configure(state="disabled")

    def on_setup():
        results = apply_setup(
            games_var.get().strip(), qb_var.get().strip(),
            admin_var.get(), mute_var.get(), shutdown_var.get(),
        )
        items = [("ok" if good else "bad", ("\u2713  " if good else "!  ") + msg) for good, msg in results]
        if all(good for good, _ in results):
            items.append(("dim", "\nAll done. Start qBittorrent and download something."))
        else:
            items.append(("dim", "\nFix the red lines, then click Set Up again, or use the manual command below."))
        show(items)

    def open_log():
        log = CFG_DIR / "autoinstall.log"
        if log.exists():
            os.startfile(str(log))  # noqa: S606
        else:
            show([("dim", "No log yet. It appears after the first download finishes.")])

    bar = tk.Frame(root, bg=BG)
    bar.pack(fill="x", padx=24, pady=14)
    button(bar, "Set Up", on_setup, primary=True).pack(side="left")
    button(bar, "Open log", open_log).pack(side="left", padx=(8, 0))
    label(bar, f"v{APP_VERSION}", 9, MUTED).pack(side="right")

    status.pack(fill="x", padx=24)
    show([("dim", "Pick your folders, choose your options, then click Set Up.")])

    # ---- manual fallback ------------------------------------------------
    label(
        root,
        "Manual fallback: qBittorrent > Options > Downloads > Run external program on torrent finished",
        9, MUTED,
    ).pack(fill="x", padx=24, pady=(14, 4))
    manual = tk.Frame(root, bg=BG)
    manual.pack(fill="x", padx=24, pady=(0, 22))
    manual.columnconfigure(0, weight=1)
    cmd_var = tk.StringVar(value=hook_command())
    e = entry(manual, cmd_var)
    e.configure(state="readonly", readonlybackground=BG)
    e.grid(row=0, column=0, sticky="ew", ipady=5)

    def copy_cmd():
        root.clipboard_clear()
        root.clipboard_append(cmd_var.get())

    button(manual, "Copy", copy_cmd).grid(row=0, column=1, padx=(8, 0))

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
