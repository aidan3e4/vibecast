# Docker Setup for Reolink Camera Clients

This guide explains how to use Docker to run the Reolink camera capture service.

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and edit it with your settings:

```bash
cp .env.example .env
```

Edit `.env` with your camera credentials and OpenAI API key:

```env
CAMERA_IP=192.168.1.100
CAMERA_USER=admin
CAMERA_PASSWORD=your_camera_password
OPENAI_API_KEY=sk-your-openai-api-key-here
CAPTURE_INTERVAL=60
PLACE=office
```

### 2. Build and Run with Docker Compose

```bash
# Build the image
docker-compose build

# Run the camera client service
docker-compose up -d camera-client

# View logs
docker-compose logs -f camera-client

# Stop the service
docker-compose down
```

### 3. Using Docker Directly

```bash
# Build the image
docker build -t camera-client .

# Run the container
docker run -d \
  --name camera-client \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  camera-client \
  python camera_capture.py --interval 60 --place office --analyze

# View logs
docker logs -f camera-client

# Stop and remove
docker stop camera-client
docker rm camera-client
```

## Configuration Options

### Environment Variables

- `CAMERA_IP` - IP address of your Reolink camera
- `CAMERA_USER` - Camera username (default: admin)
- `CAMERA_PASSWORD` - Camera password
- `OPENAI_API_KEY` - OpenAI API key for image analysis
- `CAPTURE_INTERVAL` - Seconds between captures (default: 60)
- `PLACE` - Location name for session metadata (default: office)

### Camera Capture Script Options

The `camera_capture.py` script supports several command-line options:

```bash
# Basic usage with custom interval
python camera_capture.py --interval 30

# Specify location and enable LLM analysis
python camera_capture.py --place "living-room" --analyze

# Run for a specific duration
python camera_capture.py --duration 3600 --analyze
```

Override the default command in docker-compose.yml or when running docker run.

## Data Persistence

Captured images and session data are stored in the `./data` directory, which is mounted as a volume. This ensures your data persists even if the container is removed.

```
data/
└── session_YYYYMMDD_HHMMSS/
    ├── session_metadata.json
    ├── raw_fisheye_*.jpg
    ├── view_North_*.jpg
    ├── view_South_*.jpg
    └── analysis_*.json
```

## Viewing Sessions

To view captured sessions, you can optionally run the session-viewer service:

1. Uncomment the `session-viewer` service in `docker-compose.yml`
2. Run `docker-compose up -d session-viewer`
3. Open http://localhost:8000 in your browser

## Troubleshooting

### Cannot connect to camera
- Verify the camera IP address is correct
- Ensure the camera is on the same network as the Docker host
- Check camera credentials

### OpenCV or image processing errors
- The image includes all necessary OpenCV dependencies
- If you see library errors, try rebuilding: `docker-compose build --no-cache`

### Permission errors with data directory
- Ensure the `./data` directory has proper permissions
- The container runs as user ID 1000 by default
- Fix permissions: `sudo chown -R 1000:1000 ./data`

## Resource Management

For resource-constrained environments, you can limit CPU and memory usage by uncommenting the `deploy` section in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1G
```

## Multi-Architecture Support

The Dockerfile uses `python:3.12-slim` which supports multiple architectures. To build for different platforms:

```bash
# Build for ARM64 (Raspberry Pi 4, Apple Silicon)
docker buildx build --platform linux/arm64 -t reolink-camera-client:arm64 .

# Build for AMD64
docker buildx build --platform linux/amd64 -t reolink-camera-client:amd64 .
```
