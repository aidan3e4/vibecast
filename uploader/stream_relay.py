#!/usr/bin/env python3
"""
Lightweight RTSP Stream Relay

Forwards RTSP video stream from camera to processing server or re-publishes it.
Designed for resource-constrained devices (Raspberry Pi, Orange Pi).

This is much more efficient than snapshot uploading for continuous monitoring.
"""

import os
import sys
import logging
import subprocess
import signal
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class RTSPRelay:
    """
    Relay RTSP stream using FFmpeg.

    Modes:
    1. Re-publish: Re-stream to RTSP server (MediaMTX, rtsp-simple-server)
    2. HLS: Convert to HLS for web viewing
    3. WebRTC: Forward via WebRTC (requires additional setup)
    4. Record: Save segments to disk/S3
    """

    def __init__(self,
                 camera_ip: str,
                 camera_username: str,
                 camera_password: str,
                 camera_port: int = 554,
                 mode: str = 'republish'):

        self.camera_ip = camera_ip
        self.camera_username = camera_username
        self.camera_password = camera_password
        self.camera_port = camera_port
        self.mode = mode
        self.process = None

        # Construct RTSP URL
        # Reolink format: rtsp://username:password@ip:port/h264Preview_01_main
        self.rtsp_url = (
            f"rtsp://{camera_username}:{camera_password}@{camera_ip}:{camera_port}/h264Preview_01_main"
        )

    def start_republish(self, output_rtsp_url: str):
        """
        Re-publish stream to another RTSP server.

        Requires MediaMTX or rtsp-simple-server running on output server.
        Example output: rtsp://server.local:8554/camera1
        """
        logger.info(f"Starting RTSP republish: {self.rtsp_url} -> {output_rtsp_url}")

        # FFmpeg command for RTSP re-streaming
        # -rtsp_transport tcp: Use TCP for reliability
        # -c copy: Copy streams without re-encoding (minimal CPU)
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-c', 'copy',  # No re-encoding, just copy
            '-f', 'rtsp',
            '-rtsp_transport', 'tcp',
            output_rtsp_url
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        logger.info(f"Stream relay started (PID: {self.process.pid})")

    def start_hls(self, output_dir: str, segment_time: int = 4):
        """
        Convert RTSP to HLS (HTTP Live Streaming) for web viewing.

        Creates .m3u8 playlist and .ts segment files.
        Serve with simple HTTP server (nginx, caddy, or Python http.server).
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        playlist = output_path / "stream.m3u8"

        logger.info(f"Starting HLS conversion: {self.rtsp_url} -> {playlist}")

        # FFmpeg command for HLS
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-c', 'copy',
            '-f', 'hls',
            '-hls_time', str(segment_time),  # Segment duration
            '-hls_list_size', '10',  # Keep last 10 segments in playlist
            '-hls_flags', 'delete_segments',  # Delete old segments
            '-hls_segment_filename', str(output_path / 'segment_%03d.ts'),
            str(playlist)
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        logger.info(f"HLS stream started (PID: {self.process.pid})")
        logger.info(f"Serve {output_dir} with HTTP server and view at stream.m3u8")

    def start_record_segments(self, output_dir: str, segment_time: int = 60):
        """
        Record video in segments for later processing.

        Useful for:
        - Saving to disk/NAS for batch processing
        - Uploading segments to S3 periodically
        - Creating searchable video archive
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting segment recording: {self.rtsp_url} -> {output_dir}")

        # FFmpeg command for segmented recording
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', str(segment_time),
            '-segment_format', 'mp4',
            '-strftime', '1',  # Use timestamp in filename
            '-reset_timestamps', '1',
            str(output_path / 'segment_%Y%m%d_%H%M%S.mp4')
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        logger.info(f"Recording started (PID: {self.process.pid})")

    def start_pipe_to_server(self, server_url: str):
        """
        Pipe raw video stream to HTTP endpoint for real-time processing.

        Your server receives raw H.264 stream and can process frames in real-time.
        """
        logger.info(f"Starting pipe to server: {self.rtsp_url} -> {server_url}")

        # FFmpeg outputs to stdout, curl pipes to server
        ffmpeg_cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-c', 'copy',
            '-f', 'mpegts',  # MPEG-TS format for streaming
            'pipe:1'
        ]

        curl_cmd = [
            'curl',
            '-X', 'POST',
            '-H', 'Content-Type: video/mp2t',
            '--data-binary', '@-',
            server_url
        ]

        # Pipe FFmpeg output to curl
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE
        )

        curl_proc = subprocess.Popen(
            curl_cmd,
            stdin=ffmpeg_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        ffmpeg_proc.stdout.close()  # Allow ffmpeg to receive SIGPIPE

        self.process = ffmpeg_proc
        self.curl_process = curl_proc

        logger.info(f"Stream pipe started (PID: {ffmpeg_proc.pid})")

    def stop(self):
        """Stop the relay process."""
        if self.process:
            logger.info("Stopping stream relay...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info("Stream relay stopped")

    def wait(self):
        """Wait for process to complete (blocking)."""
        if self.process:
            self.process.wait()


def load_config():
    """Load configuration from environment."""
    return {
        'camera_ip': os.getenv('CAMERA_IP'),
        'camera_username': os.getenv('CAMERA_USERNAME', 'admin'),
        'camera_password': os.getenv('CAMERA_PASSWORD', ''),
        'camera_port': int(os.getenv('CAMERA_RTSP_PORT', '554')),
        'mode': os.getenv('STREAM_MODE', 'republish'),
        'output_rtsp_url': os.getenv('OUTPUT_RTSP_URL'),
        'output_dir': os.getenv('OUTPUT_DIR', './stream_output'),
        'server_url': os.getenv('SERVER_URL'),
        'segment_time': int(os.getenv('SEGMENT_TIME', '60'))
    }


def main():
    logger.info("="*60)
    logger.info("RTSP Stream Relay Service")
    logger.info("="*60)

    config = load_config()

    if not config['camera_ip']:
        logger.error("CAMERA_IP environment variable required")
        return 1

    relay = RTSPRelay(
        camera_ip=config['camera_ip'],
        camera_username=config['camera_username'],
        camera_password=config['camera_password'],
        camera_port=config['camera_port'],
        mode=config['mode']
    )

    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        relay.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start relay based on mode
    try:
        if config['mode'] == 'republish':
            if not config['output_rtsp_url']:
                logger.error("OUTPUT_RTSP_URL required for republish mode")
                return 1
            relay.start_republish(config['output_rtsp_url'])

        elif config['mode'] == 'hls':
            relay.start_hls(config['output_dir'], config['segment_time'])

        elif config['mode'] == 'record':
            relay.start_record_segments(config['output_dir'], config['segment_time'])

        elif config['mode'] == 'pipe':
            if not config['server_url']:
                logger.error("SERVER_URL required for pipe mode")
                return 1
            relay.start_pipe_to_server(config['server_url'])

        else:
            logger.error(f"Unknown mode: {config['mode']}")
            return 1

        logger.info("Relay running. Press Ctrl+C to stop.")
        relay.wait()

    except Exception as e:
        logger.error(f"Error: {e}")
        relay.stop()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
