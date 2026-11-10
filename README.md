

https://github.com/user-attachments/assets/6ebcf867-9b01-4ae0-a0f5-c1c47b66ffc9



# Auto Game Installer


Installer/releases/latest/download/AutoGameInstaller.exe

Uploading AutoGameInstaller.mp4…


Leave your PC on overnight, wake up to a game that's already installed.

When qBittorrent finishes downloading a torrent (the moment it switches to
seeding), this tool finds the game's `setup.exe` and installs it into your
chosen folder with no clicks needed.

## Install (1 minute, no Python needed)

1. Download `AutoGameInstaller.exe` from the [latest release](../../releases/latest).
2. Close qBittorrent completely (check the system tray).
3. Double-click `AutoGameInstaller.exe`, pick your games folder with **Browse**, and click **Set Up**.
4. Open qBittorrent and download a game. Done.

Windows may show a "Windows protected your PC" screen because the app isn't
code-signed yet: click **More info > Run anyway**. The source code is all in
this repo if you want to check it.

Results are logged to `%LOCALAPPDATA%\AutoGameInstaller\autoinstall.log`
(or click **Open log** in the app).

### Run from source

```
python app.py
```

### Manual setup

If the app can't find qBittorrent's settings, copy the command shown at the
bottom of the window into qBittorrent: Options > Downloads >
"Run external program on torrent finished".

## How it works

- Finds `setup.exe` / `install.exe` / `installer.exe` in the finished download.
- **Inno Setup installers** (most game repacks) run with `/SILENT /DIR=...`:
  the progress window shows, but every page is answered for you.
- **Other installers** just open normally; you click through them.
- qBittorrent is set to start as administrator so installers don't stop at a
  Windows permission prompt. Windows asks for permission once each time
  qBittorrent opens.
- Everything is logged so you can see what happened overnight.

## Troubleshooting

**Nothing installs and there's no `autoinstall.log`**
The qBittorrent hook isn't running. Re-run the app, make sure qBittorrent was
fully closed first, then check Options > Downloads > "Run external program on
torrent finished" is filled in.

**The installer opens but waits for clicks**
It isn't an Inno Setup installer, so it can't run unattended. See the log.

**"No setup.exe found" in the log**
The download is probably an archive or disc image (`.rar`, `.iso`). Not
supported yet.

## Limitations

- Windows + qBittorrent only (for now).
- `.rar` / `.iso` downloads aren't extracted yet.
- It runs the installer in every finished torrent that contains one. Only use
  it on downloads you trust and are allowed to have.

## Roadmap

- Extract archives / mount ISOs automatically
- Only run for torrents in a chosen category
- Antivirus scan before running
- Support for other torrent clients
- Code-signed release

## Building the .exe

Push a tag like `v0.1.0` and GitHub Actions builds `AutoGameInstaller.exe` and
attaches it to a release (see `.github/workflows/build.yml`).

## License

MIT
