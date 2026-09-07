"""Regular polygon sketch helpers."""

import math

import adsk.core


def add_regular_polygon(sketch, center_point, radius_cm, sides, start_angle_deg=30.0):
    """Draw a closed regular polygon with `sides` edges.

    center_point: SketchPoint or Point3D in sketch space.
    radius_cm: vertex radius (center to corner) in centimeters.
    start_angle_deg: first vertex angle; 30° gives a flat-top hex for 6 sides.
    """
    if sides < 3:
        raise ValueError('Polygon needs at least 3 sides.')
    if radius_cm <= 0:
        raise ValueError('Polygon radius must be greater than zero.')

    if hasattr(center_point, 'geometry'):
        cx = center_point.geometry.x
        cy = center_point.geometry.y
    else:
        cx = center_point.x
        cy = center_point.y

    lines = sketch.sketchCurves.sketchLines
    points = []
    for i in range(sides):
        ang = math.radians(start_angle_deg + i * (360.0 / sides))
        points.append(adsk.core.Point3D.create(
            cx + radius_cm * math.cos(ang),
            cy + radius_cm * math.sin(ang),
            0.0))

    created = []
    for i in range(sides):
        line = lines.addByTwoPoints(points[i], points[(i + 1) % sides])
        if not line:
            raise RuntimeError('Failed to create polygon edge.')
        created.append(line)
    return created


def hex_vertex_radius_from_across_flats(across_flats_cm):
    """Convert hex across-flats distance to vertex radius (center→corner).

    For a regular hex: R = AF / sqrt(3).
    """
    if across_flats_cm <= 0:
        raise ValueError('Across-flats must be greater than zero.')
    return float(across_flats_cm) / math.sqrt(3.0)
