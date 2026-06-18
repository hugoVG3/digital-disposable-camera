# From Code to Camera — Full Setup & Deployment Guide

This walks through everything from opening the project on your computer
to guests taking photos on a Pi reachable from the internet.

---

## Part A — Local development & debugging (your computer)

### A1. Install prerequisites
- **Python 3.9+** — [python.org/downloads](https://python.org/downloads) (on Windows, tick "Add Python to PATH" during install).
- **Git** — [git-scm.com](https://git-scm.com).
- **VS Code** — [code.visualstudio.com](https://code.visualstudio.com).
- In VS Code, install the **Python** extension (by Microsoft) from the Extensions panel (`Ctrl+Shift+X` / `Cmd+Shift+X`).

### A2. Open the project
Unzip the project, then in VS Code: `File → Open Folder…` → select `digital-disposable-camera`.

### A3. Create a virtual environment & install dependencies
Open a terminal in VS Code (`` Ctrl+` ``):

```bash
python3 -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
pip install pytest   # only needed to run the test suite
```

### A4. Point VS Code at that environment
`Ctrl+Shift+P` → "Python: Select Interpreter" → pick the one inside `./venv`.
This is what makes VS Code stop complaining "Flask could not be resolved" — that warning just means it's looking at the wrong Python, not that anything is broken.

### A5. Run it locally
```bash
cp .env.example .env   # then edit .env with any test values
python app.py
```
Visit `http://127.0.0.1:5000` in a browser. The shutter button will trigger a file picker instead of a real camera (laptops don't have `capture="environment"` cameras the way phones do) — that's expected; pick any image to test the upload flow. To test the real camera UI, run this on your phone's browser pointed at your computer's LAN IP instead (`ipconfig`/`ifconfig` to find it), as long as your firewall allows inbound connections on port 5000.

### A6. Debug with breakpoints
Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Flask (debug)",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/app.py",
      "env": { "FLASK_ENV": "development" },
      "console": "integratedTerminal",
      "justMyCode": true
    }
  ]
}
```
Click in the gutter next to any line (e.g. inside `capture()` in `app/routes/camera.py`) to set a breakpoint, then press `F5`. Execution will pause there when you upload a photo.

### A7. Run the tests
```bash
python -m pytest tests/ -v
```
Or use VS Code's **Testing** sidebar (flask icon) → "Configure Python Tests" → `pytest` → `tests` directory, then run/debug individual tests from there.

---

## Part B — Flashing the Pi's microSD card

### B1. What you need
- A microSD card. The app now keeps photos at (near-)original quality rather than aggressively downsizing them, so size your card for that: modern phone JPEGs commonly run 4-10MB each. For ~70 guests × 24 shots (1,680 photos), that's roughly 7-15GB worst case — **32GB+** gives comfortable headroom. (Faster/higher-endurance cards also help on a Zero 2 W.)
- A card reader for your computer.
- **Raspberry Pi Imager** — [raspberrypi.com/software](https://www.raspberrypi.com/software/).

### B2. Choose the OS
Open Imager → "Choose Device" → Raspberry Pi Zero 2 W → "Choose OS" → **Raspberry Pi OS Lite (64-bit)**. Lite (no desktop) is the right call here — this is a headless web server, no need for a GUI eating RAM on a Zero 2 W.

### B3. Pre-configure it for headless setup (important — do this before flashing)
Click the **gear/settings icon** (or "Edit Settings" in newer Imager versions) before writing:
- **General tab**: set hostname (e.g. `disposable-cam`), username/password, and your Wi-Fi SSID/password.
- **Services tab**: enable SSH, "Use password authentication".

This lets the Pi join your Wi-Fi and accept SSH on first boot — no monitor, keyboard, or HDMI cable ever needed for a Zero 2 W.

### B4. Flash & boot
Select your microSD card as the target, click "Write", wait for it to finish, then move the card to the Pi and power it on. First boot takes a minute or two longer than usual while it resizes the filesystem.

---

## Part C — First boot: connecting to the Pi

### C1. Find it on the network
```bash
ping disposable-cam.local
```
(replace with whatever hostname you set). If that doesn't resolve, check your router's admin page for connected devices, or run `arp -a` (Windows/macOS/Linux) and look for a Raspberry Pi MAC prefix.

### C2. SSH in
```bash
ssh <username>@disposable-cam.local
```

### C3. Update and install system packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git
```

---

## Part D — Get your code onto the Pi

The cleanest path: push your finished project to GitHub from your computer, then clone it on the Pi.

```bash
# on your computer, inside the project folder
git add .
git commit -m "Implement camera capture, admin gallery, deployment docs"
git push origin main
```

```bash
# on the Pi
git clone https://github.com/<you>/digital-disposable-camera.git
cd digital-disposable-camera
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If Pillow fails to build from source (rare — PyPI ships prebuilt ARM wheels for it, but just in case):
```bash
sudo apt install -y libjpeg-dev zlib1g-dev
pip install --no-cache-dir Pillow
```

Create your real secrets file:
```bash
cp .env.example .env
nano .env   # set a real SECRET_KEY and ADMIN_PASSWORD
```

---

## Part E — Manual test run on the Pi

```bash
python app.py
```
From a phone on the same Wi-Fi, visit `http://disposable-cam.local:5000` (or the Pi's LAN IP). Take a test shot, then check it landed on disk:
```bash
ls data/photos/
```
Stop the server with `Ctrl+C` once you've confirmed it works — you don't want to run it this way long-term (no auto-restart, dies if your SSH session drops).

---

## Part F — Production-ize: gunicorn + systemd

```bash
pip install gunicorn
```

Create `/etc/systemd/system/disposable-camera.service`:
```ini
[Unit]
Description=Disposable Camera
After=network.target

[Service]
WorkingDirectory=/home/<username>/digital-disposable-camera
EnvironmentFile=/home/<username>/digital-disposable-camera/.env
ExecStart=/home/<username>/digital-disposable-camera/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always
User=<username>

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now disposable-camera
sudo systemctl status disposable-camera     # confirm it's "active (running)"
```

It will now survive reboots and restart itself if it crashes.

---

## Part G — Networking: port forwarding for WAN access

### G1. Give the Pi a fixed local IP
In your router's admin page, find "DHCP reservation" (sometimes called "Address Reservation" or "Static Lease") and bind the Pi's MAC address to a fixed local IP, e.g. `192.168.1.50`. Without this, the Pi could get a different IP after a power cut, silently breaking your port forward.

### G2. Forward a port
In the router's "Port Forwarding" / "Virtual Server" section, forward an external port (e.g. `8080`) to `192.168.1.50:5000`. The exact menu wording varies a lot by router brand/firmware — search "[your router model] port forwarding" if it's not obvious.

### G3. (Strongly recommended) Dynamic DNS
Most home internet connections have a public IP that changes periodically, which would silently break things for your guests. Set up free dynamic DNS — e.g. [DuckDNS](https://www.duckdns.org) or [No-IP](https://www.noip.com) — which gives you a stable hostname like `mycamera.duckdns.org` that always points at your current public IP, and runs a small updater script/cron job on the Pi to keep it current.

### G4. (Recommended) HTTPS via a reverse proxy
The live in-browser camera viewfinder uses `getUserMedia`, which **only works over HTTPS** (or on `localhost`) — browsers block it entirely on plain HTTP for any other address, as a privacy protection. If you skip this step, the app still works perfectly on plain HTTP: it automatically falls back to handing off to the phone's native camera app instead of showing a live preview. HTTPS just unlocks the in-page live viewfinder.

[Caddy](https://caddyserver.com) is the easiest way to get free, automatic HTTPS:
```bash
sudo apt install -y caddy   # or follow Caddy's install docs for Debian/Raspberry Pi OS
```
Minimal `/etc/caddy/Caddyfile`:
```
mycamera.duckdns.org {
    reverse_proxy localhost:5000
}
```
```bash
sudo systemctl restart caddy
```
Then forward port `443` (and `80`, for the certificate challenge) instead of `5000`/`8080`.

### G5. Basic firewall
```bash
sudo apt install -y ufw
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```
(Skip allowing 5000 externally if you're using Caddy in front of it — only Caddy needs to reach gunicorn, and it does that locally.)

---

## Part H — Getting the photos off the Pi

As flagged above: the Pi's root filesystem is ext4, so yanking the boot microSD and plugging it into a Windows/Mac machine won't behave like a normal disposable camera's card. Pick one:

### H1. Recommended: a Samba network share
This lets you browse `data/photos` from any computer on the network as a normal-looking drive, with the Pi staying up the whole time — no need to ever touch the card.
```bash
sudo apt install -y samba
```
Add to `/etc/samba/smb.conf`:
```ini
[photos]
path = /home/<username>/digital-disposable-camera/data/photos
read only = yes
guest ok = no
valid users = <username>
```
```bash
sudo smbpasswd -a <username>
sudo systemctl restart smbd
```
Now on Windows: `\\disposable-cam\photos`. On Mac: Finder → Go → Connect to Server → `smb://disposable-cam/photos`.

### H2. Alternative: a dedicated USB drive for true "pull and plug"
Format a separate USB flash drive as **exFAT** (readable on both Windows and Mac) or FAT32, plug it into the Pi, mount it, and point the app's storage at it instead of the SD card:
```bash
sudo mkdir /mnt/photos
sudo mount /dev/sda1 /mnt/photos   # adjust device name; check with `lsblk`
```
Add to `.env`:
```
PHOTOS_DIR=/mnt/photos
```
That's it — `config.py` reads `PHOTOS_DIR` from the environment, so no code changes are needed. Once mounted this way, you can `umount /mnt/photos`, physically remove the USB stick, and plug it straight into any computer — that's the actual "pull the storage and plug it into a computer" experience you described.

### H3. Alternative: read the ext4 card directly
Tools exist to read ext4 from Windows (e.g. DiskInternals Linux Reader) or Mac (e.g. Paragon ExtFS), but this still means powering down the Pi to remove its boot card, which stops the whole service. Only worth it for a one-off, after the event is fully over.

---

## Part I — Debugging cheat-sheet

| Symptom | Likely cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | venv isn't activated, or VS Code is using the wrong interpreter — see A4 |
| VS Code underlines `import flask` in red | Same as above — it's a missing-interpreter warning, not a real error, once the venv has Flask installed |
| `PermissionError` writing to `data/` | Run `chown -R <username>:<username> data/` on the Pi, or check the systemd unit's `User=` matches the folder owner |
| Pillow fails to install on the Pi | `sudo apt install libjpeg-dev zlib1g-dev` then retry `pip install Pillow` |
| Phone camera button just opens a file picker, no live camera | Expected on a laptop browser; on a phone, check it's over HTTPS (some mobile browsers restrict `capture` over plain HTTP for non-LAN hosts) |
| Service won't start | `sudo journalctl -u disposable-camera -f` to see the live error |
| Guests can't reach the WAN address | Check the DHCP reservation didn't drift, re-verify the port forward, and confirm DuckDNS updated to your current public IP |
| Rate limit (`429`) hit during testing | Expected protection working as intended — wait a minute, or temporarily raise the limits in `app/routes/camera.py` / `auth.py` while testing |

---

## Part J — Before you actually hand it to guests

- [ ] Set a real, unique `ADMIN_PASSWORD` and `SECRET_KEY` in `.env` (not the placeholders).
- [ ] Run a full 24-shot roll end-to-end on a real phone, then check `/admin` shows it correctly.
- [ ] Check available storage: photos are kept near their original quality (not aggressively compressed), so budget roughly 4-10MB per shot × `(expected guests) × 24` — a 32GB+ card comfortably covers ~70 guests.
- [ ] Try a few rapid taps on the shutter to confirm the cooldown feels right for your event (default 3s) — adjust `COOLDOWN_SECONDS` in `.env` if you want it shorter/longer.
- [ ] Test on at least one iPhone and one Android phone — the live viewfinder and its native-camera fallback behave slightly differently across browsers.
- [ ] Confirm the dynamic DNS hostname resolves correctly from outside your home network (test on mobile data, not Wi-Fi).
- [ ] Decide now how you'll pull photos afterward (Samba share is the path of least friction) so you're not figuring it out mid-event.
