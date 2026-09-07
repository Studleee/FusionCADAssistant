"""Spherical oil-sink geometry helpers (Fusion-free math)."""

import math


def sphere_radius_for_spherical_cap(base_radius, depth):
    """Sphere radius R for a spherical cap with base radius `a` and depth `h`.

    R = (a^2 + h^2) / (2h)
    """
    a = float(base_radius)
    h = float(depth)
    if a <= 0 or h <= 0:
        raise ValueError('Oil sink radius and depth must be greater than zero.')
    return (a * a + h * h) / (2.0 * h)


def spherical_cap_center_height(top_height, depth, sphere_radius):
    """Y/Z of the sphere center for a cup cut down from `top_height` by `depth`."""
    return float(top_height) - float(depth) + float(sphere_radius)


def spherical_surface_height(radius_from_axis, top_height, depth, sphere_radius):
    """Height of the concave spherical surface at a given radial distance.

    Uses the lower intersection of the sphere (the oil-cup surface).
    """
    r = float(radius_from_axis)
    R = float(sphere_radius)
    y_c = spherical_cap_center_height(top_height, depth, R)
    disc = R * R - r * r
    if disc < -1e-12:
        raise ValueError(
            'Radial distance {:.6g} is outside the oil-sink sphere radius {:.6g}.'.format(
                r, R))
    if disc < 0:
        disc = 0.0
    return y_c - math.sqrt(disc)
