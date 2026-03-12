# OpenClaw File Browser

A lightweight Python web server for browsing, viewing, editing, uploading, moving, copying, renaming, and deleting files under `~/.openclaw` from any device on your local network.

## Features

- Browse from `~/.openclaw/workspace` and one level up to `~/.openclaw`
- View text and image files
- Edit text files with draft autosave and diff preview
- Upload files, create new files, rename, move, copy, and delete
- Desktop table view and mobile card view
- Dark mode, regex filtering, keyboard shortcuts
- Python stdlib only; no npm or pip install required

## Layout

```text
server.py
static/
  style.css
  app.js
tests/
  test_server.py
docs/
  DESIGN.md
  TESTS.md
README.md
```

## Run

Port 80:

```bash
sudo python3 server.py
```

Alternate port for development:

```bash
python3 server.py --port 8080
```

Optional dashboard link button:

```bash
OPENCLAW_DASHBOARD_URL="https://your-machine.example.ts.net/" python3 server.py --port 8080
```

Optional local config via `.env`:

`server.py` automatically reads `.env` from the repo root on startup. Example:

```bash
OPENCLAW_DASHBOARD_URL="https://your-machine.example.ts.net/"
```

If `OPENCLAW_DASHBOARD_URL` is set, the header shows a `Dashboard` button. If it is missing or blank, the button stays hidden.

Then open:

- `http://localhost/` for port 80
- `http://localhost:8080/` for dev mode

## Test

From the repo root:

```bash
python3 -m unittest tests.test_server -v
```

If you prefer pytest and have it installed:

```bash
python3 -m pytest tests/test_server.py -v
```

## Notes

- Default browse root is `~/.openclaw/workspace`
- Navigation allows going up to `~/.openclaw`, but not above it
- Large files warn before loading; very large files are download-only
- Set `OPENCLAW_DASHBOARD_URL` if you want the header to show a `Dashboard` button; otherwise it is hidden
- No authentication is included by design

## macOS launchd setup

If you want the server to start automatically at system boot on macOS, you can run it with a `launchd` daemon.

Example daemon location:

`/Library/LaunchDaemons/com.openclaw.webserver.plist`

Recommended behavior:

- Run `server.py` as `root` if you need to bind to port `80`
- Set `KeepAlive = true` so the service restarts automatically if it crashes
- Send stdout and stderr to `/tmp/webserver.log` for simple troubleshooting

Useful commands:

Stop the service without removing it:

```bash
sudo launchctl stop com.openclaw.webserver
```

Start the service manually:

```bash
sudo launchctl start com.openclaw.webserver
```

Remove it completely:

```bash
sudo launchctl unload /Library/LaunchDaemons/com.openclaw.webserver.plist
sudo rm /Library/LaunchDaemons/com.openclaw.webserver.plist
```
