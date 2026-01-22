#!/usr/bin/env python3
"""
Lightweight Camera Snapshot Uploader

Designed for resource-constrained devices (Raspberry Pi, Orange Pi).
Captures snapshots from a Reolink camera and uploads them to remote storage.
"""

import io
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Minimal imports - only use what's necessary
import requests

# Optional imports based on storage backend
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            stats = getattr(self.server, 'stats', {})
            response = json.dumps(stats, indent=2)
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass


class CameraClient:
    """Minimal camera client for capturing snapshots."""

    def __init__(self, ip: str, username: str, password: str, https: bool = False):
        self.ip = ip
        self.username = username
        self.password = password
        self.protocol = 'https' if https else 'http'
        self.base_url = f'{self.protocol}://{ip}'
        self.token = None

    def login(self):
        """Login to camera and get token."""
        try:
            url = f'{self.base_url}/api.cgi?cmd=Login'
            body = [{
                'cmd': 'Login',
                'action': 0,
                'param': {
                    'User': {
                        'userName': self.username,
                        'password': self.password
                    }
                }
            }]

            response = requests.post(url, json=body, timeout=10, verify=False)
            response.raise_for_status()

            data = response.json()
            if data and data[0].get('code') == 0:
                self.token = data[0]['value']['Token']['name']
                logger.info("Successfully logged into camera")
                return True
            else:
                logger.error(f"Login failed: {data}")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def get_snapshot(self) -> bytes:
        """Get JPEG snapshot from camera."""
        if not self.token:
            if not self.login():
                return None

        try:
            url = f'{self.base_url}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=&user={self.username}&password={self.password}'

            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()

            return response.content

        except Exception as e:
            logger.error(f"Snapshot capture error: {e}")
            # Try to re-login and retry once
            if self.login():
                try:
                    response = requests.get(url, timeout=10, verify=False)
                    response.raise_for_status()
                    return response.content
                except:
                    pass
            return None


class StorageBackend:
    """Base class for storage backends."""

    def upload(self, image_bytes: bytes, filename: str) -> bool:
        raise NotImplementedError


class S3Backend(StorageBackend):
    """Upload to AWS S3 or S3-compatible storage."""

    def __init__(self, bucket: str, prefix: str = '', region: str = 'us-east-1',
                 access_key: str = None, secret_key: str = None):
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3 backend. Install with: pip install boto3")

        self.bucket = bucket
        self.prefix = prefix

        # Create S3 client
        session_kwargs = {'region_name': region}
        if access_key and secret_key:
            session_kwargs['aws_access_key_id'] = access_key
            session_kwargs['aws_secret_access_key'] = secret_key

        self.s3_client = boto3.client('s3', **session_kwargs)
        logger.info(f"Initialized S3 backend: bucket={bucket}, prefix={prefix}")

    def upload(self, image_bytes: bytes, filename: str) -> bool:
        try:
            key = f"{self.prefix}{filename}"

            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=image_bytes,
                ContentType='image/jpeg'
            )

            logger.info(f"Uploaded to S3: s3://{self.bucket}/{key}")
            return True

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            return False


class FilesystemBackend(StorageBackend):
    """Save to local or network filesystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized filesystem backend: {self.base_path}")

    def upload(self, image_bytes: bytes, filename: str) -> bool:
        try:
            filepath = self.base_path / filename

            with open(filepath, 'wb') as f:
                f.write(image_bytes)

            logger.info(f"Saved to filesystem: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Filesystem write error: {e}")
            return False


class HTTPBackend(StorageBackend):
    """POST to HTTP endpoint."""

    def __init__(self, url: str, auth_token: str = None):
        self.url = url
        self.auth_token = auth_token
        logger.info(f"Initialized HTTP backend: {url}")

    def upload(self, image_bytes: bytes, filename: str) -> bool:
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'

            files = {'file': (filename, io.BytesIO(image_bytes), 'image/jpeg')}

            response = requests.post(
                self.url,
                files=files,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            logger.info(f"Uploaded via HTTP: {filename}")
            return True

        except Exception as e:
            logger.error(f"HTTP upload error: {e}")
            return False


class SnapshotUploader:
    """Main uploader service."""

    def __init__(self, camera: CameraClient, backend: StorageBackend,
                 interval: int = 10, health_port: int = 8080):
        self.camera = camera
        self.backend = backend
        self.interval = interval
        self.health_port = health_port

        # Statistics
        self.stats = {
            'status': 'starting',
            'last_capture': None,
            'uptime_seconds': 0,
            'total_captures': 0,
            'total_uploads': 0,
            'failed_uploads': 0
        }

        self.start_time = time.time()
        self.running = False

    def start_health_server(self):
        """Start health check HTTP server in background thread."""
        def run_server():
            server = HTTPServer(('0.0.0.0', self.health_port), HealthCheckHandler)
            server.stats = self.stats
            logger.info(f"Health check server listening on port {self.health_port}")
            server.serve_forever()

        thread = Thread(target=run_server, daemon=True)
        thread.start()

    def capture_and_upload(self):
        """Capture a snapshot and upload it."""
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}.jpg"

            # Capture snapshot
            logger.info("Capturing snapshot...")
            image_bytes = self.camera.get_snapshot()

            if not image_bytes:
                logger.error("Failed to capture snapshot")
                return False

            self.stats['total_captures'] += 1
            self.stats['last_capture'] = datetime.now().isoformat()

            # Upload
            logger.info(f"Uploading {len(image_bytes)} bytes...")
            success = self.backend.upload(image_bytes, filename)

            if success:
                self.stats['total_uploads'] += 1
            else:
                self.stats['failed_uploads'] += 1

            return success

        except Exception as e:
            logger.error(f"Capture and upload error: {e}")
            self.stats['failed_uploads'] += 1
            return False

    def run(self):
        """Main run loop."""
        logger.info("Starting snapshot uploader service...")
        logger.info(f"Capture interval: {self.interval} seconds")

        # Start health check server
        self.start_health_server()

        # Login to camera
        if not self.camera.login():
            logger.error("Failed to login to camera. Exiting.")
            return 1

        self.running = True
        self.stats['status'] = 'running'

        try:
            while self.running:
                # Update uptime
                self.stats['uptime_seconds'] = int(time.time() - self.start_time)

                # Capture and upload
                self.capture_and_upload()

                # Wait for next interval
                logger.info(f"Waiting {self.interval} seconds until next capture...")
                time.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            self.stats['status'] = 'stopped'
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.stats['status'] = 'error'
            return 1

        return 0


def load_config():
    """Load configuration from environment variables."""
    config = {}

    # Camera settings
    config['camera_ip'] = os.getenv('CAMERA_IP')
    config['camera_username'] = os.getenv('CAMERA_USERNAME', 'admin')
    config['camera_password'] = os.getenv('CAMERA_PASSWORD', '')
    config['camera_https'] = os.getenv('CAMERA_USE_HTTPS', 'false').lower() == 'true'

    # Capture settings
    config['capture_interval'] = int(os.getenv('CAPTURE_INTERVAL', '10'))

    # Storage backend
    config['storage_backend'] = os.getenv('STORAGE_BACKEND', 'filesystem').lower()

    # S3 settings
    config['aws_access_key'] = os.getenv('AWS_ACCESS_KEY_ID')
    config['aws_secret_key'] = os.getenv('AWS_SECRET_ACCESS_KEY')
    config['aws_region'] = os.getenv('AWS_REGION', 'us-east-1')
    config['s3_bucket'] = os.getenv('S3_BUCKET')
    config['s3_prefix'] = os.getenv('S3_PREFIX', 'snapshots/')

    # Filesystem settings
    config['local_storage_path'] = os.getenv('LOCAL_STORAGE_PATH', './snapshots')

    # HTTP settings
    config['http_upload_url'] = os.getenv('HTTP_UPLOAD_URL')
    config['http_auth_token'] = os.getenv('HTTP_AUTH_TOKEN')

    # Health check
    config['health_check_port'] = int(os.getenv('HEALTH_CHECK_PORT', '8080'))

    return config


def create_storage_backend(config):
    """Create storage backend based on configuration."""
    backend_type = config['storage_backend']

    if backend_type == 's3':
        if not config['s3_bucket']:
            raise ValueError("S3_BUCKET is required for S3 backend")

        return S3Backend(
            bucket=config['s3_bucket'],
            prefix=config['s3_prefix'],
            region=config['aws_region'],
            access_key=config['aws_access_key'],
            secret_key=config['aws_secret_key']
        )

    elif backend_type == 'filesystem':
        return FilesystemBackend(config['local_storage_path'])

    elif backend_type == 'http':
        if not config['http_upload_url']:
            raise ValueError("HTTP_UPLOAD_URL is required for HTTP backend")

        return HTTPBackend(
            url=config['http_upload_url'],
            auth_token=config['http_auth_token']
        )

    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")


def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("Camera Snapshot Uploader Service")
    logger.info("="*60)

    # Load configuration
    config = load_config()

    # Validate required settings
    if not config['camera_ip']:
        logger.error("CAMERA_IP environment variable is required")
        return 1

    # Create camera client
    camera = CameraClient(
        ip=config['camera_ip'],
        username=config['camera_username'],
        password=config['camera_password'],
        https=config['camera_https']
    )

    # Create storage backend
    try:
        backend = create_storage_backend(config)
    except Exception as e:
        logger.error(f"Failed to create storage backend: {e}")
        return 1

    # Create and run uploader
    uploader = SnapshotUploader(
        camera=camera,
        backend=backend,
        interval=config['capture_interval'],
        health_port=config['health_check_port']
    )

    return uploader.run()


if __name__ == '__main__':
    # Disable SSL warnings for camera connections
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sys.exit(main())
