# Quick Start Guide

**Get your USGS River Monitoring System up and running in 5 minutes!**

---

## 🚀 Option 1: View Live Production (Instant!)

Just open your browser:

**🌐 Production Dashboard**: https://docker-blue-sound-1751.fly.dev/

That's it! The system is already running in the cloud.

---

## 🏠 Option 2: Run Locally (5 minutes)

### Prerequisites
- Podman or Docker installed
- Git clone of this repository

### Steps

**1. Navigate to the project**:
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
```

**2. Build the container**:
```bash
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

**3. Run it**:
```bash
podman run -d --name usgs-river \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  -v "$(pwd)/usgs-site":/site:Z \
  usgs-api:latest
```

**4. Wait 30 seconds** for initial data load

**5. Find your IP**:
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

**6. Access your dashboard**:
```
http://YOUR_IP:8080/
```

For example: http://192.168.1.168:8080/

**Note**: Use your machine's IP address, NOT `localhost`!

---

## 🔄 Option 3: Auto-Start on Boot (10 minutes)

Make it start automatically when your machine boots:

**1. Create systemd configuration**:
```bash
mkdir -p ~/.config/containers/systemd
cat > ~/.config/containers/systemd/usgs-alert.container << 'EOF'
[Unit]
Description=USGS River Alert System with Flask API
After=network-online.target

[Container]
Image=localhost/usgs-api:latest
Pull=never
PublishPort=8080:8080

Environment=BIND_HOST=0.0.0.0
Environment=RUN_INTERVAL_SEC=60
Environment=NWS_UA=mdchansl-usgs-alert/1.0
Environment=NWS_CONTACT=michael.chanslor@gmail.com

Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data:/data:Z
Volume=/chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-site:/site:Z

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF
```

**2. Build the image** (if not done already):
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

**3. Enable auto-start**:
```bash
systemctl --user daemon-reload
systemctl --user enable --now usgs-alert.service
loginctl enable-linger "$USER"
```

**4. Check it's running**:
```bash
systemctl --user status usgs-alert.service
```

**Done!** It will now start automatically on boot.

---

## 📱 Using the API (ESP32/IoT)

Once running, you can fetch river data from your ESP32 or other devices:

**Health Check**:
```bash
curl http://YOUR_IP:8080/api/health
```

**All Rivers**:
```bash
curl http://YOUR_IP:8080/api/river-levels
```

**Specific River** (Little River Canyon):
```bash
curl http://YOUR_IP:8080/api/river-levels/02399200
```

**Response includes 5-line display format for OLED screens**:
```json
{
  "display_lines": [
    "Little River Canyon",
    "22 cfs -> steady",
    "QPF Today: 0.00\"",
    "Tom:0.00\" Day3:0.18\"",
    "Max:60F Wind:0.0 N"
  ]
}
```

See [API_README.md](API_README.md) for complete API documentation.

---

## 🛠️ Common Commands

### View Logs
```bash
# For manual container
podman logs -f usgs-river

# For systemd service
journalctl --user -u usgs-alert.service -f
```

### Stop/Restart
```bash
# Manual container
podman stop usgs-river
podman start usgs-river

# Systemd service
systemctl --user stop usgs-alert.service
systemctl --user start usgs-alert.service
systemctl --user restart usgs-alert.service
```

### Update to Latest Code
```bash
# 1. Pull latest code
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
git pull

# 2. Rebuild image
podman build -f Containerfile.api.simple -t usgs-api:latest .

# 3. Restart
# For manual container:
podman stop usgs-river && podman rm usgs-river
# Then run again (see Option 2 above)

# For systemd:
systemctl --user restart usgs-alert.service
```

---

## 🔍 Troubleshooting

### "River Monitor Starting..." - Nothing loads

**Cause**: Background worker is still fetching initial data

**Fix**: Wait 30-60 seconds and refresh the page

---

### Can't access on localhost

**Cause**: Container networking issue

**Fix**: Use your machine's IP address instead:
```bash
# Find your IP
ip addr show | grep "inet " | grep -v 127.0.0.1

# Access via IP
http://192.168.1.168:8080/
```

---

### Service won't start

**Check logs**:
```bash
journalctl --user -u usgs-alert.service -n 50
```

**Common issues**:
1. Image not built: Run `podman build` command
2. Port 8080 in use: Change port in systemd config
3. Volume permissions: Check directory exists and is writable

---

### Data not updating

**Check if worker is running**:
```bash
# View recent logs
journalctl --user -u usgs-alert.service -n 100 | grep -E "INFO|ERROR"
```

**Expected**: You should see `[INFO]` lines every 60 seconds

---

## 📚 More Documentation

- **[DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)** - Complete deployment guide
- **[API_README.md](API_README.md)** - API reference and ESP32 examples
- **[CLAUDE.md](CLAUDE.md)** - Full project documentation
- **[CONTAINERFILES.md](CONTAINERFILES.md)** - Container build options
- **[DOCS_INDEX.md](DOCS_INDEX.md)** - Documentation index

---

## ✅ Quick Health Check

Is everything working? Run this:

```bash
# Check service
systemctl --user status usgs-alert.service

# Check API
curl http://$(ip addr show | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | cut -d/ -f1):8080/api/health

# Should return:
# {"status": "ok", "timestamp": "..."}
```

If you see `"status": "ok"`, you're all set! 🎉

---

**Need help?** Check the troubleshooting section above or see [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)
