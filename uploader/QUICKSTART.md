# Quick Start Guide

Get the snapshot uploader running in 5 minutes.

## Prerequisites

- Raspberry Pi / Orange Pi (or any Linux machine)
- Python 3.8 or higher
- Network access to your Reolink camera
- (Optional) AWS S3 account or other storage

## Installation

### Option 1: Automated Install (Recommended for Raspberry Pi)

```bash
cd snapshot-uploader
bash install-rpi.sh
```

This will:
- Install Python dependencies
- Optionally install boto3 for S3
- Create default directories
- Generate `.env` configuration file

### Option 2: Manual Install

```bash
cd snapshot-uploader

# Install dependencies
pip3 install -r requirements.txt

# For S3 support
pip3 install boto3

# Copy example config
cp .env.example .env
```

## Configuration

Edit the `.env` file:

```bash
nano .env
```

### Minimal Configuration (Filesystem Storage)

```bash
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=yourpassword
CAPTURE_INTERVAL=10
STORAGE_BACKEND=filesystem
LOCAL_STORAGE_PATH=./snapshots
```

### S3 Configuration

```bash
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=yourpassword
CAPTURE_INTERVAL=10
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET=camera-snapshots
S3_PREFIX=camera-1/
```

### HTTP Configuration

```bash
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=yourpassword
CAPTURE_INTERVAL=10
STORAGE_BACKEND=http
HTTP_UPLOAD_URL=https://your-server.com/api/snapshots
HTTP_AUTH_TOKEN=your-token
```

## Running

### Test Run (Foreground)

```bash
python3 uploader.py
```

You should see output like:
```
============================================================
Camera Snapshot Uploader Service
============================================================
2026-01-21 10:30:00 - INFO - Initialized filesystem backend: ./snapshots
2026-01-21 10:30:00 - INFO - Starting snapshot uploader service...
2026-01-21 10:30:00 - INFO - Health check server listening on port 8080
2026-01-21 10:30:01 - INFO - Successfully logged into camera
2026-01-21 10:30:01 - INFO - Capturing snapshot...
2026-01-21 10:30:02 - INFO - Uploading 1234567 bytes...
2026-01-21 10:30:02 - INFO - Saved to filesystem: ./snapshots/snapshot_20260121_103002.jpg
```

Press `Ctrl+C` to stop.

### Check Health Status

In another terminal:

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "running",
  "last_capture": "2026-01-21T10:30:45",
  "uptime_seconds": 45,
  "total_captures": 4,
  "total_uploads": 4,
  "failed_uploads": 0
}
```

### Install as System Service

For production use, install as a systemd service:

```bash
bash install-service.sh
```

Then manage with:

```bash
# Start service
sudo systemctl start snapshot-uploader

# Check status
sudo systemctl status snapshot-uploader

# View logs (follow mode)
sudo journalctl -u snapshot-uploader -f

# Stop service
sudo systemctl stop snapshot-uploader

# Restart service
sudo systemctl restart snapshot-uploader
```

## Docker Deployment

### Using Docker Compose

```bash
# Edit .env file
nano .env

# Start container
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
curl http://localhost:8080/health

# Stop
docker-compose down
```

### Manual Docker

```bash
# Build image
docker build -t snapshot-uploader .

# Run container
docker run -d \
  --name snapshot-uploader \
  --env-file .env \
  -p 8080:8080 \
  -v $(pwd)/snapshots:/app/snapshots \
  snapshot-uploader

# View logs
docker logs -f snapshot-uploader

# Stop
docker stop snapshot-uploader
```

## Verification

### Test Camera Connection

```bash
# Ping camera
ping 192.168.1.141

# Test HTTP API (replace IP and credentials)
curl "http://admin:password@192.168.1.141/api.cgi?cmd=GetDevInfo"
```

### Check Snapshots

#### Filesystem Backend
```bash
ls -lh snapshots/
```

#### S3 Backend
```bash
aws s3 ls s3://your-bucket/snapshots/
```

#### HTTP Backend
Check your server logs for incoming requests.

## Troubleshooting

### "Failed to login to camera"

- Check camera IP is correct: `ping <CAMERA_IP>`
- Verify username/password
- Try toggling `CAMERA_USE_HTTPS` setting
- Test camera web UI in browser

### "S3 upload error"

- Check AWS credentials
- Verify S3 bucket exists and is accessible
- Check IAM permissions (need `s3:PutObject`)
- Test with AWS CLI: `aws s3 ls s3://your-bucket`

### "High memory usage on Raspberry Pi"

- Use `filesystem` or `http` backend instead of S3 (boto3 adds overhead)
- Increase `CAPTURE_INTERVAL` to reduce frequency
- Monitor with: `htop` or `free -h`

### Service won't start

```bash
# Check service status
sudo systemctl status snapshot-uploader

# View full logs
sudo journalctl -u snapshot-uploader -n 50

# Verify .env file location
ls -la /home/pi/reolinkapipy/snapshot-uploader/.env

# Test manually
cd /home/pi/reolinkapipy/snapshot-uploader
python3 uploader.py
```

## Next Steps

### Connect ML Processing

Now that snapshots are being uploaded, set up your ML processing pipeline:

1. **S3 Backend**: Use AWS Lambda trigger or EC2 polling
2. **HTTP Backend**: Your server receives snapshots directly
3. **Filesystem Backend**: Use the parent `camera_capture.py` script to process images from the shared directory

### Example: S3 + Lambda Processing

```python
# lambda_function.py
import json
import boto3

def lambda_handler(event, context):
    s3 = boto3.client('s3')

    # Get snapshot info from S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Download snapshot
    response = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = response['Body'].read()

    # TODO: Add your ML processing here
    # - Send to OpenAI Vision API
    # - Run object detection model
    # - Store results in database

    return {'statusCode': 200, 'body': json.dumps('Processed')}
```

### Example: HTTP Backend Processing

```python
# server.py (Flask example)
from flask import Flask, request
import cv2
import numpy as np

app = Flask(__name__)

@app.route('/api/snapshots', methods=['POST'])
def receive_snapshot():
    # Get uploaded file
    file = request.files['file']
    image_bytes = file.read()

    # Convert to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # TODO: Process image
    # - Run ML model
    # - Extract features
    # - Store results

    return {'status': 'success'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## Monitoring

### Prometheus Metrics (Future Enhancement)

Consider adding Prometheus exporter for metrics:
- Capture rate
- Upload success rate
- Error rate
- Latency

### Simple Monitoring Script

```bash
#!/bin/bash
# check-uploader.sh

STATUS=$(curl -s http://localhost:8080/health | jq -r '.status')

if [ "$STATUS" != "running" ]; then
    echo "Service is not running!"
    sudo systemctl restart snapshot-uploader
fi
```

Add to crontab:
```bash
crontab -e
# Add line:
*/5 * * * * /home/pi/check-uploader.sh
```

## Support

- See [README.md](README.md) for detailed documentation
- See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Report issues on GitHub
