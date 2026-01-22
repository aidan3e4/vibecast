#!/usr/bin/env python3
"""
Reolink Fisheye Camera Capture Script

Captures photos from a Reolink fisheye camera at regular intervals,
generates perspective views, and optionally sends them to an LLM for analysis.
"""

import argparse
from datetime import datetime
from dotenv import load_dotenv
import json
import os
from pathlib import Path
import time

import numpy as np

from reolinkapi import Camera

# Import image processing functions from the image-processor service
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from image_processor import (
    get_room_views,
    image_to_base64,
    save_image,
    analyze_with_openai,
)

load_dotenv()

# View name mapping
VIEW_MAP = {
    'N': 'North',
    'S': 'South',
    'E': 'East',
    'W': 'West',
    'B': 'Below',
}


def create_session(output_dir, place=None):
    """Create a new session folder with metadata."""
    timestamp = datetime.now()
    session_id = f"session_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    session_dir = output_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        'session_id': session_id,
        'start_time': timestamp.isoformat(),
        'end_time': None,
        'place': place,
        'capture_count': 0
    }

    metadata_path = session_dir / 'session_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return session_dir, metadata_path


def update_session_metadata(metadata_path, **updates):
    """Update session metadata file with new values."""
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    metadata.update(updates)

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def capture_and_process(cam, session_dir, metadata_path, views_to_send, prompt, api_key, fov=90, output_size=(1080, 810)):
    """Capture a snapshot, generate views, save files, and optionally call LLM."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get snapshot
    pil_image = cam.get_snap()
    if not pil_image:
        print(f"[{timestamp}] Failed to get snapshot")
        return None

    img_np = np.array(pil_image)

    # Save original fisheye
    fisheye_path = session_dir / f"{timestamp}_fisheye.jpg"
    save_image(img_np, fisheye_path)
    print(f"[{timestamp}] Saved fisheye: {fisheye_path}")

    # Generate and save all views
    views = get_room_views(img_np, fov=fov, output_size=output_size)

    view_paths = {}
    for view_name, view_img in views.items():
        short_name = view_name[0].upper()  # N, E, S, W, B
        view_path = session_dir / f"{timestamp}_{short_name}.jpg"
        save_image(view_img, view_path)
        view_paths[short_name] = view_path
        print(f"[{timestamp}] Saved {view_name}: {view_path}")

    # Send selected views to LLM if API key provided
    if api_key and views_to_send:
        results = {}

        for view_code in views_to_send:
            view_name = VIEW_MAP.get(view_code.upper())
            if view_name and view_name in views:
                view_img = views[view_name]
                image_base64 = image_to_base64(view_img)

                print(f"[{timestamp}] Sending {view_name} view to LLM...")
                try:
                    response = analyze_with_openai(image_base64, prompt, api_key)
                    results[view_name] = response
                    print(f"[{timestamp}] LLM response for {view_name}:")
                    print(response)
                    print()
                except Exception as e:
                    print(f"[{timestamp}] LLM error for {view_name}: {e}")
                    results[view_name] = f"Error: {e}"

        # Save LLM responses
        if results:
            response_path = session_dir / f"{timestamp}_llm_responses.json"
            with open(response_path, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'prompt': prompt,
                    'views_analyzed': list(results.keys()),
                    'responses': results,
                }, f, indent=2)
            print(f"[{timestamp}] Saved LLM responses: {response_path}")

    # Update session metadata with incremented capture count
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    metadata['capture_count'] += 1
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return timestamp


def main():
    parser = argparse.ArgumentParser(
        description='Capture photos from Reolink fisheye camera and analyze with LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using defaults from .env file:
  python camera_capture.py -f 60 -v N

  # Capture every 30 seconds, send multiple views
  python camera_capture.py -f 30 -v N S E W B

  # Just save photos, no LLM analysis
  python camera_capture.py -f 60

  # Single capture (no loop)
  python camera_capture.py --once

  # Override .env settings
  python camera_capture.py -i 192.168.1.100 -u admin -p password -f 60 -v N

Environment variables (can be set in .env file):
  CAMERA_IP, CAMERA_USERNAME, CAMERA_PASSWORD, OPENAI_API_KEY

View codes:
  N = North, S = South, E = East, W = West, B = Below (floor)
"""
    )

    # Camera connection (defaults from .env)
    parser.add_argument('-i', '--ip', default=os.environ.get('CAMERA_IP'),
                        help='Camera IP address (default: from CAMERA_IP env var)')
    parser.add_argument('-u', '--username', default=os.environ.get('CAMERA_USERNAME', 'admin'),
                        help='Camera username (default: from CAMERA_USERNAME env var)')
    parser.add_argument('-p', '--password', default=os.environ.get('CAMERA_PASSWORD', ''),
                        help='Camera password (default: from CAMERA_PASSWORD env var)')
    parser.add_argument('--https', action='store_true', help='Use HTTPS instead of HTTP')

    # Capture settings
    parser.add_argument('-f', '--frequency', type=int, default=60,
                        help='Capture frequency in seconds (default: 60)')
    parser.add_argument('-o', '--output', type=str, default='../data',
                        help='Output directory for saved files (default: ../data)')
    parser.add_argument('--once', action='store_true', help='Capture once and exit (no loop)')

    # View settings
    parser.add_argument('-v', '--views', nargs='+', default=[],
                        choices=['N', 'S', 'E', 'W', 'B', 'n', 's', 'e', 'w', 'b'],
                        help='Views to send to LLM: N(orth), S(outh), E(ast), W(est), B(elow)')
    parser.add_argument('--fov', type=int, default=90, help='Field of view in degrees (default: 90)')
    parser.add_argument('--size', type=int, nargs=2, default=[1080, 810],
                        metavar=('WIDTH', 'HEIGHT'), help='Output image size (default: 1080 810)')

    # LLM settings
    parser.add_argument('--prompt', type=str, default=None, help='Prompt to send to LLM')
    parser.add_argument('--api-key', type=str, default=os.environ.get('OPENAI_API_KEY'),
                        help='OpenAI API key (default: from OPENAI_API_KEY env var)')

    args = parser.parse_args()

    # Validate
    if not args.ip:
        parser.error("Camera IP required: use -i or set CAMERA_IP in .env")
    if args.views and not args.api_key:
        parser.error("--api-key or OPENAI_API_KEY environment variable required when using --views")

    # Setup output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = args.prompt
    if not prompt:
        prompt_file = Path(__file__).parent.parent / "image_processor" / "default_prompt.txt"
        with open(prompt_file) as tfile:
            prompt = tfile.read()

    # Connect to camera
    print(f"Connecting to camera at {args.ip}...")
    try:
        cam = Camera(args.ip, args.username, args.password, https=args.https)
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return 1

    # Normalize view codes to uppercase
    views_to_send = [v.upper() for v in args.views]

    # Create session
    session_dir, metadata_path = create_session(output_dir)

    print(f"Output directory: {output_dir}")
    print(f"Session directory: {session_dir}")
    print(f"Capture frequency: {args.frequency} seconds")
    print(f"Views to analyze: {views_to_send if views_to_send else 'None (only capturing, no anlysis)'}")
    print()

    try:
        while True:
            capture_and_process(
                cam=cam,
                session_dir=session_dir,
                metadata_path=metadata_path,
                views_to_send=views_to_send,
                prompt=prompt,
                api_key=args.api_key,
                fov=args.fov,
                output_size=tuple(args.size),
            )

            if args.once:
                print("Single capture complete.")
                update_session_metadata(metadata_path, end_time=datetime.now().isoformat())
                break

            print(f"Waiting {args.frequency} seconds until next capture...")
            print()
            time.sleep(args.frequency)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        update_session_metadata(metadata_path, end_time=datetime.now().isoformat())

    return 0


if __name__ == '__main__':
    exit(main())
