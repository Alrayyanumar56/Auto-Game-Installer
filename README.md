# Auto Game Installer

Leave your PC on overnight, wake up to a game that's already installed.

When qBittorrent finishes downloading a torrent (the moment it switches to
seeding), this tool finds the game's `setup.exe` and installs it into your
chosen folder with no clicks needed.

## Setup (2 minutes)

1. Install [Python 3](https://www.python.org/downloads/) (tick "Add to PATH").
2. Close qBittorrent completely (check the system tray).
3. Run: `python setup.py` and enter your install folder (e.g. `D:\Games`).
4. Start qBittorrent **as administrator** (otherwise installers stop at the UAC prompt).

That's it. Results are logged to `%LOCALAPPDATA%\AutoGameInstaller\autoinstall.log`.

### Manual setup

If `setup.py` can't find your qBittorrent settings: copy `autoinstall.py` and
`config.json.example` (renamed `config.json`) into one folder, then in
qBittorrent go to Options > Downloads > "Run external program on torrent finished":

    pythonw "C:\path\to\autoinstall.py" "%N" "%F"

## How it works

- Finds `setup.exe` / `install.exe` / `installer.exe` in the finished download.
- **Inno Setup installers** (most game repacks) run with `/SILENT /DIR=...`:
  the progress window shows, but every page is answered for you.
- **Other installers** just open normally; you click through them.
- Everything is logged so you can see what happened overnight.

## Limitations

- Windows + qBittorrent only (for now).
- `.rar` / `.iso` downloads aren't extracted yet.
- Only installs; it doesn't scan files. Only use it on downloads you trust and
  are allowed to have.

## Roadmap

- Extract archives / mount ISOs automatically
- Antivirus scan before running
- Support for other torrent clients
- Packaged `.exe` installer

## License

MIT
## Troubleshooting

**"Python was not found"**
Install Python from python.org/downloads. On the first screen, tick
"Add python.exe to PATH". Close and reopen your terminal, then check with
`python --version`. If the Microsoft Store message still appears, turn off the
`python.exe` entries under Settings > Apps > Advanced app settings >
App execution aliases.

**Nothing installs and there's no `autoinstall.log`**
The qBittorrent hook isn't running. Check that Python is on your PATH and that
the command is saved under Options > Downloads > Run external program on
torrent finished.

**The installer opens but waits for clicks**
It isn't an Inno Setup installer, so it can't run unattended. See the log.## Troubleshooting

**"Python was not found"**
Install Python from python.org/downloads. On the first screen, tick
"Add python.exe to PATH". Close and reopen your terminal, then check with
`python --version`. If the Microsoft Store message still appears, turn off the
`python.exe` entries under Settings > Apps > Advanced app settings >
App execution aliases.

**Nothing installs and there's no `autoinstall.log`**
The qBittorrent hook isn't running. Check that Python is on your PATH and that
the command is saved under Options > Downloads > Run external program on
torrent finished.

**The installer opens but waits for clicks**
It isn't an Inno Setup installer, so it can't run unattended. See the log.
