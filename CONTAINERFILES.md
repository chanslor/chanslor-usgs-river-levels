# Containerfile Documentation

This document describes all available Containerfiles in this project and their use cases.

## Production Containerfiles

### Containerfile (symlink) ⭐ DEFAULT

**Purpose**: Symlink to `Containerfile.api.simple` for convenient default builds

**Note:** `Containerfile` is a symbolic link, not a standalone file:
```
Containerfile -> Containerfile.api.simple
```

**Build:**
```bash
podman build -t usgs-api:latest .
```

This uses the production configuration by default.

---

### Containerfile.api.simple ⭐ CURRENT PRODUCTION

**Purpose**: Single-stage Ubuntu build with Flask API + Dashboard

**Features:**
- Base: Ubuntu 22.04
- Single-stage build (simple, fast)
- Flask REST API server
- Serves HTML dashboard at `/`
- Serves API endpoints at `/api/*`
- Background worker for data refresh
- Production-ready for Fly.io

**Build:**
```bash
podman build -f Containerfile.api.simple -t usgs-api:latest .
```

**Use Case:** Current production deployment on Fly.io

**Entry Point:** `/app/entrypoint-api.sh`

**Ports:** 8080 (Flask server)

**Volumes:**
- `/data` - Persistent SQLite databases and cache
- `/site` - Generated HTML/JSON output (optional, generated in container)

---

## Legacy/Alternative Containerfiles

### Containerfile.cloud

**Purpose**: Cloud-optimized multi-stage build

**Features:**
- Base: Alpine Linux
- Multi-stage build
- Optimized for Fly.io/cloud deployments
- Static HTML dashboard only
- No Flask API

**Build:**
```bash
podman build -f Containerfile.cloud -t usgs-cloud:latest .
```

**Use Case:** Cloud deployments before API integration

**Entry Point:** `/app/entrypoint.sh`

---

### Containerfile.cloud.api

**Purpose**: Cloud-optimized build WITH Flask API (Alpine base)

**Features:**
- Base: Alpine Linux
- Multi-stage build
- Flask REST API included
- Smaller image than Ubuntu-based builds

**Build:**
```bash
podman build -f Containerfile.cloud.api -t usgs-cloud-api:latest .
```

**Use Case:** Alternative to Containerfile.api.simple with smaller footprint

**Entry Point:** `/app/entrypoint-api.sh`

**Note:** May have Python compatibility issues compared to Ubuntu base

---

### Containerfile.ubuntu

**Purpose**: Ubuntu-based build (single-stage)

**Features:**
- Base: Ubuntu 22.04
- Simple single-stage build
- Good Python compatibility
- Larger image size

**Build:**
```bash
podman build -f Containerfile.ubuntu -t usgs-ubuntu:latest .
```

**Use Case:** Development/testing with full Ubuntu environment

**Entry Point:** `/app/entrypoint.sh`

---

## Comparison Matrix

| Containerfile | Base OS | Stages | Flask API | Image Size | Complexity | Production Ready |
|---------------|---------|--------|-----------|------------|------------|------------------|
| **Containerfile** (symlink) | Ubuntu 22.04 | Single | ✅ Yes | ~450MB | Low | ✅ **DEFAULT** |
| **Containerfile.api.simple** | Ubuntu 22.04 | Single | ✅ Yes | ~450MB | Low | ✅ **CURRENT** |
| Containerfile.cloud | Alpine | Multi | ❌ No | ~200MB | Medium | ✅ Yes |
| Containerfile.cloud.api | Alpine | Multi | ✅ Yes | ~250MB | Medium | ⚠️ Maybe |
| Containerfile.ubuntu | Ubuntu 22.04 | Single | ❌ No | ~400MB | Low | ✅ Yes |

**Note:** `Containerfile` is a symlink to `Containerfile.api.simple`, so they produce identical images.

---

## Choosing a Containerfile

### For Production (Fly.io)
**Use:** `Containerfile` (or `Containerfile.api.simple`)
- Default symlink points to production config
- Most reliable
- Full Python compatibility
- Flask API + Dashboard
- Currently deployed

### For Lightweight Deployments (No API)
**Use:** `Containerfile.cloud`
- Smaller footprint (Alpine base)
- Dashboard only
- No ESP32 API

### For Development/Testing
**Use:** `Containerfile.api.simple` or `Containerfile.ubuntu`
- Full Ubuntu environment
- Easy debugging
- Good package availability

### For Size-Constrained Deployments
**Use:** `Containerfile.cloud.api` (experimental)
- Alpine base
- Flask API included
- Test thoroughly before production

---

## Current Production Configuration

**File:** `fly.toml`

```toml
[build]
  dockerfile = "Containerfile.api.simple"
```

**Why this choice:**
- Ubuntu 22.04 has excellent Python compatibility
- Single-stage build is simple and maintainable
- Flask works reliably without Alpine quirks
- Image size is acceptable for Fly.io (512MB VM)
- Production-proven over multiple deployments

---

## Migration Notes

If migrating between Containerfiles:

1. **From static (Containerfile/Containerfile.cloud) to API (Containerfile.api.simple)**:
   - Add Flask dependencies
   - Switch entrypoint from `entrypoint.sh` to `entrypoint-api.sh`
   - Test API endpoints
   - Update documentation URLs

2. **From Alpine to Ubuntu**:
   - May need to rebuild Python wheels
   - Check for Alpine-specific package names
   - Image size will increase (~2x)
   - Better compatibility, easier debugging

3. **From Ubuntu to Alpine**:
   - Test all Python packages thoroughly
   - May need musl-dev for some packages
   - Image size will decrease
   - More complex troubleshooting

---

## Testing Locally

After building any Containerfile:

```bash
# Run the container
podman run -d --name test-container \
  -p 8080:8080 \
  -v "$(pwd)/usgs-data":/data:Z \
  localhost/your-image:latest

# Check logs
podman logs -f test-container

# Test endpoints
curl http://localhost:8080/
curl http://localhost:8080/api  # Only if using API-enabled Containerfile
```

---

## Dockerfile vs Containerfile

All files use the `Containerfile` naming convention (Podman/Buildah standard) but are fully compatible with Docker. If using Docker:

```bash
# Works with Docker too
docker build -f Containerfile.api.simple -t usgs-api:latest .
```
