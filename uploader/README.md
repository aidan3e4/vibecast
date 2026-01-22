# Snapshot Uploader Service

A lightweight service designed to run on resource-constrained devices (Raspberry Pi, Orange Pi) for capturing camera snapshots and uploading them to remote storage for later ML processing.

## Architecture

This service is designed to decouple image capture from ML processing:

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Reolink Camera │────▶│ Snapshot     │────▶│ S3 / Remote     │
│                 │     │ Uploader     │     │ Storage         │
│                 │     │ (Orange Pi)  │     │                 │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ ML Processing   │
                                               │ Server          │
                                               └─────────────────┘
```

## Features

### Snapshot Uploader (uploader.py)
- **Lightweight**: Minimal dependencies for running on low-power devices
- **Multiple storage backends**: S3, local filesystem, HTTP POST
- **Configurable intervals**: Capture snapshots at specified intervals
- **Health monitoring**: Built-in health check endpoint
- **Error resilience**: Automatic retry with exponential backoff
- **Low memory footprint**: Optimized for devices with limited RAM

### Video Stream Relay (stream_relay.py) - NEW!
- **RTSP republishing**: Forward video stream to central RTSP server
- **HLS conversion**: Convert to HTTP Live Streaming for web browsers
- **Segmented recording**: Save video in chunks for batch processing
- **Zero re-encoding**: Copy streams directly (minimal CPU usage)
- **Real-time monitoring**: Continuous video instead of periodic snapshots

**See [STREAMING.md](STREAMING.md) for video streaming guide**

## Requirements

Minimal dependencies for Raspberry Pi / Orange Pi:

```
python >= 3.8
requests >= 2.28
boto3 (only if using S3)
```

## Installation

### On Raspberry Pi / Orange Pi

```bash
# Install Python and pip
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Clone the repo (or copy just the snapshot-uploader folder)
git clone https://github.com/yourusername/reolinkapipy.git
cd reolinkapipy/snapshot-uploader

# Install dependencies (minimal install)
pip3 install -r requirements.txt

# For S3 support (optional)
pip3 install boto3
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# Camera settings
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=yourpassword
CAMERA_USE_HTTPS=false

# Capture settings
CAPTURE_INTERVAL=10  # seconds between snapshots

# Storage backend: "s3", "filesystem", or "http"
STORAGE_BACKEND=s3

# S3 Configuration (if STORAGE_BACKEND=s3)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
S3_BUCKET=camera-snapshots
S3_PREFIX=snapshots/

# Filesystem Configuration (if STORAGE_BACKEND=filesystem)
LOCAL_STORAGE_PATH=/mnt/storage/snapshots

# HTTP Configuration (if STORAGE_BACKEND=http)
HTTP_UPLOAD_URL=https://your-server.com/api/snapshots
HTTP_AUTH_TOKEN=your-auth-token

# Health check settings
HEALTH_CHECK_PORT=8080
```

## Usage

### Run as a foreground service

```bash
python3 uploader.py
```

### Run as a systemd service (recommended for production)

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/snapshot-uploader.service
```

2. Add the following content:

```ini
[Unit]
Description=Camera Snapshot Uploader
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/reolinkapipy/snapshot-uploader
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /home/pi/reolinkapipy/snapshot-uploader/uploader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl enable snapshot-uploader
sudo systemctl start snapshot-uploader
sudo systemctl status snapshot-uploader
```

4. View logs:

```bash
sudo journalctl -u snapshot-uploader -f
```

## Health Check

The service exposes a health check endpoint on the configured port (default 8080):

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "last_capture": "2026-01-21T10:30:45",
  "uptime_seconds": 3600,
  "total_captures": 360,
  "total_uploads": 358,
  "failed_uploads": 2
}
```

## Storage Backends

### S3 Backend

Uploads snapshots to AWS S3 or S3-compatible storage (MinIO, DigitalOcean Spaces, etc.).

**Benefits**:
- Scalable storage
- Easy integration with cloud ML services
- Built-in redundancy

### Filesystem Backend

Saves snapshots to local or network-attached storage.

**Benefits**:
- No cloud costs
- Works offline
- Simple setup

### HTTP Backend

Posts snapshots to a custom HTTP endpoint.

**Benefits**:
- Maximum flexibility
- Direct integration with your processing server
- Custom authentication

## Performance Tips for Raspberry Pi

1. **Use SD card wisely**: If using filesystem backend, consider using an external USB drive to reduce SD card wear
2. **Optimize capture interval**: Balance between freshness and resource usage (10-30 seconds is usually good)
3. **Monitor temperature**: Use `vcgencmd measure_temp` to ensure Pi doesn't overheat
4. **Use lightweight backend**: S3 SDK adds overhead; consider HTTP backend for minimal resource usage

## Troubleshooting

### Camera connection fails

```bash
# Test camera connectivity
ping 192.168.1.141

# Test camera HTTP API
curl http://192.168.1.141/api.cgi?cmd=GetDevInfo

# Check credentials in .env file
```

### S3 upload fails

```bash
# Test AWS credentials
aws s3 ls s3://your-bucket/

# Check IAM permissions (need s3:PutObject)
```

### High memory usage

- Reduce `CAPTURE_INTERVAL` if accumulating images in memory
- Use HTTP backend instead of S3 (boto3 adds overhead)
- Restart service periodically if needed

## Development

### Testing locally

```bash
# Use filesystem backend for testing
export STORAGE_BACKEND=filesystem
export LOCAL_STORAGE_PATH=./test-snapshots
python3 uploader.py
```

### Simulating failures

```bash
# Test retry logic
export CAMERA_IP=192.168.1.999  # Invalid IP
python3 uploader.py
```

## License

Same as parent project (see LICENSE.md in root)
