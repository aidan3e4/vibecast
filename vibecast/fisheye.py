"""
Fisheye Image Processing

Functions for converting fisheye camera images to perspective views.
"""

import cv2
import numpy as np


def create_perspective_map(fisheye_shape, output_size, fov, theta, phi):
    """
    Create remap arrays for fast fisheye to perspective conversion.
    """
    h, w = fisheye_shape[:2]
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)

    out_w, out_h = output_size

    fov_rad = np.radians(fov)
    theta_rad = np.radians(theta)
    phi_rad = np.radians(phi)

    f = out_w / (2 * np.tan(fov_rad / 2))

    x = np.arange(out_w) - out_w / 2
    y = np.arange(out_h) - out_h / 2
    x_grid, y_grid = np.meshgrid(x, y)

    x_norm = x_grid / f
    y_norm = -y_grid / f
    z_norm = np.ones_like(x_norm)

    rays = np.stack([x_norm, y_norm, z_norm], axis=-1)
    rays = rays / np.linalg.norm(rays, axis=-1, keepdims=True)

    cos_t, sin_t = np.cos(theta_rad), np.sin(theta_rad)
    cos_p, sin_p = np.cos(phi_rad), np.sin(phi_rad)

    Ry = np.array([[cos_t, 0, sin_t], [0, 1, 0], [-sin_t, 0, cos_t]])
    Rx = np.array([[1, 0, 0], [0, cos_p, -sin_p], [0, sin_p, cos_p]])
    R = Ry @ Rx

    rays_rotated = np.einsum("ij,hwj->hwi", R, rays)

    rx, ry, rz = rays_rotated[..., 0], rays_rotated[..., 1], rays_rotated[..., 2]

    angle_from_nadir = np.arccos(np.clip(-ry, -1, 1))
    azimuth = np.arctan2(rx, rz)

    r_fish = (angle_from_nadir / (np.pi / 2)) * radius

    map_x = (cx + r_fish * np.sin(azimuth)).astype(np.float32)
    map_y = (cy - r_fish * np.cos(azimuth)).astype(np.float32)

    return map_x, map_y


def fisheye_to_perspective_fast(img, fov=90, theta=0, phi=0, output_size=(800, 600)):
    """Fast fisheye to perspective conversion using OpenCV remap."""
    map_x, map_y = create_perspective_map(img.shape, output_size, fov, theta, phi)
    return cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def extract_center_view(img, radius_fraction=0.6, output_size=(600, 600)):
    """Extract and unwarp the center portion of a fisheye image (directly below)."""
    h, w = img.shape[:2]
    cx, cy = w / 2, h / 2
    radius = min(cx, cy)

    out_w, out_h = output_size

    x = np.linspace(-1, 1, out_w)
    y = np.linspace(-1, 1, out_h)
    x_grid, y_grid = np.meshgrid(x, y)

    r_out = np.sqrt(x_grid**2 + y_grid**2)
    theta_out = np.arctan2(y_grid, x_grid)

    r_fish = r_out * radius * radius_fraction

    map_x = (cx + r_fish * np.cos(theta_out)).astype(np.float32)
    map_y = (cy + r_fish * np.sin(theta_out)).astype(np.float32)

    mask = r_out <= 1.0

    result = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    result[~mask] = 0

    return result


def get_room_views(img, fov=90, output_size=(1080, 810), view_angle=45, below_fraction=0.6):
    """Generate perspective views from fisheye image."""
    directions = {
        "North": (0, view_angle),
        "East": (90, view_angle),
        "South": (180, view_angle),
        "West": (270, view_angle),
    }

    views = {}
    for name, (theta, phi) in directions.items():
        views[name] = fisheye_to_perspective_fast(img, fov=fov, theta=theta, phi=phi, output_size=output_size)

    views["Below"] = extract_center_view(
        img, radius_fraction=below_fraction, output_size=(output_size[0], output_size[0])
    )

    return views
