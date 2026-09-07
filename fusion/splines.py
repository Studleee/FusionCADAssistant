"""Spline sketch helpers."""

import adsk.core


def add_fitted_spline(sketch, points_xyz, name=None):
    """Create a fitted spline through (x, y, z) tuples in sketch space.

    Returns the SketchFittedSpline.
    """
    if not points_xyz or len(points_xyz) < 2:
        raise ValueError('A fitted spline needs at least two points.')

    collection = adsk.core.ObjectCollection.create()
    for x, y, z in points_xyz:
        collection.add(adsk.core.Point3D.create(float(x), float(y), float(z)))

    spline = sketch.sketchCurves.sketchFittedSplines.add(collection)
    if not spline:
        raise RuntimeError('Failed to create fitted spline.')
    if name:
        try:
            spline.name = name
        except Exception:
            pass
    return spline
