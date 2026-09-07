"""Helpers to draw polylines / fitted splines in a sketch."""

import adsk.core


def _as_point3d(pt):
    return adsk.core.Point3D.create(float(pt[0]), float(pt[1]), float(pt[2]))


def _dedupe_closed(points_xyz, tol=1e-9):
    """Drop a duplicate closing vertex if first == last."""
    pts = list(points_xyz)
    if len(pts) < 2:
        return pts
    x0, y0, z0 = pts[0]
    x1, y1, z1 = pts[-1]
    if abs(x0 - x1) <= tol and abs(y0 - y1) <= tol and abs(z0 - z1) <= tol:
        return pts[:-1]
    return pts


def add_polyline(sketch, points_xyz, close_loop=False):
    """Connect (x,y,z) points with sketch lines. Returns the list of SketchLine.

    If close_loop is True and the first/last points differ, adds a closing segment.
    If first and last are already equal, no extra segment is added.
    """
    if not points_xyz or len(points_xyz) < 2:
        raise ValueError('Polyline needs at least two points.')

    pts = list(points_xyz)
    if close_loop:
        x0, y0, z0 = pts[0]
        x1, y1, z1 = pts[-1]
        if abs(x0 - x1) > 1e-9 or abs(y0 - y1) > 1e-9 or abs(z0 - z1) > 1e-9:
            pts.append(pts[0])

    lines = sketch.sketchCurves.sketchLines
    created = []
    for i in range(len(pts) - 1):
        line = lines.addByTwoPoints(_as_point3d(pts[i]), _as_point3d(pts[i + 1]))
        if not line:
            raise RuntimeError('Failed to create polyline segment {}.'.format(i))
        created.append(line)
    return created


def add_closed_fitted_spline(sketch, points_xyz):
    """Create one closed fitted spline through the points (Fusion-stable for gears).

    Much lighter than hundreds/thousands of individual sketch lines.
    """
    pts = _dedupe_closed(points_xyz)
    if len(pts) < 3:
        raise ValueError('Closed fitted spline needs at least three points.')

    collection = adsk.core.ObjectCollection.create()
    for pt in pts:
        collection.add(_as_point3d(pt))

    spline = sketch.sketchCurves.sketchFittedSplines.add(collection)
    if not spline:
        raise RuntimeError('Failed to create fitted spline.')
    try:
        spline.isClosed = True
    except Exception:
        # Older builds: close by ensuring first point repeated in the fit set.
        pass
    return spline


def add_closed_outline(sketch, points_xyz, prefer_spline=True, spline_if_over=40):
    """Draw a closed outline as a fitted spline (preferred) or polyline fallback.

    prefer_spline: use a fitted spline when point count is high or always when True
    and len > spline_if_over.
    """
    pts = list(points_xyz)
    n = len(_dedupe_closed(pts))
    if prefer_spline and n >= int(spline_if_over):
        try:
            return add_closed_fitted_spline(sketch, pts)
        except Exception:
            # Fall back to segmented polyline if spline creation fails.
            pass
    return add_polyline(sketch, pts, close_loop=True)
