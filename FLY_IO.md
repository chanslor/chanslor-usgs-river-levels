# Fly.io Deployment Guide

Complete reference for deploying and managing the USGS River Monitoring application on Fly.io.

## Quick Reference

| Item | Value |
|------|-------|
| App Name | `docker-blue-sound-1751` |
| URL | https://docker-blue-sound-1751.fly.dev/ |
| Region | Dallas (dfw) |
| Machine Size | 512MB RAM, shared CPU |
| Volume | `usgs_data` (1GB) mounted at `/data` |

## Basic Commands

### Check App Status

```bash
# View app overview and machine status
fly status -a docker-blue-sound-1751

# View running machines with details
fly machine list -a docker-blue-sound-1751

# Check specific machine status
fly machine status <machine_id> -a docker-blue-sound-1751
```

### View Logs

```bash
# Stream live logs
fly logs -a docker-blue-sound-1751

# View recent logs (last 100 lines)
fly logs -a docker-blue-sound-1751 | tail -100
```

### Deploy

```bash
# Standard deployment (builds locally, pushes to Fly registry)
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only

# Or use the deploy script
./deploy.sh
```

### Health Check

```bash
# Check API health endpoint
curl -s https://docker-blue-sound-1751.fly.dev/api/health

# Expected response:
# {"status":"ok","timestamp":"2026-01-05T01:49:24.466340Z"}
```

### SSH Access

```bash
# Interactive shell
fly ssh console -a docker-blue-sound-1751

# Run single command
fly ssh console -a docker-blue-sound-1751 -C "ls -la /data/"

# Check disk usage
fly ssh console -a docker-blue-sound-1751 -C "df -h"

# View SQLite database files
fly ssh console -a docker-blue-sound-1751 -C "ls -lh /data/*.sqlite"
```

## Machine Management

### Stop/Start/Restart

```bash
# Stop a machine
fly machine stop <machine_id> -a docker-blue-sound-1751

# Start a stopped machine
fly machine start <machine_id> -a docker-blue-sound-1751

# Restart a machine (stop + start)
fly machine restart <machine_id> -a docker-blue-sound-1751
```

### Destroy Machine

```bash
# Graceful destroy (waits for machine to stop)
fly machine destroy <machine_id> -a docker-blue-sound-1751

# Force destroy (immediate)
fly machine destroy <machine_id> -a docker-blue-sound-1751 --force
```

### Update Machine Configuration

```bash
# Update machine settings (memory, CPU, etc.)
fly machine update <machine_id> -a docker-blue-sound-1751 --memory 512
```

## Volume Management

### List Volumes

```bash
fly volumes list -a docker-blue-sound-1751

# Example output:
# ID                    STATE    NAME       SIZE  REGION  ATTACHED VM
# vol_rn8e3d7ln3nnnder  created  usgs_data  1GB   dfw     48edde4b217758
```

### Create New Volume

```bash
# Create 1GB volume in specific region
fly volumes create usgs_data --region dfw --size 1 -a docker-blue-sound-1751
```

### Fork Volume (Copy to New Region)

```bash
# Fork existing volume to a new region (preserves all data)
fly volumes fork <volume_id> -r <new_region> -n <volume_name> -a docker-blue-sound-1751

# Example: Fork from iad to dfw
fly volumes fork vol_re871j01pokqojor -r dfw -n usgs_data -a docker-blue-sound-1751
```

### Delete Volume

```bash
# Delete a volume (WARNING: destroys all data)
fly volumes delete <volume_id> -a docker-blue-sound-1751 -y
```

### Extend Volume Size

```bash
fly volumes extend <volume_id> --size 2 -a docker-blue-sound-1751
```

## Region Management

### List Available Regions

```bash
fly platform regions
```

### Common Regions

| Code | Location | Notes |
|------|----------|-------|
| `iad` | Ashburn, Virginia | US East (frequently has capacity issues) |
| `dfw` | Dallas, Texas | US Central (current production) |
| `ord` | Chicago, Illinois | US Central alternative |
| `lax` | Los Angeles, California | US West |
| `sea` | Seattle, Washington | US Northwest |
| `atl` | Atlanta, Georgia | US Southeast |

### Change Primary Region

Edit `fly.toml`:
```toml
primary_region = 'dfw'
```

## Region Migration Procedure

Complete procedure for migrating to a new region while preserving data:

### Step 1: Fork the Volume

```bash
# List current volumes to get the volume ID
fly volumes list -a docker-blue-sound-1751

# Fork to new region (e.g., dfw)
fly volumes fork <old_volume_id> -r dfw -n usgs_data -a docker-blue-sound-1751
```

### Step 2: Update fly.toml

```bash
# Edit fly.toml and change primary_region
# primary_region = 'dfw'
```

### Step 3: Stop and Destroy Old Machine

```bash
# Get machine ID
fly machine list -a docker-blue-sound-1751

# Stop the old machine
fly machine stop <machine_id> -a docker-blue-sound-1751

# Destroy the old machine
fly machine destroy <machine_id> -a docker-blue-sound-1751 --force
```

### Step 4: Deploy to New Region

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only
```

### Step 5: Verify Migration

```bash
# Check new machine is running in correct region
fly status -a docker-blue-sound-1751

# Verify data is intact
fly ssh console -a docker-blue-sound-1751 -C "ls -la /data/"

# Test health endpoint
curl -s https://docker-blue-sound-1751.fly.dev/api/health
```

### Step 6: Cleanup Old Volume

```bash
# List volumes to confirm old one is not attached
fly volumes list -a docker-blue-sound-1751

# Delete old volume in previous region
fly volumes delete <old_volume_id> -a docker-blue-sound-1751 -y
```

## Secrets Management

```bash
# List secrets (names only, not values)
fly secrets list -a docker-blue-sound-1751

# Set a secret
fly secrets set SECRET_NAME=value -a docker-blue-sound-1751

# Remove a secret
fly secrets unset SECRET_NAME -a docker-blue-sound-1751
```

## Configuration (fly.toml)

Current production configuration:

```toml
app = 'docker-blue-sound-1751'
primary_region = 'dfw'

[build]
  dockerfile = "Containerfile.api.simple"

[env]
  RUN_INTERVAL_SEC = "60"
  NWS_UA = "mdchansl-usgs-alert/1.0"
  QPF_TTL_HOURS = "3"
  QPF_CACHE = "/data/qpf_cache.sqlite"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

[mounts]
  source = "usgs_data"
  destination = "/data"

[[vm]]
  memory = '512mb'
  cpu_kind = 'shared'
  cpus = 1
```

## Troubleshooting

### "Insufficient Memory" Error

**Symptoms:**
```
Error: failed to update VM: aborted: could not reserve resource for machine:
insufficient memory available to fulfill request
```

**Solution:**
The region is oversubscribed. Migrate to a different region:

```bash
# 1. Fork volume to new region
fly volumes fork <volume_id> -r dfw -n usgs_data -a docker-blue-sound-1751

# 2. Update fly.toml primary_region

# 3. Stop and destroy old machine
fly machine stop <machine_id> -a docker-blue-sound-1751
fly machine destroy <machine_id> -a docker-blue-sound-1751 --force

# 4. Deploy fresh
fly deploy -a docker-blue-sound-1751 --local-only

# 5. Delete old volume
fly volumes delete <old_volume_id> -a docker-blue-sound-1751 -y
```

### "Volume Not Found in Region" Error

**Symptoms:**
```
Error: could not find a volume named 'usgs_data' in region 'xyz'
```

**Solution:**
Volumes are region-specific. Create or fork a volume in the target region:

```bash
# Fork existing volume to new region
fly volumes fork <existing_volume_id> -r <target_region> -n usgs_data -a docker-blue-sound-1751

# Or create new empty volume
fly volumes create usgs_data --region <target_region> --size 1 -a docker-blue-sound-1751
```

### App Not Responding After Deploy

**Symptoms:**
- Deploy succeeds but app returns 502/503 errors
- Health check fails

**Debugging:**

```bash
# Check machine status
fly status -a docker-blue-sound-1751

# View recent logs for errors
fly logs -a docker-blue-sound-1751

# Check if app is listening on correct port
fly ssh console -a docker-blue-sound-1751 -C "ss -tlnp"

# Restart machine
fly machine restart <machine_id> -a docker-blue-sound-1751
```

### Cache Issues (Data Not Updating)

**Symptoms:**
- Dashboard shows old data after code changes
- Drought/QPF data seems stale

**Solution:**
Clear the relevant cache and restart:

```bash
# Clear specific cache
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/drought_cache.sqlite"
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/qpf_cache.sqlite"
fly ssh console -a docker-blue-sound-1751 -C "rm -f /data/aqi_cache.sqlite"

# Restart machine to fetch fresh data
fly machine restart <machine_id> -a docker-blue-sound-1751
```

### Containerfile Not Found

**Symptoms:**
```
Error: dockerfile '/home/mdc/Containerfile.api.simple' not found
```

**Solution:**
Run deploy from the correct directory:

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker
fly deploy -a docker-blue-sound-1751 --local-only
```

Or use the deploy script which handles directory:
```bash
./deploy.sh
```

## Monitoring Dashboard

Access the Fly.io monitoring dashboard:
```
https://fly.io/apps/docker-blue-sound-1751/monitoring
```

Features:
- Real-time machine metrics (CPU, memory, network)
- Request logs and latency
- Health check status
- Deployment history

## Cost Management

```bash
# View app resource usage
fly scale show -a docker-blue-sound-1751

# View billing information
fly billing show
```

Current configuration costs:
- 1x shared-cpu-1x machine (512MB): ~$1.94/month
- 1GB volume: ~$0.15/month
- **Total**: ~$2.09/month (within free tier allowance)

## Useful Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Quick status check
alias flystat='fly status -a docker-blue-sound-1751'

# Quick log view
alias flylogs='fly logs -a docker-blue-sound-1751'

# Quick deploy
alias flydeploy='cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker && fly deploy -a docker-blue-sound-1751 --local-only'

# Quick SSH
alias flyssh='fly ssh console -a docker-blue-sound-1751'

# Quick health check
alias flyhealth='curl -s https://docker-blue-sound-1751.fly.dev/api/health | python3 -m json.tool'
```

## Database Sync (Fly.io → Local)

Sync production databases from Fly.io to your local machine for backup or analysis.

### Compare Local vs Fly.io

```bash
# Check local database files
ls -lh /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data/*.sqlite

# Check Fly.io database files
fly ssh console -a docker-blue-sound-1751 -C "ls -lh /data/"
```

### Download All Databases

**Step 1: Backup existing local files**
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data

# Backup existing files (if they exist)
mv rainfall_history.sqlite rainfall_history.sqlite.bak 2>/dev/null
mv tva_history.sqlite tva_history.sqlite.bak 2>/dev/null
mv paddle_log.sqlite paddle_log.sqlite.bak 2>/dev/null
mv state.sqlite state.sqlite.bak 2>/dev/null
```

**Step 2: Download from Fly.io**
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data

# Download each database (fly ssh sftp won't overwrite existing files)
fly ssh sftp get /data/rainfall_history.sqlite rainfall_history.sqlite -a docker-blue-sound-1751
fly ssh sftp get /data/tva_history.sqlite tva_history.sqlite -a docker-blue-sound-1751
fly ssh sftp get /data/paddle_log.sqlite paddle_log.sqlite -a docker-blue-sound-1751
fly ssh sftp get /data/state.sqlite state.sqlite -a docker-blue-sound-1751
```

**Step 3: Verify download**
```bash
ls -lh /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data/*.sqlite
```

**Step 4: Clean up backups (optional)**
```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data
rm -f *.sqlite.bak
```

### Download Single Database

```bash
cd /chanslor/mdc/YOUTUBE/chanslor-usgs-river-levels/docker/usgs-data

# Example: Download just paddle_log.sqlite
fly ssh sftp get /data/paddle_log.sqlite paddle_log.sqlite -a docker-blue-sound-1751
```

### Important Notes

- `fly ssh sftp get` will **not overwrite** existing files (safety feature)
- You must backup/remove existing files before downloading
- Cache files (qpf_cache, drought_cache, aqi_cache) typically don't need syncing
- Production data grows over time; local copies become stale quickly

### Query Synced Databases

```bash
# Check rainfall history stats
sqlite3 usgs-data/rainfall_history.sqlite "SELECT river_name, COUNT(*) FROM daily_rainfall GROUP BY river_name;"

# Check TVA history date range
sqlite3 usgs-data/tva_history.sqlite "SELECT site_code, MIN(timestamp), MAX(timestamp) FROM observations GROUP BY site_code;"

# Check paddle log entries
sqlite3 usgs-data/paddle_log.sqlite "SELECT * FROM paddle_events ORDER BY paddle_date DESC LIMIT 10;"
```

## Data Files on Volume

Files stored in `/data/` (persistent across deployments):

| File | Purpose | Size |
|------|---------|------|
| `state.sqlite` | Alert state, StreamBeam history | ~114KB |
| `rainfall_history.sqlite` | Historical rainfall data | ~3.3MB |
| `tva_history.sqlite` | TVA dam observations | ~256KB |
| `paddle_log.sqlite` | Paddle event tracking | ~20KB |
| `qpf_cache.sqlite` | QPF forecast cache (3h TTL) | ~12KB |
| `drought_cache.sqlite` | Drought data cache (12h TTL) | ~12KB |
| `aqi_cache.sqlite` | Air quality cache (1h TTL) | ~12KB |

## Migration History

| Date | From | To | Reason |
|------|------|-----|--------|
| 2026-01-05 | iad (Virginia) | dfw (Dallas) | Persistent "insufficient memory" errors in iad |

---

*Last Updated: 2026-01-05*
