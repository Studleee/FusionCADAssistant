"""2D finish-guide layout math (Fusion-free).

All coordinates are in a local sketch XY plane.
Bounds are (min_x, min_y, max_x, max_y).
"""

import math


def inset_bounds(min_x, min_y, max_x, max_y, margin):
    """Shrink a bounding box by margin on all sides."""
    m = float(margin)
    x0 = float(min_x) + m
    y0 = float(min_y) + m
    x1 = float(max_x) - m
    y1 = float(max_y) - m
    if x1 <= x0 or y1 <= y0:
        raise ValueError('Margin is too large for the selected face.')
    return x0, y0, x1, y1


def parallel_line_segments(min_x, min_y, max_x, max_y, spacing, angle_deg=0.0):
    """Return list of ((x1,y1), (x2,y2)) parallel guide lines across a box.

    Lines are long enough to cover the rotated bounding box, then clipped
    roughly to the axis-aligned box (endpoint clamp). Good enough for guides.
    """
    spacing = float(spacing)
    if spacing <= 0:
        raise ValueError('Spacing must be greater than zero.')

    x0, y0, x1, y1 = float(min_x), float(min_y), float(max_x), float(max_y)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    width = x1 - x0
    height = y1 - y0
    diag = math.hypot(width, height)

    ang = math.radians(float(angle_deg))
    # Direction along stripes; normal for packing.
    dx = math.cos(ang)
    dy = math.sin(ang)
    nx = -math.sin(ang)
    ny = math.cos(ang)

    # Number of lines to cover the diagonal extent.
    count = int(math.ceil(diag / spacing)) + 3
    half = count // 2
    segments = []
    for i in range(-half, half + 1):
        ox = cx + nx * (i * spacing)
        oy = cy + ny * (i * spacing)
        p0 = (ox - dx * diag, oy - dy * diag)
        p1 = (ox + dx * diag, oy + dy * diag)
        clipped = _clip_segment_to_box(p0, p1, x0, y0, x1, y1)
        if clipped:
            segments.append(clipped)
    return segments


def _clip_segment_to_box(p0, p1, x0, y0, x1, y1):
    """Cohen–Sutherland style clip of a segment to an axis-aligned box."""
    INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8

    def code(x, y):
        c = INSIDE
        if x < x0:
            c |= LEFT
        elif x > x1:
            c |= RIGHT
        if y < y0:
            c |= BOTTOM
        elif y > y1:
            c |= TOP
        return c

    x_a, y_a = p0
    x_b, y_b = p1
    c0 = code(x_a, y_a)
    c1 = code(x_b, y_b)

    for _ in range(16):
        if not (c0 | c1):
            return ((x_a, y_a), (x_b, y_b))
        if c0 & c1:
            return None
        c_out = c0 or c1
        if c_out & TOP:
            x = x_a + (x_b - x_a) * (y1 - y_a) / (y_b - y_a) if y_b != y_a else x_a
            y = y1
        elif c_out & BOTTOM:
            x = x_a + (x_b - x_a) * (y0 - y_a) / (y_b - y_a) if y_b != y_a else x_a
            y = y0
        elif c_out & RIGHT:
            y = y_a + (y_b - y_a) * (x1 - x_a) / (x_b - x_a) if x_b != x_a else y_a
            x = x1
        else:  # LEFT
            y = y_a + (y_b - y_a) * (x0 - x_a) / (x_b - x_a) if x_b != x_a else y_a
            x = x0

        if c_out == c0:
            x_a, y_a = x, y
            c0 = code(x_a, y_a)
        else:
            x_b, y_b = x, y
            c1 = code(x_b, y_b)
    return None


def perlage_centers(min_x, min_y, max_x, max_y, spacing, hex_grid=True):
    """Return (x, y) centers for perlage spots inside a box."""
    spacing = float(spacing)
    if spacing <= 0:
        raise ValueError('Perlage spacing must be greater than zero.')

    x0, y0, x1, y1 = float(min_x), float(min_y), float(max_x), float(max_y)
    centers = []
    row = 0
    y = y0
    while y <= y1 + 1e-9:
        x_off = 0.5 * spacing if (hex_grid and row % 2) else 0.0
        x = x0 + x_off
        while x <= x1 + 1e-9:
            centers.append((x, y))
            x += spacing
        y += spacing * (math.sqrt(3.0) * 0.5 if hex_grid else 1.0)
        row += 1
    return centers


def concentric_radii(inner_radius, outer_radius, spacing):
    """Radii for circular-graining rings from inner to outer."""
    spacing = float(spacing)
    if spacing <= 0:
        raise ValueError('Ring spacing must be greater than zero.')
    r0 = max(float(inner_radius), 0.0)
    r1 = float(outer_radius)
    if r1 <= r0:
        raise ValueError('Outer radius must be larger than inner radius.')
    radii = []
    r = r0 + spacing
    while r < r1 - 1e-9:
        radii.append(r)
        r += spacing
    if not radii:
        radii.append(0.5 * (r0 + r1))
    return radii


def sunburst_rays(center_x, center_y, inner_radius, outer_radius, ray_count):
    """Return list of ((x1,y1), (x2,y2)) radial ray segments."""
    n = int(ray_count)
    if n < 3:
        raise ValueError('Sunburst needs at least 3 rays.')
    r0 = max(float(inner_radius), 0.0)
    r1 = float(outer_radius)
    if r1 <= r0:
        raise ValueError('Sunburst outer radius must exceed inner radius.')
    rays = []
    for i in range(n):
        a = (2.0 * math.pi) * (float(i) / float(n))
        c = math.cos(a)
        s = math.sin(a)
        rays.append((
            (center_x + r0 * c, center_y + r0 * s),
            (center_x + r1 * c, center_y + r1 * s),
        ))
    return rays
