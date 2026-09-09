"""Watch dial layout helpers (sizes in centimeters)."""

from __future__ import annotations

import math


def dial_dims_are_valid(diameter_cm, thickness_cm, center_hole_cm,
                        chapter_ring=False, chapter_width_cm=0.0,
                        hour_indices=False, index_length_cm=0.0,
                        index_width_cm=0.0, index_inset_cm=0.0):
    """True when dial blank + optional features can be built."""
    d = float(diameter_cm)
    t = float(thickness_cm)
    hole = float(center_hole_cm)
    if d <= 0 or t <= 0:
        return False
    if hole < 0 or hole >= d - 1e-4:
        return False
    if chapter_ring:
        cw = float(chapter_width_cm)
        if cw <= 0 or cw * 2.0 >= d - hole:
            return False
    if hour_indices:
        length = float(index_length_cm)
        width = float(index_width_cm)
        inset = float(index_inset_cm)
        if length <= 0 or width <= 0:
            return False
        ra = d * 0.5
        tip_r = ra - inset
        root_r = tip_r - length
        if tip_r <= hole * 0.5 + 1e-4:
            return False
        if root_r <= hole * 0.5 + 1e-4:
            return False
        if width >= length * 2.0 and width >= d * 0.25:
            return False
    return True


def hour_index_rects_xy(diameter_cm, index_length_cm, index_width_cm,
                        index_inset_cm, count=12):
    """Return `count` radial baton rectangles as (xmin, ymin, xmax, ymax) in XY.

    Each baton is axis-aligned in a local radial frame, then rotated. Stored as
    four corner points for sketching (not AABB).
    """
    ra = float(diameter_cm) * 0.5
    length = float(index_length_cm)
    half_w = float(index_width_cm) * 0.5
    tip_r = ra - float(index_inset_cm)
    root_r = tip_r - length
    if tip_r <= root_r:
        raise ValueError('Hour index length/inset are invalid for this dial.')

    rects = []
    for i in range(int(count)):
        ang = (2.0 * math.pi / float(count)) * float(i)
        # Local rectangle along +X (radial), then rotate into place.
        local = (
            (root_r, -half_w),
            (tip_r, -half_w),
            (tip_r, half_w),
            (root_r, half_w),
        )
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)
        corners = []
        for x, y in local:
            corners.append((
                x * cos_a - y * sin_a,
                x * sin_a + y * cos_a,
            ))
        rects.append(corners)
    return rects


def minute_track_ticks_xy(diameter_cm, track_inset_cm, tick_length_cm,
                          hour_length_cm=None, count=60):
    """Radial tick segments for a minute track: list of ((x0,y0),(x1,y1)).

    Every 5th tick (hour position) uses hour_length_cm when provided.
    """
    ra = float(diameter_cm) * 0.5
    outer = ra - float(track_inset_cm)
    short = float(tick_length_cm)
    long = float(hour_length_cm) if hour_length_cm is not None else short * 1.6
    ticks = []
    for i in range(int(count)):
        ang = (2.0 * math.pi / float(count)) * float(i)
        length = long if (i % 5 == 0) else short
        inner = outer - length
        c = math.cos(ang)
        s = math.sin(ang)
        ticks.append(((inner * c, inner * s), (outer * c, outer * s)))
    return ticks
