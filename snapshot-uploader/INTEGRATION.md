# Integration Guide: Snapshot Uploader + ML Processing

This guide explains how to integrate the snapshot uploader with your ML processing pipeline.

## Architecture Overview

```
┌──────────────┐
│   Camera     │
│  (Reolink)   │
└──────┬───────┘
       │
       │ 1. Capture (every N seconds)
       ▼
┌──────────────────────┐
│  Snapshot Uploader   │
│  (Orange Pi/RPI)     │
│  - Lightweight       │
│  - No ML deps        │
│  - Just upload       │
└──────┬───────────────┘
       │
       │ 2. Upload raw JPEG
       ▼
┌──────────────────────┐
│   Storage Layer      │
│   - S3 Bucket        │
│   - File Server      │
│   - HTTP Endpoint    │
└──────┬───────────────┘
       │
       │ 3. Trigger processing
       ▼
┌──────────────────────┐
│  ML Processing       │
│  (Your Server)       │
│  - Fisheye unwarp    │
│  - OpenAI Vision     │
│  - Object detection  │
└──────────────────────┘
```

## Integration Patterns

### Pattern 1: S3 + Event-Driven Processing

**Best for:** Scalable cloud deployments, AWS ecosystem

#### Setup Snapshot Uploader

```bash
# .env
STORAGE_BACKEND=s3
S3_BUCKET=camera-snapshots
S3_PREFIX=raw/camera-1/
CAPTURE_INTERVAL=10
```

#### Configure S3 Event Notification

1. Go to S3 bucket → Properties → Event notifications
2. Create event:
   - Event name: `new-snapshot`
   - Event types: `PUT` (object created)
   - Destination: Lambda function, SQS queue, or SNS topic

#### Lambda Function for Processing

```python
# lambda_function.py
import json
import boto3
import base64
from openai import OpenAI

s3 = boto3.client('s3')
openai_client = OpenAI()

def lambda_handler(event, context):
    # Get snapshot info from S3 event
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        print(f"Processing: s3://{bucket}/{key}")

        # Download image
        response = s3.get_object(Bucket=bucket, Key=key)
        image_bytes = response['Body'].read()

        # Convert to base64 for OpenAI
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Send to OpenAI Vision API
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this camera snapshot"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                    ],
                }
            ],
        )

        analysis = response.choices[0].message.content

        # Store results
        result_key = key.replace('raw/', 'processed/').replace('.jpg', '.json')
        s3.put_object(
            Bucket=bucket,
            Key=result_key,
            Body=json.dumps({
                'timestamp': key.split('_')[1].split('.')[0],
                'analysis': analysis,
                'source_image': f"s3://{bucket}/{key}"
            }),
            ContentType='application/json'
        )

        print(f"Results saved to: s3://{bucket}/{result_key}")

    return {'statusCode': 200, 'body': json.dumps('Processed')}
```

#### Deploy Lambda

```bash
# Install dependencies
pip install openai boto3 -t ./package
cd package
zip -r ../lambda.zip .
cd ..
zip -g lambda.zip lambda_function.py

# Upload to AWS
aws lambda create-function \
  --function-name snapshot-processor \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda.zip \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-s3-role \
  --environment Variables="{OPENAI_API_KEY=your-key}" \
  --timeout 60 \
  --memory-size 512
```

---

### Pattern 2: HTTP POST + Direct Processing

**Best for:** Low-latency processing, direct server communication, no cloud dependencies

#### Setup Snapshot Uploader

```bash
# .env
STORAGE_BACKEND=http
HTTP_UPLOAD_URL=https://your-server.com/api/snapshots
HTTP_AUTH_TOKEN=your-secret-token
CAPTURE_INTERVAL=10
```

#### Flask Server for Processing

```python
# server.py
from flask import Flask, request, jsonify
import cv2
import numpy as np
import base64
from openai import OpenAI
import os
from datetime import datetime

app = Flask(__name__)
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# Import dewarping functions from your existing code
from camera_capture import get_room_views

@app.route('/api/snapshots', methods=['POST'])
def receive_snapshot():
    # Validate auth token
    auth_header = request.headers.get('Authorization')
    expected_token = f"Bearer {os.environ['HTTP_AUTH_TOKEN']}"

    if auth_header != expected_token:
        return jsonify({'error': 'Unauthorized'}), 401

    # Get uploaded file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = file.filename

    # Read image
    image_bytes = file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Generate dewarped views
    views = get_room_views(img_rgb, fov=90, output_size=(1080, 810))

    # Process "Below" view (or any view you want)
    below_view = views['Directly Below (floor)']

    # Convert to base64 for OpenAI
    _, encoded = cv2.imencode('.jpg', cv2.cvtColor(below_view, cv2.COLOR_RGB2BGR))
    image_base64 = base64.b64encode(encoded.tobytes()).decode('utf-8')

    # Analyze with OpenAI
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this room snapshot"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                ],
            }
        ],
    )

    analysis = response.choices[0].message.content

    # Save results
    timestamp = datetime.now().isoformat()
    result = {
        'timestamp': timestamp,
        'filename': filename,
        'analysis': analysis
    }

    # TODO: Store in database, send notification, etc.
    print(f"Processed {filename}: {analysis}")

    return jsonify({'status': 'success', 'result': result}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

#### Run Server

```bash
# Install dependencies
pip install flask opencv-python numpy openai

# Set environment
export OPENAI_API_KEY=your-key
export HTTP_AUTH_TOKEN=your-secret-token

# Run
python server.py
```

---

### Pattern 3: Filesystem + Polling

**Best for:** Simple local setups, no cloud, direct filesystem access

#### Setup Snapshot Uploader (On Orange Pi)

```bash
# .env
STORAGE_BACKEND=filesystem
LOCAL_STORAGE_PATH=/mnt/shared/snapshots
CAPTURE_INTERVAL=10
```

Mount shared directory:
```bash
# On Orange Pi
sudo mount -t nfs server.local:/snapshots /mnt/shared/snapshots
```

#### Processing Script (On Server)

```python
# process_snapshots.py
import os
import time
from pathlib import Path
import cv2
import numpy as np
from openai import OpenAI
import base64
import json

SNAPSHOT_DIR = Path("/path/to/snapshots")
PROCESSED_DIR = Path("/path/to/processed")
CHECK_INTERVAL = 5  # seconds

client = OpenAI()

def process_image(image_path):
    """Process a single snapshot."""
    print(f"Processing {image_path}")

    # Read image
    img = cv2.imread(str(image_path))
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # TODO: Add your dewarping logic here
    # from camera_capture import get_room_views
    # views = get_room_views(img_rgb)

    # Convert to base64
    _, encoded = cv2.imencode('.jpg', img)
    image_base64 = base64.b64encode(encoded.tobytes()).decode('utf-8')

    # Analyze with OpenAI
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this snapshot"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                ],
            }
        ],
    )

    analysis = response.choices[0].message.content

    # Save results
    result_path = PROCESSED_DIR / f"{image_path.stem}_analysis.json"
    with open(result_path, 'w') as f:
        json.dump({
            'source': str(image_path),
            'timestamp': image_path.stem,
            'analysis': analysis
        }, f, indent=2)

    # Move processed image
    processed_image = PROCESSED_DIR / image_path.name
    os.rename(image_path, processed_image)

    print(f"Saved results to {result_path}")

def watch_directory():
    """Watch for new snapshots and process them."""
    PROCESSED_DIR.mkdir(exist_ok=True)
    processed_files = set()

    print(f"Watching {SNAPSHOT_DIR} for new snapshots...")

    while True:
        # Find new snapshots
        snapshots = list(SNAPSHOT_DIR.glob("snapshot_*.jpg"))

        for snapshot in snapshots:
            if snapshot not in processed_files:
                try:
                    process_image(snapshot)
                    processed_files.add(snapshot)
                except Exception as e:
                    print(f"Error processing {snapshot}: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    watch_directory()
```

Run as service:
```bash
# Run in background
nohup python3 process_snapshots.py > processing.log 2>&1 &
```

---

## Comparison of Patterns

| Pattern | Latency | Cost | Complexity | Scalability | Offline Support |
|---------|---------|------|------------|-------------|-----------------|
| S3 + Lambda | Medium | Medium | Medium | High | No |
| HTTP POST | Low | Low | Low | Medium | No |
| Filesystem | Medium | Low | Low | Low | Yes |

## Monitoring Integration

### Health Check Monitoring

Use the uploader's health endpoint for monitoring:

```bash
# Check from processing server
curl http://orangepi.local:8080/health

# Prometheus scraping (optional)
# Add to prometheus.yml:
scrape_configs:
  - job_name: 'snapshot-uploader'
    static_configs:
      - targets: ['orangepi.local:8080']
```

### Processing Metrics

Track your processing pipeline:

```python
# Add to processing code
import time

METRICS = {
    'processed_count': 0,
    'error_count': 0,
    'avg_processing_time': 0
}

def process_image(image_path):
    start = time.time()
    try:
        # ... processing code ...
        METRICS['processed_count'] += 1
    except Exception as e:
        METRICS['error_count'] += 1
        raise
    finally:
        elapsed = time.time() - start
        METRICS['avg_processing_time'] = (
            METRICS['avg_processing_time'] * 0.9 + elapsed * 0.1
        )
```

## Cost Optimization

### S3 Storage Costs

```python
# Lifecycle policy to archive old snapshots
lifecycle_policy = {
    'Rules': [{
        'Id': 'archive-old-snapshots',
        'Status': 'Enabled',
        'Transitions': [{
            'Days': 7,
            'StorageClass': 'GLACIER'
        }],
        'Expiration': {'Days': 30}
    }]
}

s3.put_bucket_lifecycle_configuration(
    Bucket='camera-snapshots',
    LifecycleConfiguration=lifecycle_policy
)
```

### Lambda Costs

- Reduce Lambda memory if not needed (128MB may be sufficient)
- Use Lambda power tuning to find optimal configuration
- Consider processing in batches if latency allows

### OpenAI API Costs

- Use GPT-4o-mini for simple analysis (cheaper)
- Batch multiple images per request if applicable
- Cache results for similar images
- Pre-filter with simple CV before sending to API

## Example: Complete Setup Script

```bash
#!/bin/bash
# setup-complete-pipeline.sh

set -e

echo "Setting up complete snapshot + processing pipeline"

# 1. Install snapshot uploader on Orange Pi
ssh pi@orangepi.local << 'EOF'
cd ~/
git clone https://github.com/yourusername/reolinkapipy.git
cd reolinkapipy/snapshot-uploader
bash install-rpi.sh

# Configure for S3
cat > .env << EOL
CAMERA_IP=192.168.1.141
CAMERA_USERNAME=admin
CAMERA_PASSWORD=password
STORAGE_BACKEND=s3
S3_BUCKET=camera-snapshots
S3_PREFIX=raw/
CAPTURE_INTERVAL=10
EOL

# Install as service
bash install-service.sh
sudo systemctl start snapshot-uploader
EOF

# 2. Deploy Lambda function
echo "Deploying Lambda function..."
cd lambda
pip install -r requirements.txt -t .
zip -r lambda.zip .
aws lambda create-function \
  --function-name snapshot-processor \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda.zip \
  --role arn:aws:iam::123456789:role/lambda-s3-role \
  --environment Variables="{OPENAI_API_KEY=$OPENAI_API_KEY}"

# 3. Configure S3 event trigger
aws s3api put-bucket-notification-configuration \
  --bucket camera-snapshots \
  --notification-configuration file://s3-notification.json

echo "Setup complete!"
echo "Check status: ssh pi@orangepi.local 'sudo systemctl status snapshot-uploader'"
```

## Troubleshooting

### Uploader can't reach S3
- Check internet connectivity on Orange Pi
- Verify AWS credentials
- Test with: `aws s3 ls` from Orange Pi

### Lambda not triggering
- Check S3 event configuration
- View Lambda logs: `aws logs tail /aws/lambda/snapshot-processor --follow`
- Verify Lambda has S3 read permissions

### HTTP endpoint unreachable
- Check firewall rules
- Verify server is running: `curl http://server:5000/health`
- Check auth token matches

### High processing latency
- Monitor Lambda cold starts
- Consider provisioned concurrency for Lambda
- Use CloudWatch metrics to identify bottlenecks
