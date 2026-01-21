# Video Streaming Guide

Instead of uploading snapshots, you can stream the entire video feed. This guide shows different approaches.

## Why Stream Instead of Snapshots?

### Advantages of Streaming
- ✅ **Continuous monitoring** - No gaps between snapshots
- ✅ **Lower latency** - Real-time video processing
- ✅ **More efficient** - No repeated camera requests
- ✅ **Better for motion** - Capture fast-moving objects
- ✅ **Original framerate** - Full 15-30 FPS instead of 1 per N seconds

### Disadvantages of Streaming
- ❌ **Higher bandwidth** - Constant ~1-5 Mbps vs sporadic KB
- ❌ **More storage** - Video files are large
- ❌ **More complex** - Requires video processing infrastructure
- ❌ **Higher CPU** - Continuous encoding/decoding

## Streaming Approaches

### Approach 1: RTSP Re-Publishing (Recommended)

**Best for:** Real-time monitoring, multiple viewers

The camera already provides an RTSP stream. Simply forward it to a central RTSP server.

```
Camera RTSP → Orange Pi (relay) → RTSP Server → Processing / Viewing
```

#### Setup RTSP Server (MediaMTX)

On your processing server:

```bash
# Download MediaMTX (formerly rtsp-simple-server)
wget https://github.com/bluenviron/mediamtx/releases/download/v1.5.0/mediamtx_v1.5.0_linux_amd64.tar.gz
tar xzf mediamtx_v1.5.0_linux_amd64.tar.gz

# Run
./mediamtx
# Now listening on rtsp://server:8554
```

#### Configure Stream Relay (Orange Pi)

```bash
# .env
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=password
STREAM_MODE=republish
OUTPUT_RTSP_URL=rtsp://your-server.local:8554/camera1
```

#### Run Relay

```bash
python3 stream_relay.py
```

#### View Stream

```bash
# VLC, MPV, or FFplay
ffplay rtsp://your-server.local:8554/camera1

# Python (OpenCV)
import cv2
cap = cv2.VideoCapture('rtsp://your-server.local:8554/camera1')
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow('Camera', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
```

---

### Approach 2: HLS Streaming (HTTP Live Streaming)

**Best for:** Web browsers, mobile apps, many viewers

Converts RTSP to HLS format (.m3u8 playlist + .ts segments).

#### Configure for HLS

```bash
# .env
CAMERA_IP=192.168.1.141
STREAM_MODE=hls
OUTPUT_DIR=/var/www/html/camera1
SEGMENT_TIME=4  # 4-second segments
```

#### Run Relay

```bash
python3 stream_relay.py
```

#### Serve with HTTP Server

```bash
# Simple Python server
cd /var/www/html/camera1
python3 -m http.server 8000

# Or use Nginx/Caddy for production
```

#### View in Browser

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
</head>
<body>
    <video id="video" controls width="640"></video>
    <script>
        const video = document.getElementById('video');
        const hls = new Hls();
        hls.loadSource('http://your-server:8000/stream.m3u8');
        hls.attachMedia(video);
    </script>
</body>
</html>
```

---

### Approach 3: Segmented Recording + Processing

**Best for:** Batch processing, archival, cost-sensitive deployments

Records video in segments for later processing.

#### Configure for Recording

```bash
# .env
CAMERA_IP=192.168.1.141
STREAM_MODE=record
OUTPUT_DIR=/mnt/storage/camera1
SEGMENT_TIME=60  # 1-minute segments
```

#### Run Relay

```bash
python3 stream_relay.py
```

This creates files like:
```
/mnt/storage/camera1/
├── segment_20260121_100000.mp4
├── segment_20260121_100100.mp4
├── segment_20260121_100200.mp4
```

#### Process Segments

```python
# process_segments.py
import cv2
import glob
from pathlib import Path

SEGMENT_DIR = Path("/mnt/storage/camera1")

for segment_file in sorted(SEGMENT_DIR.glob("segment_*.mp4")):
    print(f"Processing {segment_file}")

    cap = cv2.VideoCapture(str(segment_file))

    # Extract frames at intervals
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Process every 30th frame (1 per second at 30 FPS)
        if frame_count % 30 == 0:
            # TODO: Your ML processing here
            # - Fisheye dewarp
            # - OpenAI Vision API
            # - Object detection
            pass

        frame_count += 1

    cap.release()

    # Move processed segment
    segment_file.rename(SEGMENT_DIR / "processed" / segment_file.name)
```

---

### Approach 4: Real-Time Frame Processing

**Best for:** Low-latency ML inference, immediate alerts

Stream frames directly to your processing server.

#### Option A: Using Existing camera_capture.py

The simplest approach - use the existing streaming functionality:

```python
# live_processing.py
from reolinkapi import Camera
import cv2
import numpy as np

cam = Camera("192.168.1.141", "admin", "password")

# Open video stream (uses RTSP internally)
stream = cam.open_video_stream()

for frame in stream:
    # frame is a numpy array (BGR)

    # TODO: Add your processing
    # - Dewarp fisheye
    # - Run ML model
    # - Send to OpenAI API (batch every N frames)

    # Display (optional)
    cv2.imshow('Camera', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
```

#### Option B: Direct RTSP on Processing Server

Skip the relay entirely - connect directly from processing server:

```python
# server_processor.py
import cv2
import base64
from openai import OpenAI

client = OpenAI()

# Connect directly to camera RTSP
rtsp_url = "rtsp://admin:password@192.168.1.141:554/h264Preview_01_main"
cap = cv2.VideoCapture(rtsp_url)

frame_count = 0
process_every = 30  # Process 1 frame per second (assuming 30 FPS)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    # Only process every Nth frame
    if frame_count % process_every == 0:
        # Convert to JPEG
        _, encoded = cv2.imencode('.jpg', frame)
        image_base64 = base64.b64encode(encoded).decode('utf-8')

        # Send to OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's happening?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    }
                ]
            }]
        )

        print(f"Frame {frame_count}: {response.choices[0].message.content}")

cap.release()
```

---

## Comparison Matrix

| Approach | Latency | Bandwidth | Storage | Complexity | Best For |
|----------|---------|-----------|---------|------------|----------|
| RTSP Republish | Low | High | None | Low | Real-time monitoring |
| HLS | Medium | High | Low | Medium | Web viewing |
| Segmented Record | High | Medium | High | Low | Batch processing |
| Direct RTSP | Low | High | None | Low | Simple setups |

## Bandwidth & Storage Requirements

### RTSP Stream
- **Bitrate:** 1-5 Mbps (depends on resolution/quality)
- **Daily:** ~10-60 GB per camera
- **Monthly:** ~300-1800 GB per camera

### HLS Segments
- **Bitrate:** 1-5 Mbps
- **Storage:** Depends on retention (auto-delete old segments)
- **Recommended:** Keep last 1-6 hours (~4-100 GB)

### Recorded Segments
- **Bitrate:** 1-5 Mbps
- **Daily:** ~10-60 GB per camera
- **Monthly:** ~300-1800 GB per camera
- **Recommendation:** Delete after processing or move to cold storage

## Resource Usage

### Stream Relay (Orange Pi)

```
CPU: 5-15% (minimal with -c copy)
Memory: ~50-100 MB
Network: 1-5 Mbps constant
Power: ~3-5W
```

### Direct Processing (Server)

```
CPU: 20-80% (depends on ML workload)
Memory: 500 MB - 2 GB
Network: 1-5 Mbps constant
Power: Depends on server hardware
```

## Installation

### Install FFmpeg (Required for stream_relay.py)

```bash
# Raspberry Pi / Orange Pi
sudo apt-get update
sudo apt-get install -y ffmpeg

# Test
ffmpeg -version
```

### Install Stream Relay as Service

```bash
# Create systemd service
sudo tee /etc/systemd/system/stream-relay.service > /dev/null <<EOF
[Unit]
Description=RTSP Stream Relay
After=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
EnvironmentFile=$(pwd)/.env
ExecStart=/usr/bin/python3 $(pwd)/stream_relay.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable stream-relay
sudo systemctl start stream-relay
```

## Hybrid Approach: Streaming + Snapshots

**Best of both worlds:** Stream for live monitoring, snapshots for archival.

```bash
# Terminal 1: Stream relay for real-time viewing
STREAM_MODE=republish python3 stream_relay.py

# Terminal 2: Snapshot uploader for archival
STORAGE_BACKEND=s3 python3 uploader.py
```

Benefits:
- Live stream for immediate alerts and monitoring
- Snapshots for cost-effective long-term storage
- Process snapshots in batch during off-peak hours

## Cost Comparison

### Streaming (S3 + EC2 Processing)
- **Storage:** ~$20-60/month (1 TB)
- **Transfer:** ~$10-20/month
- **Compute:** ~$50-200/month (EC2 instance)
- **Total:** ~$80-280/month per camera

### Snapshots (10-second interval)
- **Storage:** ~$0.50/month (10 GB)
- **Transfer:** ~$0.10/month
- **Compute:** ~$5/month (Lambda)
- **Total:** ~$5-10/month per camera

### Recommendation
- Use streaming for 1-3 critical cameras
- Use snapshots for additional cameras
- Hybrid: stream during business hours, snapshots overnight

## Troubleshooting

### Stream relay fails to start
```bash
# Check FFmpeg installation
ffmpeg -version

# Test camera RTSP directly
ffplay rtsp://admin:password@192.168.1.141:554/h264Preview_01_main

# Check network connectivity
ping 192.168.1.141
```

### High CPU usage on Orange Pi
```bash
# Use -c copy (no re-encoding)
# This is already default in stream_relay.py

# Check if re-encoding is happening
top -p $(pgrep ffmpeg)

# If high CPU, check FFmpeg logs
journalctl -u stream-relay -f
```

### Stream buffering/lagging
```bash
# Add these FFmpeg flags for lower latency
-fflags nobuffer -flags low_delay -framedrop
```

### Can't view HLS in browser
```bash
# Check CORS headers in HTTP server
# For Python http.server, use a wrapper with CORS enabled

# Or use Caddy with auto CORS
caddy file-server --browse --listen :8000
```

## Next Steps

1. **Test locally:** Start with direct RTSP connection on your processing server
2. **Add relay:** Deploy stream_relay.py on Orange Pi once you confirm it works
3. **Choose mode:** Pick RTSP republish (real-time) or segmented recording (batch)
4. **Integrate ML:** Use your existing dewarping and OpenAI code on the stream
5. **Monitor:** Set up health checks and bandwidth monitoring

See [INTEGRATION.md](INTEGRATION.md) for ML processing integration patterns.
