#!/usr/bin/env python3
"""
Session Viewer Web Application

A FastAPI-based web UI for viewing camera capture sessions with metadata,
images, and LLM analysis results.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import tempfile

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request
from dotenv import load_dotenv

from constants import viewer_dir, data_dir as DATA_DIR
from reolinkapi import Camera
from vision_llm import (
    get_room_views,
    image_to_base64,
    save_image,
    analyze_with_openai,
)

load_dotenv()

app = FastAPI(title="Camera Session Viewer")

# Global camera instance
camera_instance: Optional[Camera] = None
temp_dir = Path(tempfile.gettempdir()) / "vibecast_camera"
temp_dir.mkdir(exist_ok=True)

# Configuration
templates = Jinja2Templates(directory=viewer_dir / "templates")

# View name mapping
VIEW_MAP = {
    'N': 'North',
    'S': 'South',
    'E': 'East',
    'W': 'West',
    'B': 'Below',
}


# Request/Response Models
class CameraConnectRequest(BaseModel):
    ip: str
    username: str = "admin"
    password: str = ""


class CaptureResponse(BaseModel):
    timestamp: str
    fisheye_path: str


class UnwarpRequest(BaseModel):
    timestamp: str


class UnwarpResponse(BaseModel):
    views: dict


class AnalyzeRequest(BaseModel):
    timestamp: str
    prompt: str
    api_key: str
    views: list[str]


class AnalyzeResponse(BaseModel):
    results: dict


def get_available_sessions():
    """Get list of all available session folders."""
    if not DATA_DIR.exists():
        return []

    sessions = []
    for session_dir in DATA_DIR.iterdir():
        if session_dir.is_dir() and session_dir.name.startswith('session_'):
            metadata_path = session_dir / 'session_metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                sessions.append({
                    'path': session_dir.name,
                    'metadata': metadata
                })

    # Sort by start time (newest first)
    sessions.sort(key=lambda x: x['metadata']['start_time'], reverse=True)
    return sessions


def get_session_data(session_name):
    """Get complete session data including metadata, images, and analyses."""
    session_dir = DATA_DIR / session_name

    if not session_dir.exists():
        return None

    # Read metadata
    metadata_path = session_dir / 'session_metadata.json'
    if not metadata_path.exists():
        return None

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Find all images and their analyses
    captures = {}

    # Find all fisheye images to get timestamps
    for img_file in session_dir.glob('*_fisheye.jpg'):
        timestamp = img_file.stem.replace('_fisheye', '')
        captures[timestamp] = {
            'timestamp': timestamp,
            'fisheye': img_file.name,
            'views': {},
            'analysis': None
        }

    # Find all view images
    view_codes = ['N', 'S', 'E', 'W', 'B']
    view_names = {
        'N': 'North',
        'S': 'South',
        'E': 'East',
        'W': 'West',
        'B': 'Below'
    }

    for timestamp in captures.keys():
        for code in view_codes:
            view_file = session_dir / f"{timestamp}_{code}.jpg"
            if view_file.exists():
                captures[timestamp]['views'][code] = {
                    'filename': view_file.name,
                    'name': view_names[code]
                }

        # Check for LLM analysis
        analysis_file = session_dir / f"{timestamp}_llm_responses.json"
        if analysis_file.exists():
            with open(analysis_file, 'r') as f:
                captures[timestamp]['analysis'] = json.load(f)

    # Sort captures by timestamp
    sorted_captures = sorted(captures.values(), key=lambda x: x['timestamp'])

    return {
        'session_name': session_name,
        'metadata': metadata,
        'captures': sorted_captures
    }


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """Main page - shows list of available sessions."""
    sessions = get_available_sessions()
    return templates.TemplateResponse('index.html', {
        'request': request,
        'sessions': sessions
    })


@app.get('/session/{session_name}', response_class=HTMLResponse)
async def view_session(request: Request, session_name: str):
    """View a specific session with all its images and analyses."""
    session_data = get_session_data(session_name)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    return templates.TemplateResponse('session.html', {
        'request': request,
        'session': session_data
    })


@app.get('/data/{session_name}/{filename}')
async def serve_image(session_name: str, filename: str):
    """Serve image files from session directories."""
    session_dir = DATA_DIR / session_name
    file_path = session_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@app.get('/api/sessions')
async def api_sessions():
    """API endpoint to get list of sessions."""
    sessions = get_available_sessions()
    return sessions


@app.get('/api/session/{session_name}')
async def api_session(session_name: str):
    """API endpoint to get session data."""
    session_data = get_session_data(session_name)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_data


@app.get('/camera', response_class=HTMLResponse)
async def camera_control(request: Request):
    """Camera control page."""
    camera_ip = os.environ.get('CAMERA_IP', '')
    camera_username = os.environ.get('CAMERA_USERNAME', 'admin')
    camera_password = os.environ.get('CAMERA_PASSWORD', '')
    openai_api_key = os.environ.get('OPENAI_API_KEY', '')
    return templates.TemplateResponse('camera_control.html', {
        'request': request,
        'camera_ip': camera_ip,
        'camera_username': camera_username,
        'camera_password': camera_password,
        'openai_api_key': openai_api_key
    })


@app.post('/api/camera/connect')
async def connect_camera(req: CameraConnectRequest):
    """Connect to the camera."""
    global camera_instance
    try:
        camera_instance = Camera(req.ip, req.username, req.password, https=False)
        return {"status": "connected", "ip": req.ip}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/camera/snapshot')
async def get_snapshot():
    """Get a snapshot from the camera (for live view)."""
    global camera_instance
    if not camera_instance:
        raise HTTPException(status_code=400, detail="Camera not connected")

    try:
        pil_image = camera_instance.get_snap()
        if not pil_image:
            raise HTTPException(status_code=500, detail="Failed to get snapshot")

        # Save to temporary file and return
        temp_path = temp_dir / "live_view.jpg"
        pil_image.save(temp_path, "JPEG")
        return FileResponse(temp_path, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/camera/capture')
async def capture_photo() -> CaptureResponse:
    """Capture and save a fisheye photo."""
    global camera_instance
    if not camera_instance:
        raise HTTPException(status_code=400, detail="Camera not connected")

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get snapshot
        pil_image = camera_instance.get_snap()
        if not pil_image:
            raise HTTPException(status_code=500, detail="Failed to get snapshot")

        img_np = np.array(pil_image)

        # Save fisheye image to temp directory
        fisheye_path = temp_dir / f"{timestamp}_fisheye.jpg"
        save_image(img_np, fisheye_path)

        return CaptureResponse(
            timestamp=timestamp,
            fisheye_path=str(fisheye_path)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/camera/unwarp')
async def unwarp_photo(req: UnwarpRequest) -> UnwarpResponse:
    """Generate perspective views from fisheye image."""
    fisheye_path = temp_dir / f"{req.timestamp}_fisheye.jpg"

    if not fisheye_path.exists():
        raise HTTPException(status_code=404, detail="Fisheye image not found")

    try:
        # Load the fisheye image
        from PIL import Image
        pil_image = Image.open(fisheye_path)
        img_np = np.array(pil_image)

        # Generate perspective views
        views = get_room_views(img_np, fov=90, output_size=(1080, 810))

        # Save all views
        view_files = {}
        for view_name, view_img in views.items():
            short_name = view_name[0].upper()  # N, E, S, W, B
            view_path = temp_dir / f"{req.timestamp}_{short_name}.jpg"
            save_image(view_img, view_path)
            view_files[short_name] = VIEW_MAP[short_name]

        return UnwarpResponse(views=view_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/camera/analyze')
async def analyze_photo(req: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze perspective views with LLM."""
    results = {}

    try:
        for view_name in req.views:
            # Map full name to short code
            short_code = None
            for code, full_name in VIEW_MAP.items():
                if full_name == view_name:
                    short_code = code
                    break

            if not short_code:
                continue

            view_path = temp_dir / f"{req.timestamp}_{short_code}.jpg"
            if not view_path.exists():
                results[view_name] = "Error: View image not found"
                continue

            # Load image and convert to base64
            from PIL import Image
            pil_image = Image.open(view_path)
            img_np = np.array(pil_image)
            image_base64 = image_to_base64(img_np)

            # Analyze with LLM
            try:
                response = analyze_with_openai(image_base64, req.prompt, req.api_key)
                results[view_name] = response
            except Exception as e:
                results[view_name] = f"Error: {str(e)}"

        return AnalyzeResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/camera/image/{filename}')
async def serve_temp_image(filename: str):
    """Serve images from temp directory."""
    file_path = temp_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


if __name__ == '__main__':
    import uvicorn
    print("Starting Session Viewer...")
    print(f"Data directory: {DATA_DIR.absolute()}")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host='0.0.0.0', port=8000)
