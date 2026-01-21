# Streaming vs. Snapshots: Which Should You Use?

Quick decision guide to help you choose between video streaming and snapshot uploading.

## TL;DR Decision Tree

```
Do you need real-time continuous monitoring?
├─ YES → Use streaming (stream_relay.py)
└─ NO → Continue below

Do you need to detect fast motion/events?
├─ YES → Use streaming
└─ NO → Continue below

Can you afford 1-5 Mbps constant bandwidth?
├─ NO → Use snapshots (uploader.py)
└─ YES → Continue below

Do you have > 100GB monthly storage budget?
├─ NO → Use snapshots
└─ YES → Use streaming

Default recommendation: Start with snapshots, upgrade to streaming if needed
```

## Quick Comparison

| Aspect | Snapshots (uploader.py) | Streaming (stream_relay.py) |
|--------|------------------------|----------------------------|
| **Bandwidth** | ~10 KB - 2 MB per capture | 1-5 Mbps constant |
| **Storage** | 0.5-10 GB/month | 300-1800 GB/month |
| **Latency** | Capture interval (10-60s) | <1 second |
| **Frame Rate** | 0.01-0.1 FPS (1 per 10-60s) | 15-30 FPS |
| **CPU (Orange Pi)** | 5-10% during capture | 5-15% constant |
| **Use Case** | Periodic monitoring, archival | Real-time alerts, motion |
| **Best For** | Most users | Critical monitoring |

## When to Use Snapshots

### ✅ Good For:
1. **Periodic monitoring** - Check status every few minutes
2. **Long-term archival** - Store images for weeks/months
3. **Cost-sensitive** - Limited bandwidth or storage budget
4. **Multiple cameras** - Need to monitor many cameras cheaply
5. **Slow-changing scenes** - Office, parking lot, warehouse
6. **Batch ML processing** - Process images during off-peak hours
7. **Intermittent connectivity** - Unreliable network connection

### Examples:
- Security monitoring (check every 30 seconds)
- Time-lapse photography
- Equipment status checks
- Parking lot monitoring
- Weather camera
- Plant growth monitoring

### Real-World Scenario:
> "I have 5 cameras in my warehouse. I want to check for unusual activity
> once per minute and keep images for 90 days. I don't need real-time alerts."

**Use snapshots:** ~25 GB/month storage, $2/month cost

## When to Use Streaming

### ✅ Good For:
1. **Real-time monitoring** - Immediate awareness of events
2. **Motion detection** - Catch fast-moving objects
3. **Live viewing** - Watch camera feed in real-time
4. **Continuous recording** - DVR-like functionality
5. **Fast-changing scenes** - Retail, traffic, public areas
6. **Immediate alerts** - Detect intrusions within seconds
7. **High-value areas** - Critical infrastructure monitoring

### Examples:
- Retail store (detect shoplifting)
- Traffic monitoring
- Intruder detection
- Baby/pet monitoring
- Manufacturing line inspection
- High-security areas

### Real-World Scenario:
> "I need to detect when someone enters my store and analyze their behavior
> in real-time. I want alerts within 2-3 seconds."

**Use streaming:** ~500 GB/month storage, $30/month cost

## Hybrid Approach: Best of Both Worlds

Many users benefit from **both** running simultaneously:

### Setup:
```bash
# Terminal 1: Stream for real-time monitoring
STREAM_MODE=hls python3 stream_relay.py

# Terminal 2: Snapshots for archival
STORAGE_BACKEND=s3 CAPTURE_INTERVAL=60 python3 uploader.py
```

### Benefits:
- **Live stream:** Real-time viewing and alerts
- **Snapshots:** Cost-effective long-term storage
- **Flexibility:** Process stream in real-time, snapshots in batch
- **Redundancy:** Both capture methods for reliability

### Use Cases:
1. **Retail:** Stream during business hours (9am-9pm), snapshots 24/7
2. **Security:** Stream for live viewing, snapshots for archival evidence
3. **Research:** Stream for experiments, snapshots for long-term data
4. **Smart Home:** Stream when home, snapshots when away

## Cost Comparison (1 Camera, 1 Month)

### Snapshots (10-second interval)
```
Storage: 10 GB × $0.023/GB = $0.23
Requests: 259,200 × $0.0004/1000 = $0.10
Transfer: 10 GB × $0.09/GB = $0.90
Processing: Lambda @ $0.20
──────────────────────────────────
Total: ~$1.50/month
```

### Streaming (24/7, 2 Mbps)
```
Storage: 650 GB × $0.023/GB = $15.00
Transfer: 650 GB × $0.09/GB = $58.50
Processing: EC2 t3.small = $15.00
──────────────────────────────────
Total: ~$90/month
```

### Hybrid (Stream 12h/day + Snapshots 24/7)
```
Stream storage: 325 GB × $0.023/GB = $7.50
Stream transfer: 325 GB × $0.09/GB = $29.25
Snapshot storage: 10 GB × $0.023/GB = $0.23
EC2 (shared): $15.00
──────────────────────────────────
Total: ~$52/month
```

## Bandwidth Impact

### Home Internet (100 Mbps down, 10 Mbps up)

**Snapshots:**
- Peak usage: 2 Mbps for 1-2 seconds
- Average: <0.01 Mbps
- Impact: Negligible ✅

**Streaming:**
- Constant: 2-5 Mbps
- Peak: Up to 8 Mbps
- Impact: 20-50% of upload bandwidth ⚠️
- May affect video calls, gaming

**Recommendation:** Use snapshots on residential internet

### Business Internet (1 Gbps symmetrical)

**Both approaches:** Negligible impact ✅

## Storage Requirements

### Snapshots (10s interval, 1 camera)
```
Per day: 8,640 images × 500 KB = 4.3 GB
Per week: 30 GB
Per month: 130 GB
Per year: 1.6 TB

Retention options:
- 7 days: 30 GB
- 30 days: 130 GB
- 90 days: 390 GB
```

### Streaming (24/7, 1 camera, 2 Mbps)
```
Per hour: 900 MB
Per day: 21.6 GB
Per week: 151 GB
Per month: 648 GB
Per year: 7.9 TB

Retention options:
- 24 hours: 22 GB
- 7 days: 151 GB
- 30 days: 648 GB
```

## Processing Workload

### Snapshots
```
Images per day: 8,640
Processing time: ~5s per image (OpenAI API)
Total time: 12 hours
Recommendation: Batch process during off-peak hours
```

### Streaming
```
Frames per day: 2,592,000 (at 30 FPS)
Process every Nth frame: 1:30 = 86,400 frames
Processing time: ~5s per frame
Total time: 120 hours (!!)
Recommendation: Use dedicated GPU or filter frames first
```

## Migration Path

### From Snapshots to Streaming

Reasons to migrate:
- Need lower latency (<10 seconds)
- Missing important events between snapshots
- Want to view live feed
- Budget increased

Steps:
1. Install FFmpeg: `sudo apt-get install ffmpeg`
2. Test streaming: `python3 stream_relay.py`
3. Keep snapshots running initially (hybrid)
4. Gradually phase out snapshots once confident

### From Streaming to Snapshots

Reasons to migrate:
- Too expensive (bandwidth/storage)
- Don't need real-time monitoring
- Want longer retention period
- Reduce complexity

Steps:
1. Determine snapshot interval (start with 30s)
2. Configure uploader.py
3. Run both for a week to compare
4. Stop streaming service

## Real-World Examples

### Example 1: Home Security

**User:** "Monitor front door, need to know when packages arrive"

**Solution:** Snapshots every 30 seconds
- Catch all deliveries
- Cost: $2/month
- Keep images for 7 days
- Alert on motion (process with ML)

### Example 2: Retail Loss Prevention

**User:** "Detect shoplifting in real-time, 3 cameras"

**Solution:** Streaming (HLS) + ML processing
- Real-time alerts within 2 seconds
- Cost: $200/month (3 cameras)
- Live viewing on manager's screen
- Save suspicious events only

### Example 3: Wildlife Research

**User:** "Monitor animal behavior, 10 cameras, remote location"

**Solution:** Snapshots every 60 seconds + cellular
- Limited bandwidth: 1 GB/day per camera
- Cost: $50/month cellular
- Download for processing weekly
- Keep all data for research

### Example 4: Smart City Traffic

**User:** "Monitor 50 intersections, detect congestion"

**Solution:** Hybrid (stream at peak, snapshots off-peak)
- Stream: 7am-7pm weekdays
- Snapshots: All other times
- Cost: $1500/month (50 cameras)
- Process streams for real-time traffic updates
- Archive snapshots for planning

## Technical Considerations

### Snapshots
- **Pros:** Simple, reliable, standard JPEG format
- **Cons:** Miss events between captures
- **Best with:** S3, cheap storage, batch processing

### Streaming
- **Pros:** Continuous, real-time, smooth video
- **Cons:** Complex, requires video processing tools
- **Best with:** GPU servers, dedicated bandwidth, MediaMTX/RTSP server

## Recommendation Algorithm

```python
def choose_mode(requirements):
    # Critical factors
    if requirements['need_realtime_alerts']:
        return 'streaming'

    if requirements['bandwidth_limited']:
        return 'snapshots'

    if requirements['budget_per_camera'] < 10:
        return 'snapshots'

    # Preference factors
    score_streaming = 0
    score_snapshots = 0

    if requirements['latency_requirement'] < 5:
        score_streaming += 3
    else:
        score_snapshots += 2

    if requirements['retention_days'] > 30:
        score_snapshots += 2

    if requirements['num_cameras'] > 5:
        score_snapshots += 2

    if requirements['scene_change_frequency'] == 'high':
        score_streaming += 2

    if score_streaming > score_snapshots:
        return 'streaming'
    else:
        return 'snapshots'

# Example usage
my_requirements = {
    'need_realtime_alerts': False,
    'bandwidth_limited': True,
    'budget_per_camera': 5,
    'latency_requirement': 30,
    'retention_days': 90,
    'num_cameras': 3,
    'scene_change_frequency': 'low'
}

mode = choose_mode(my_requirements)
print(f"Recommended: {mode}")  # Output: snapshots
```

## Summary

**Use Snapshots (uploader.py) if:**
- Cost is a concern
- Don't need real-time alerts
- Limited bandwidth
- Many cameras
- Long retention period needed

**Use Streaming (stream_relay.py) if:**
- Need real-time monitoring
- Fast-changing scenes
- Can afford bandwidth/storage
- Live viewing required
- Immediate alerts critical

**Use Both (Hybrid) if:**
- Want flexibility
- Budget allows
- Need both real-time and archival
- Different needs at different times

**Still unsure?** Start with snapshots. You can always add streaming later if needed.
