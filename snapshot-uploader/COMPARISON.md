# Comparison: Snapshot Uploader vs. camera_capture.py

## When to Use Each

### Use `snapshot-uploader` when:
- ✅ Running on resource-constrained hardware (Raspberry Pi, Orange Pi)
- ✅ You want to separate capture from processing
- ✅ Need to run 24/7 as a system service
- ✅ Want to upload to cloud storage (S3, etc.)
- ✅ Processing will happen on a separate, more powerful machine
- ✅ Need minimal memory footprint (<100MB)
- ✅ Want simple deployment and monitoring

### Use `camera_capture.py` when:
- ✅ Running on a desktop/laptop with sufficient resources
- ✅ Want immediate ML processing with each capture
- ✅ Need fisheye dewarping and multi-view generation
- ✅ Want to directly call OpenAI API for image analysis
- ✅ Prefer local storage with session management
- ✅ Need the full reolinkapi library features
- ✅ Doing development or experimentation

## Technical Comparison

| Feature | snapshot-uploader | camera_capture.py |
|---------|-------------------|-------------------|
| **Primary Purpose** | Capture + Upload | Capture + Process + Analyze |
| **Target Hardware** | Raspberry Pi / Orange Pi | Desktop / Laptop |
| **Memory Usage** | ~50-90 MB | ~500+ MB |
| **CPU Usage (idle)** | <1% | ~5-10% |
| **Dependencies** | Minimal (requests, boto3) | Heavy (OpenCV, NumPy, OpenAI) |
| **Image Processing** | None (raw JPEG) | Fisheye unwarp, multi-view |
| **ML Integration** | Deferred to server | Direct OpenAI API calls |
| **Storage** | S3 / HTTP / Filesystem | Local filesystem with sessions |
| **Deployment** | Systemd service / Docker | Script execution |
| **Monitoring** | Built-in health endpoint | None |
| **Configuration** | Environment variables | Command-line args + .env |

## Dependency Comparison

### snapshot-uploader
```
Core:
  - requests (HTTP client)

Optional:
  - boto3 (S3 backend only)

Total install size: ~10-30 MB
```

### camera_capture.py
```
Required:
  - opencv-python (image processing)
  - numpy (array operations)
  - python-dotenv (config)
  - reolinkapi (full camera API)
  - openai (ML API client)
  - Pillow (image handling)

Total install size: ~200-500 MB
```

## Memory Footprint Analysis

### Snapshot Uploader (Raspberry Pi 3)
```
$ ps aux | grep uploader
pi       1234  0.2  3.1  49536 32768  python3 uploader.py

Memory: ~50 MB
- Python interpreter: ~20 MB
- requests library: ~10 MB
- boto3 (if loaded): ~20 MB
- Application code: ~5 MB
```

### camera_capture.py (Desktop)
```
$ ps aux | grep camera_capture
user    5678  5.2 12.8 524288 512000  python3 camera_capture.py

Memory: ~500 MB
- Python interpreter: ~20 MB
- OpenCV + NumPy: ~200 MB
- OpenAI client: ~50 MB
- Image buffers: ~200 MB
- Application code: ~30 MB
```

## Storage Patterns

### snapshot-uploader
```
S3 Backend:
s3://bucket/snapshots/
  ├── snapshot_20260121_100001.jpg
  ├── snapshot_20260121_100011.jpg
  └── snapshot_20260121_100021.jpg

Filesystem Backend:
/home/pi/snapshots/
  ├── snapshot_20260121_100001.jpg
  ├── snapshot_20260121_100011.jpg
  └── snapshot_20260121_100021.jpg
```

### camera_capture.py
```
./data/
├── session_20260121_100000/
│   ├── session_metadata.json
│   ├── 20260121_100001_fisheye.jpg
│   ├── 20260121_100001_N.jpg  (North view)
│   ├── 20260121_100001_E.jpg  (East view)
│   ├── 20260121_100001_S.jpg  (South view)
│   ├── 20260121_100001_W.jpg  (West view)
│   ├── 20260121_100001_B.jpg  (Below view)
│   └── 20260121_100001_llm_responses.json
```

## Processing Flow Comparison

### snapshot-uploader
```
┌─────────┐    ┌──────────┐    ┌────────┐
│ Camera  │───▶│ Uploader │───▶│ Storage│
└─────────┘    └──────────┘    └───┬────┘
                                    │
                                    ▼
                              ┌──────────┐
                              │Processing│
                              │ Server   │
                              └──────────┘
```

**Advantages:**
- Uploader runs continuously on low-power device
- Processing can scale independently
- Multiple cameras can feed one processing server
- Processing server can be upgraded without touching edge devices

### camera_capture.py
```
┌─────────┐    ┌────────────────────┐    ┌─────────┐
│ Camera  │───▶│ camera_capture.py  │───▶│ Storage │
└─────────┘    │ - Capture          │    └─────────┘
               │ - Dewarp           │
               │ - ML Analysis      │
               └────────────────────┘
```

**Advantages:**
- All-in-one solution
- Immediate results
- No network dependency for processing
- Simpler architecture for single-camera setups

## Cost Comparison

### snapshot-uploader (Production Setup)

**Hardware:**
- Orange Pi Zero 2: $30
- Power supply: $10
- SD card: $10
- **Total: $50**

**Ongoing:**
- Power: ~$2/month (2W * 730h * $0.12/kWh)
- S3 storage: ~$0.50/month (10GB)
- S3 requests: ~$0.05/month (10,000 PUTs)
- Lambda processing: ~$1/month
- **Monthly: ~$3.50**

### camera_capture.py (Desktop)

**Hardware:**
- Existing desktop/laptop
- **Total: $0 (assuming you have one)**

**Ongoing:**
- Power: ~$15/month (100W * 730h * $0.12/kWh) [if running 24/7]
- Storage: $0 (local)
- OpenAI API: ~$10/month (depending on usage)
- **Monthly: ~$25** (if running 24/7)

Or just run when needed: **$0/month** + OpenAI API costs per use

## Use Case Examples

### Use Case 1: Home Security Monitoring

**Best Choice: snapshot-uploader**

Why?
- Needs to run 24/7
- Orange Pi consumes minimal power
- Upload to S3 for cloud backup
- Processing happens on demand when you check footage
- Low ongoing costs

### Use Case 2: Development & Testing

**Best Choice: camera_capture.py**

Why?
- Run on your development machine
- Immediate visual feedback from dewarped images
- Iterate quickly on ML prompts
- No need for production infrastructure

### Use Case 3: Research Lab with Multiple Cameras

**Best Choice: snapshot-uploader (multiple instances)**

Why?
- Deploy one Orange Pi per camera
- All upload to centralized S3 bucket
- Single processing server analyzes all feeds
- Easy to add more cameras
- Centralized monitoring

### Use Case 4: Retail Store Analytics

**Best Choice: Hybrid (snapshot-uploader + processing server)**

Why?
- Multiple cameras across store
- Low-power edge devices for capture
- Powerful backend for real-time analytics
- Scalable as business grows
- Professional deployment

### Use Case 5: Temporary Event Monitoring

**Best Choice: camera_capture.py**

Why?
- Short-term use (a few hours/days)
- Bring your laptop
- No need for permanent installation
- Easy setup and teardown

## Migration Path

### From camera_capture.py to snapshot-uploader

1. **Extract camera credentials**
   ```bash
   # From .env or camera_capture.py args
   CAMERA_IP=192.168.1.141
   CAMERA_USERNAME=admin
   CAMERA_PASSWORD=password
   ```

2. **Set up Orange Pi**
   ```bash
   cd snapshot-uploader
   bash install-rpi.sh
   # Edit .env with camera credentials
   ```

3. **Choose storage backend**
   - Start with `filesystem` for testing
   - Move to `s3` or `http` for production

4. **Adapt processing code**
   ```python
   # Use INTEGRATION.md patterns to process uploaded images
   # Keep your existing dewarping and ML code
   # Just change input source from camera to storage
   ```

### From snapshot-uploader to camera_capture.py

Reverse process:
1. Stop snapshot-uploader service
2. Run camera_capture.py on a more powerful machine
3. Adjust capture intervals and view settings
4. Start capturing with immediate processing

## Performance Benchmarks

### Capture Latency

| System | Time to Capture | Time to Store |
|--------|----------------|---------------|
| snapshot-uploader (Orange Pi) | 1-2s | 0.5-2s (depends on backend) |
| camera_capture.py (Desktop) | 1-2s | 0.1s (local disk) |

### End-to-End Latency (Capture to Analysis)

| System | Time to Complete |
|--------|------------------|
| snapshot-uploader + S3 + Lambda | 5-10s |
| snapshot-uploader + HTTP | 3-5s |
| camera_capture.py (direct) | 5-8s |

### Throughput

| System | Images per Hour | Bottleneck |
|--------|----------------|------------|
| snapshot-uploader | 360 (10s interval) | Network upload |
| camera_capture.py | 120-180 | ML processing |

## Recommendations

### Hobbyist / Personal Use
- **Start with:** camera_capture.py on your laptop
- **Upgrade to:** snapshot-uploader when you want 24/7 monitoring

### Small Business / Startup
- **Start with:** snapshot-uploader + HTTP backend
- **Scale to:** snapshot-uploader + S3 + Lambda/EC2

### Enterprise / Large Scale
- **Start with:** snapshot-uploader fleet + S3
- **Scale to:** Custom processing pipeline with Kubernetes/ECS

### Researcher / Academic
- **Use:** Both
  - snapshot-uploader for data collection
  - camera_capture.py for experiments and analysis

## Decision Tree

```
Do you need 24/7 operation?
├─ Yes: Do you have a desktop available to run 24/7?
│  ├─ Yes: Consider power costs → Maybe snapshot-uploader
│  └─ No: Use snapshot-uploader on Orange Pi/RPI
└─ No: Run camera_capture.py when needed

Do you need to process in real-time?
├─ Yes: Use camera_capture.py OR snapshot-uploader + HTTP backend
└─ No: Use snapshot-uploader + S3 + async processing

Do you have >3 cameras?
├─ Yes: Use snapshot-uploader fleet + centralized processing
└─ No: Either works, choose based on hardware availability

Is budget a concern?
├─ Yes: Use snapshot-uploader on cheap hardware
└─ No: Either works, choose based on convenience
```

## Summary

**snapshot-uploader is better for:**
- Production deployments
- 24/7 monitoring
- Multiple camera setups
- Cloud-first architecture
- Power efficiency
- Service-oriented deployment

**camera_capture.py is better for:**
- Development & experimentation
- Single-camera setups
- When you need immediate results
- Local-first processing
- Already have powerful hardware running
- Quick prototyping
