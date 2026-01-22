# Snapshot Uploader - Documentation Index

Welcome! This directory contains a complete, production-ready service for capturing and uploading camera snapshots from resource-constrained devices.

## 📚 Documentation Guide

### Getting Started (Read in Order)

1. **[README.md](README.md)** - Start here!
   - Overview and features
   - Installation instructions
   - Configuration options
   - Basic usage examples

2. **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
   - Quick installation steps
   - Minimal configuration
   - Running the service
   - Common troubleshooting

3. **[COMPARISON.md](COMPARISON.md)** - Choose the right tool
   - snapshot-uploader vs camera_capture.py
   - When to use which
   - Performance comparison
   - Cost analysis

### Deep Dive Documentation

4. **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design
   - Component architecture
   - Data flow diagrams
   - Design decisions
   - Performance characteristics

5. **[INTEGRATION.md](INTEGRATION.md)** - Connect to processing
   - S3 + Lambda pattern
   - HTTP + Flask pattern
   - Filesystem + polling pattern
   - Complete code examples

### Reference Materials

6. **[requirements.txt](requirements.txt)** - Python dependencies
7. **[.env.example](.env.example)** - Configuration template
8. **[Dockerfile](Dockerfile)** - Container image
9. **[docker-compose.yml](docker-compose.yml)** - Container orchestration

### Installation Scripts

10. **[install-rpi.sh](install-rpi.sh)** - Automated setup for Raspberry Pi
11. **[install-service.sh](install-service.sh)** - Systemd service installer

### Core Applications

12. **[uploader.py](uploader.py)** - Snapshot uploader (~400 lines)
13. **[stream_relay.py](stream_relay.py)** - Video stream relay (~350 lines)

### Video Streaming (NEW!)

14. **[STREAMING.md](STREAMING.md)** - Complete video streaming guide
    - RTSP republishing
    - HLS conversion
    - Segmented recording
    - Real-time processing

15. **[STREAMING_VS_SNAPSHOTS.md](STREAMING_VS_SNAPSHOTS.md)** - Choose the right approach
    - Decision tree
    - Cost comparison
    - Use case examples

## 🎯 Quick Navigation

### I want to...

#### Install on Raspberry Pi
→ [QUICKSTART.md](QUICKSTART.md) → Run `install-rpi.sh`

#### Deploy with Docker
→ [docker-compose.yml](docker-compose.yml) → `docker-compose up`

#### Stream video instead of snapshots
→ [STREAMING.md](STREAMING.md) → Use `stream_relay.py`

#### Choose between streaming and snapshots
→ [STREAMING_VS_SNAPSHOTS.md](STREAMING_VS_SNAPSHOTS.md)

#### Understand the architecture
→ [ARCHITECTURE.md](ARCHITECTURE.md)

#### Integrate with my processing pipeline
→ [INTEGRATION.md](INTEGRATION.md)

#### Compare with camera_capture.py
→ [COMPARISON.md](COMPARISON.md)

#### Configure for S3
→ [.env.example](.env.example) → Set `STORAGE_BACKEND=s3`

#### Configure for HTTP endpoint
→ [.env.example](.env.example) → Set `STORAGE_BACKEND=http`

#### Run as a systemd service
→ [install-service.sh](install-service.sh)

## 📊 Project Statistics

- **Total Lines of Documentation:** ~2,100 lines
- **Core Application Code:** ~400 lines (Python)
- **Installation Scripts:** ~100 lines (Bash)
- **Configuration Files:** ~50 lines
- **Docker Configuration:** ~50 lines
- **Total Project Size:** ~2,500 lines

## 🔑 Key Features

### Lightweight
- **Memory:** ~50-90 MB (vs 500+ MB for full processing)
- **CPU:** <1% idle, 5-10% during capture
- **Dependencies:** Just `requests` (+ optional `boto3`)

### Flexible Storage
- **S3/Cloud:** AWS S3, DigitalOcean Spaces, MinIO
- **Filesystem:** Local or network-attached storage
- **HTTP:** Custom endpoints, webhooks

### Production-Ready
- **Monitoring:** Built-in health check endpoint
- **Deployment:** Systemd service + Docker support
- **Reliability:** Auto-retry, error tracking
- **Logging:** Comprehensive logging to stdout/journal

### Easy Setup
- **Automated:** One-command installation
- **Documented:** Step-by-step guides
- **Tested:** Runs on Raspberry Pi, Orange Pi, Docker

## 🏗️ Architecture Overview

```
┌──────────────┐
│   Reolink    │  Camera captures images
│   Camera     │
└──────┬───────┘
       │ HTTP API
       ▼
┌──────────────────┐
│  Orange Pi/RPI   │  Lightweight capture service
│  ┌────────────┐  │  - Minimal dependencies
│  │ uploader.py│  │  - Low power consumption
│  │ (~50MB RAM)│  │  - Systemd service
│  └─────┬──────┘  │
└────────┼─────────┘
         │
         ▼
┌────────────────────┐
│  Storage Backend   │  Choose your storage
│  ┌──────────────┐  │
│  │ • S3         │  │  Cloud storage
│  │ • Filesystem │  │  Local/NAS storage
│  │ • HTTP POST  │  │  Custom endpoint
│  └──────┬───────┘  │
└─────────┼──────────┘
          │
          ▼
┌─────────────────────┐
│  Processing Server  │  Your ML pipeline
│  ┌───────────────┐  │
│  │ • Fisheye     │  │  (Runs separately)
│  │   unwarp      │  │
│  │ • OpenAI API  │  │
│  │ • Analysis    │  │
│  └───────────────┘  │
└─────────────────────┘
```

## 🚀 Deployment Scenarios

### Scenario 1: Single Camera, Home User
**Hardware:** Raspberry Pi 4 + Camera
**Storage:** Filesystem (local)
**Processing:** On-demand via laptop
**Cost:** $50 one-time, $2/month power

### Scenario 2: Multiple Cameras, Small Business
**Hardware:** 3x Orange Pi Zero 2 + Cameras
**Storage:** S3 bucket
**Processing:** AWS Lambda triggered
**Cost:** $150 one-time, $10/month cloud

### Scenario 3: Research Lab, Many Cameras
**Hardware:** 10x Raspberry Pi + Cameras
**Storage:** S3 bucket
**Processing:** EC2 server with GPU
**Cost:** $500 one-time, $50/month cloud

## 🔧 Configuration Examples

### Minimal (Filesystem)
```bash
CAMERA_IP=192.168.1.141
STORAGE_BACKEND=filesystem
CAPTURE_INTERVAL=10
```

### Production (S3)
```bash
CAMERA_IP=192.168.1.141
STORAGE_BACKEND=s3
S3_BUCKET=camera-snapshots
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
CAPTURE_INTERVAL=10
```

### Custom Server (HTTP)
```bash
CAMERA_IP=192.168.1.141
STORAGE_BACKEND=http
HTTP_UPLOAD_URL=https://myserver.com/api/snapshots
HTTP_AUTH_TOKEN=secret
CAPTURE_INTERVAL=10
```

## 📈 Performance Characteristics

| Metric | Value |
|--------|-------|
| Capture Latency | 1-2 seconds |
| Upload Latency (S3) | 1-3 seconds |
| Upload Latency (HTTP) | 0.5-2 seconds |
| Memory Usage | 50-90 MB |
| CPU Usage (idle) | <1% |
| CPU Usage (capture) | 5-10% |
| Power Consumption | ~2W |
| Max Capture Rate | ~1 per second |

## 🐛 Troubleshooting

### Quick Checks
```bash
# Is the service running?
sudo systemctl status snapshot-uploader

# Can we reach the camera?
ping 192.168.1.141

# Is the health endpoint responding?
curl http://localhost:8080/health

# What are the logs saying?
sudo journalctl -u snapshot-uploader -f
```

### Common Issues
1. **Can't connect to camera** → Check IP, credentials, HTTPS setting
2. **S3 upload fails** → Verify AWS credentials and bucket permissions
3. **High memory usage** → Use HTTP/filesystem backend instead of S3
4. **Service won't start** → Check .env file location and permissions

## 🤝 Contributing

Improvements welcome! Consider:
- Additional storage backends (FTP, SFTP, WebDAV)
- Compression before upload
- Motion detection filtering
- Multiple camera support in single process
- Metrics export (Prometheus)

## 📄 License

Same as parent project - see [LICENSE.md](../LICENSE.md)

## 🔗 Related Projects

- **Parent Repo:** [reolinkapipy](../)
- **Full Processing Script:** [camera_capture.py](../camera_capture.py)
- **Session Viewer:** [session_viewer.py](../session_viewer.py)

## 📮 Support

- Issues: [GitHub Issues](https://github.com/ReolinkCameraAPI/reolinkapipy/issues)
- Docs: This directory
- Discord: https://discord.gg/8z3fdAmZJP

---

**Ready to get started?** → [QUICKSTART.md](QUICKSTART.md)
