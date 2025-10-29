# USGS River Monitoring System

A containerized river gauge monitoring system that tracks USGS water levels, sends email alerts, and displays live data on a web dashboard.

## Features

- 📊 Real-time monitoring of multiple USGS river gauges
- 📧 Email alerts for threshold crossings (IN/OUT)
- 📈 Percentage change alerts (20%+ changes)
- 🌐 Live web dashboard with trend indicators
- ⏳ Stale data warnings for gauges not updating
- 🗄️ SQLite state persistence with alert cooldowns
- 🌧️ NWS Quantitative Precipitation Forecast (QPF) integration

## Quick Start

### 1. Configure Your Gauges and Credentials

**IMPORTANT: Never commit real credentials to Git!**

Create your configuration file from the template:
```bash
cp gauges.conf.json.example gauges.conf.json
```

Edit `gauges.conf.json` and update:
- SMTP credentials (or use environment variables - see below)
- River gauges and thresholds

### 2. Secure Setup (Recommended)

**Option A: Environment Variables (Most Secure)**

Keep placeholder values in `gauges.conf.json` and pass real credentials via environment variables:

```bash
podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  -e SMTP_USER="your-email@gmail.com" \
  -e SMTP_PASS="your-app-password" \
  -e SMTP_TO="your-email@gmail.com" \
  -e NWS_UA="your-app-name/1.0" \
  -e NWS_CONTACT="your-email@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-alert:latest
```

**Option B: Config File (Keep it private)**

Put real credentials in `gauges.conf.json` but **never commit this file**. It's already in `.gitignore`.

### 3. Getting a Gmail App Password

For Gmail SMTP:
1. Enable 2-factor authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use this 16-character password (not your regular Gmail password)

## Build & Run

### Build the container:
```bash
podman build -t usgs-alert:latest .
```

### Run the container:
```bash
podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  -e NWS_UA="your-app-name/1.0" \
  -e NWS_CONTACT="your-email@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-alert:latest
```

### Access the dashboard:
```
http://localhost:8080
```

### View logs:
```bash
podman logs -f usgs-alert
```

## Sharing on GitHub - Security Checklist

Before pushing to GitHub, verify:

- [ ] `gauges.conf.json` is in `.gitignore` (✓ already done)
- [ ] You've created `gauges.conf.json` from the `.example` file
- [ ] No real passwords/tokens appear in any committed files
- [ ] Test with: `git status` - `gauges.conf.json` should NOT appear
- [ ] If you accidentally committed secrets, rotate them immediately

To check for accidentally committed secrets:
```bash
git log --all --full-history -- "*gauges.conf.json"
```

If you find committed secrets:
1. Rotate/revoke the credentials immediately
2. Consider using tools like `git-filter-repo` to remove from history
3. Force push (⚠️ destructive - coordinate with collaborators)

## Commands Reference


 # Confirm the site files exist on the host (bind mount)
ls -l "$(pwd)/usgs-site"/{index.html,gauges.json}

# Test via curl
curl -I http://localhost:8080

# View logs
podman logs -f usgs-alert

# Restart / stop
podman restart usgs-alert
podman stop usgs-alert

# Enable at boot (user mode)
podman generate systemd --new --name usgs-alert --files
mkdir -p ~/.config/systemd/user
mv container-usgs-alert.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now container-usgs-alert.service
loginctl enable-linger "$USER"


#Update the gauges file:
# 1) Stop & remove the existing container (keeps your data/site dirs)
podman stop usgs-alert
podman rm usgs-alert

# 2) Run again, ADDING a bind-mount for the config (read-only)
podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  localhost/usgs-alert:3.1


#Get the container to start after reboot 
#Using Quadlet
 ~/.config/containers/systemd/usgs-alert.container

mkdir -p ~/.config/systemd/user/default.target.wants
ln -sf ~/.config/containers/systemd/usgs-alert.container \
       ~/.config/systemd/user/default.target.wants/usgs-alert.container

# reload and start
systemctl --user daemon-reload
systemctl --user restart usgs-alert.service

# verify
systemctl --user is-enabled usgs-alert.service
systemctl --user status usgs-alert.service --no-pager

 systemctl --user daemon-reload
 systemctl --user restart usgs-alert.service
 systemctl --user is-enabled usgs-alert.service
 systemctl --user status usgs-alert.service --no-pager

  mbajslkpryfvhlyl
 
# Export the container
 podman export -o usgs-alert.tar 586ec117f368 

# Build the container after updates:

 podman rm -f usgs-alert || true

 VER=usgs-alert:$(date +%Y%m%d%H%M)
 podman build -t "$VER" -t usgs-alert:latest .


# Run the container:
 podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  -e NWS_UA="mdchansl-usgs-alert/1.0" \
  -e NWS_CONTACT="michael.chanslor@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-alert:latest


 podman logs -f usgs-alert

# Confirming
podman logs -f usgs-alert | egrep -i 'QPF|quantitativePrecipitation|api.weather.gov'
ls -l usgs-data/qpf_cache.sqlite

# Rebuild and run:
 # From the directory with Containerfile, usgs_multi_alert.py, qpf.py, entrypoint.sh
 podman build -t localhost/usgs-alert:3.3 -t localhost/usgs-alert:latest .

 podman rm -f usgs-alert 2>/dev/null || true

 podman run -d --name usgs-alert \
  --pull=never \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  -v "$(pwd)/gauges.conf.json":/app/gauges.conf.json:ro,Z \
  -e RUN_INTERVAL_SEC=600 \
  -e NWS_UA="mdchansl-usgs-alert/1.0" \
  -e NWS_CONTACT="michael.chanslor@gmail.com" \
  -e QPF_TTL_HOURS="3" \
  -e QPF_CACHE="/data/qpf_cache.sqlite" \
  localhost/usgs-alert:3.3

# QPF cache created?
ls -l "$(pwd)/usgs-data/qpf_cache.sqlite"

# JSON contains a qpf section per site?
jq '.rows[0].qpf // empty' "$(pwd)/usgs-site/gauges.json"

# HTML subtitle now includes "Rain: Today ..."
grep -i 'Rain:' "$(pwd)/usgs-site/index.html" | head


# Keep code + container in sync (nice touch)
 podman build -t localhost/usgs-alert:v3.1.0 .
 podman tag localhost/usgs-alert:v3.1.0 localhost/usgs-alert:stable

 Naming tips

Use semantic versions: MAJOR.MINOR.PATCH (e.g., v3.1.0).

Reserve -rc.1 if you want release candidates: v3.2.0-rc.1.

Optional niceties

Signed tag (if you use GPG): git tag -s v3.1.0 -m "…"

GitHub/Gitea release: after pushing, create a release from tag and attach your built image tar or artifacts.

Changelog discipline: keep a CHANGELOG.md; tag message should summarize user-visible changes.

# Current working version 10-29-2025
<p align="center">
 <img src="./working.10-29-2025.png"
</p>



