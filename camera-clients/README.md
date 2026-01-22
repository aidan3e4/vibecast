# Camera Client Applications

Client applications for capturing and processing camera images.

## Applications

### camera_capture.py

Command-line script for capturing photos from a Reolink fisheye camera at regular intervals.

**Features:**
- Captures fisheye images from Reolink camera
- Generates perspective views (North, South, East, West, Below)
- Optional LLM-based image analysis
- Session-based organization with metadata
- Configurable capture frequency and output settings

**Usage:**
```bash
# From the camera-clients directory
cd camera-clients

# Capture every 60 seconds, analyze North view
python camera_capture.py -f 60 -v N

# Capture multiple views
python camera_capture.py -f 30 -v N S E W B

# Single capture
python camera_capture.py --once

# Override camera settings
python camera_capture.py -i 192.168.1.100 -u admin -p password -f 60
```

**Dependencies:**
- Uses `../image_processor` for image processing
- Uses `../reolinkapi` for camera communication
- Outputs to `../data` by default

### camera_demo.ipynb

Jupyter notebook for interactive camera exploration and testing.

**Features:**
- Interactive fisheye image processing
- View generation experimentation
- LLM analysis testing
- Visualization of results

## Directory Structure

```
camera-clients/
├── camera_capture.py      # CLI capture script
├── camera_demo.ipynb      # Interactive notebook
└── README.md              # This file
```

## Related Services

- [../image_processor/](../image_processor/) - Image processing and LLM analysis
- [../snapshot-uploader/](../snapshot-uploader/) - Upload snapshots to cloud storage
- [../session_viewer.py](../session_viewer.py) - Web UI for viewing capture sessions
