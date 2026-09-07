"""Archimedean spiral helpers for hairspring geometry (Fusion-free)."""

import math


def archimedean_spiral_points(r_inner, r_outer, turns, handedness='CCW',
                              samples_per_turn=36):
    """Return list of (x, y, z) points along a flat Archimedean spiral.

    r = r_inner + b * theta, theta in [0, turns * 2π]
    handedness: 'CCW' or 'CW'
    """
    r_inner = float(r_inner)
    r_outer = float(r_outer)
    turns = float(turns)
    if r_inner <= 0 or r_outer <= r_inner:
        raise ValueError('Outer radius must be greater than inner radius, both > 0.')
    if turns <= 0:
        raise ValueError('Turns must be greater than zero.')

    theta_max = turns * 2.0 * math.pi
    b = (r_outer - r_inner) / theta_max
    sign = 1.0 if str(handedness).upper() == 'CCW' else -1.0
    count = max(int(math.ceil(turns * samples_per_turn)) + 1, 8)

    points = []
    for i in range(count):
        t = theta_max * (float(i) / float(count - 1))
        r = r_inner + b * t
        th = sign * t
        points.append((r * math.cos(th), r * math.sin(th), 0.0))
    return points


def spiral_pitch(r_inner, r_outer, turns):
    """Radial advance per turn for an Archimedean spiral."""
    turns = float(turns)
    if turns <= 0:
        raise ValueError('Turns must be greater than zero.')
    return (float(r_outer) - float(r_inner)) / turns


def offset_polyline_2d(points, offset):
    """Offset a 2D polyline by `offset` along the left-hand normal.

    Positive offset is to the left when traveling along the polyline.
    """
    if len(points) < 2:
        raise ValueError('Need at least two points to offset a polyline.')

    out = []
    n = len(points)
    for i in range(n):
        if i == 0:
            tx = points[1][0] - points[0][0]
            ty = points[1][1] - points[0][1]
        elif i == n - 1:
            tx = points[i][0] - points[i - 1][0]
            ty = points[i][1] - points[i - 1][1]
        else:
            tx = points[i + 1][0] - points[i - 1][0]
            ty = points[i + 1][1] - points[i - 1][1]

        length = math.hypot(tx, ty)
        if length < 1e-12:
            nx, ny = 0.0, 0.0
        else:
            nx = -ty / length
            ny = tx / length

        out.append((
            points[i][0] + nx * float(offset),
            points[i][1] + ny * float(offset),
            points[i][2] if len(points[i]) > 2 else 0.0,
        ))
    return out
