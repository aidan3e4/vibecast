# Architecture Documentation

## Design Philosophy

This service is designed with the following principles:

1. **Separation of Concerns**: Decouple image capture from ML processing
2. **Resource Efficiency**: Minimal dependencies and memory footprint for edge devices
3. **Flexibility**: Support multiple storage backends
4. **Reliability**: Built-in health monitoring and error recovery

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Reolink Camera                          │
│                   (192.168.1.x)                             │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP API
                         │ (Snapshot endpoint)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Snapshot Uploader Service                       │
│                  (Raspberry Pi / Orange Pi)                  │
│                                                              │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐   │
│  │ Camera       │───▶│  Storage    │───▶│  Backend     │   │
│  │ Client       │    │  Manager    │    │  Adapter     │   │
│  └──────────────┘    └─────────────┘    └──────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │        Health Check Server (Port 8080)               │   │
│  │        - Status monitoring                           │   │
│  │        - Statistics endpoint                         │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Upload
                         ▼
        ┌────────────────┴────────────────┐
        │                                  │
        ▼                                  ▼
┌───────────────┐              ┌────────────────────┐
│  S3 / Cloud   │              │  HTTP Endpoint     │
│  Storage      │              │  (Your Server)     │
└───────┬───────┘              └─────────┬──────────┘
        │                                 │
        │                                 │
        └────────────┬────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   ML Processing        │
        │   Server / Pipeline    │
        │   - Image analysis     │
        │   - Object detection   │
        │   - Fisheye unwarp     │
        └────────────────────────┘
```

## Components

### 1. Camera Client (`CameraClient`)

**Responsibility**: Communicate with Reolink camera API

**Key Features**:
- Lightweight HTTP client using `requests` library
- Session management with token-based authentication
- Automatic re-login on authentication failures
- Direct snapshot capture without unnecessary dependencies

**Methods**:
- `login()`: Authenticate with camera
- `get_snapshot()`: Capture JPEG image

**Design Decisions**:
- Uses camera's native HTTP API instead of the full `reolinkapi` library to reduce dependencies
- Implements only what's needed for snapshot capture
- No video streaming or complex camera control

### 2. Storage Backend (Abstract)

**Responsibility**: Upload captured snapshots to remote storage

**Implemented Backends**:

#### a. S3Backend
- **Use Case**: Cloud storage (AWS S3, DigitalOcean Spaces, MinIO)
- **Dependencies**: `boto3` (optional, only installed if needed)
- **Configuration**: Bucket name, prefix, region, credentials
- **Best For**: Scalable cloud deployments, integration with AWS services

#### b. FilesystemBackend
- **Use Case**: Local or network-attached storage
- **Dependencies**: None (stdlib only)
- **Configuration**: Base directory path
- **Best For**: Development, offline operation, NAS integration

#### c. HTTPBackend
- **Use Case**: Custom endpoints, webhooks
- **Dependencies**: `requests` (already required)
- **Configuration**: URL, optional auth token
- **Best For**: Direct integration with processing servers, minimal overhead

### 3. Snapshot Uploader (`SnapshotUploader`)

**Responsibility**: Main service orchestration

**Key Features**:
- Configurable capture intervals
- Statistics tracking
- Health monitoring
- Graceful shutdown handling

**Statistics Tracked**:
- Total captures
- Successful uploads
- Failed uploads
- Last capture timestamp
- Uptime

### 4. Health Check Server

**Responsibility**: Monitoring and observability

**Endpoints**:
- `GET /health`: Returns JSON with service status and statistics

**Use Cases**:
- Monitoring tools (Prometheus, Nagios, etc.)
- Load balancer health checks
- Manual service verification

**Example Response**:
```json
{
  "status": "running",
  "last_capture": "2026-01-21T10:30:45",
  "uptime_seconds": 3600,
  "total_captures": 360,
  "total_uploads": 358,
  "failed_uploads": 2
}
```

## Data Flow

### Capture and Upload Cycle

```
1. Timer triggers (every N seconds)
   │
   ├─▶ Generate timestamp
   │
   ├─▶ Call camera.get_snapshot()
   │   │
   │   ├─▶ Check authentication token
   │   │   └─▶ Login if needed
   │   │
   │   ├─▶ HTTP GET to camera /cgi-bin/api.cgi?cmd=Snap
   │   │
   │   └─▶ Return JPEG bytes
   │
   ├─▶ Create filename: snapshot_YYYYMMDD_HHMMSS.jpg
   │
   ├─▶ Call backend.upload(image_bytes, filename)
   │   │
   │   ├─▶ [S3Backend] Put object to S3
   │   ├─▶ [FilesystemBackend] Write to disk
   │   └─▶ [HTTPBackend] POST to endpoint
   │
   ├─▶ Update statistics
   │   ├─▶ Increment total_captures
   │   ├─▶ Increment total_uploads (if success)
   │   └─▶ Increment failed_uploads (if failure)
   │
   └─▶ Sleep until next interval
```

## Performance Characteristics

### Resource Usage (Raspberry Pi 3/4)

| Metric | Value |
|--------|-------|
| Memory (baseline) | ~30-50 MB |
| Memory (with boto3) | ~70-90 MB |
| CPU (idle) | < 1% |
| CPU (capture) | 5-10% |
| Network (per capture) | ~500 KB - 2 MB |

### Optimization Strategies

1. **Minimal Dependencies**: Only `requests` is required; `boto3` is optional
2. **No Image Processing**: Raw JPEG bytes are uploaded without modification
3. **Lazy Imports**: Optional dependencies only imported when needed
4. **Efficient Memory Usage**: Images are captured and uploaded without storing in memory longer than necessary
5. **No Threading for Uploads**: Simple sequential operation reduces complexity

## Configuration Strategy

### Environment Variables

All configuration via environment variables for:
- Easy container deployment
- Systemd service integration
- No code changes needed for different deployments

### Configuration Precedence

1. Environment variables (highest priority)
2. `.env` file
3. Default values (lowest priority)

## Error Handling

### Camera Connection Errors
- Automatic retry with re-login
- Logged but non-fatal (service continues)

### Upload Errors
- Logged and tracked in statistics
- Service continues to next capture
- No automatic retry (prevents backup/memory issues)

### Fatal Errors
- Missing required configuration
- Invalid storage backend
- Service exits with error code

## Deployment Models

### 1. Standalone Service (Raspberry Pi)

```
[Raspberry Pi]
   ├─ Snapshot Uploader (systemd service)
   ├─ Network connection to camera
   └─ Network connection to storage/server
```

**Benefits**:
- Dedicated hardware
- Runs 24/7
- Low power consumption

### 2. Containerized (Docker)

```
[Docker Host]
   └─ Container: snapshot-uploader
      ├─ Environment variables
      └─ Volume mount (for filesystem backend)
```

**Benefits**:
- Portable deployment
- Easy updates
- Resource isolation

### 3. Multiple Cameras

```
[Raspberry Pi]
   ├─ Service Instance 1 (Camera A, Port 8080)
   ├─ Service Instance 2 (Camera B, Port 8081)
   └─ Service Instance 3 (Camera C, Port 8082)
```

**Benefits**:
- Single device, multiple cameras
- Separate configurations
- Independent health monitoring

## Security Considerations

### Camera Communication
- Credentials stored in environment variables (not in code)
- SSL verification disabled for local cameras (common self-signed certs)
- Token-based authentication

### Storage
- S3: IAM credentials with least privilege (s3:PutObject only)
- HTTP: Bearer token authentication
- Filesystem: Unix permissions on output directory

### Network
- Camera should be on isolated VLAN if possible
- Health check server binds to 0.0.0.0 (consider firewall rules)

## Comparison with Original camera_capture.py

| Feature | camera_capture.py | snapshot-uploader |
|---------|-------------------|-------------------|
| Purpose | ML processing + capture | Capture + upload only |
| Dependencies | OpenCV, NumPy, OpenAI | requests (+ optional boto3) |
| Image Processing | Fisheye unwarp, multi-view | None (raw JPEG) |
| ML Integration | Direct OpenAI API calls | None (deferred to server) |
| Target Hardware | Desktop/Laptop | Raspberry Pi / Orange Pi |
| Memory Footprint | High (~500MB+) | Low (~50MB) |
| Storage | Local filesystem | Multiple backends |
| Deployment | Local script | Systemd service |

## Future Extensions

Potential enhancements without compromising lightweight design:

1. **Compression**: Optional on-device JPEG quality reduction
2. **Buffering**: Queue failed uploads for retry (with max buffer size)
3. **Multiple Cameras**: Single service managing multiple camera sources
4. **Metadata**: Embed timestamp/location in EXIF data
5. **Pre-filtering**: Basic motion detection to avoid uploading empty frames
6. **Edge Processing**: Optional lightweight preprocessing (resize, crop) before upload
