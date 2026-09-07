"""Sketch creation helpers.

Fusion internal length unit is centimeters. Pass radii/distances in cm.
"""

import adsk.core
import adsk.fusion


def create_offset_plane(component, offset_cm):
    """Create a construction plane offset from the component XY plane.

    offset_cm: signed offset distance in centimeters.
    Returns the ConstructionPlane.
    """
    planes = component.constructionPlanes
    plane_input = planes.createInput()
    # setByOffset offsets along the plane normal (Z for XY).
    plane_input.setByOffset(
        component.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(float(offset_cm)))
    plane = planes.add(plane_input)
    if not plane:
        raise RuntimeError('Failed to create offset construction plane.')
    return plane


def create_yz_offset_plane(component, x_offset_cm):
    """Construction plane parallel to YZ, offset along +X by x_offset_cm."""
    planes = component.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        component.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(float(x_offset_cm)))
    plane = planes.add(plane_input)
    if not plane:
        raise RuntimeError('Failed to create YZ-offset construction plane.')
    return plane


def create_sketch_on_plane(component, plane, name=None):
    """Create a sketch on a construction plane or planar entity."""
    sketch = component.sketches.add(plane)
    if not sketch:
        raise RuntimeError('Failed to create sketch on the selected plane.')
    if name:
        sketch.name = name
    return sketch


def create_circle(sketch, center_point, radius_cm):
    """Add a circle by center and radius (cm).

    center_point may be a SketchPoint or Point3D. Prefer an existing SketchPoint
    (e.g. sketch.originPoint) so concentric circles share one center.
    """
    if radius_cm <= 0:
        raise ValueError('Circle radius must be greater than zero.')

    circles = sketch.sketchCurves.sketchCircles
    circle = circles.addByCenterRadius(center_point, float(radius_cm))
    if not circle:
        raise RuntimeError('Failed to create sketch circle.')
    return circle


def add_diameter_dimension(sketch, circle, text_point, diameter_cm=None):
    """Add a driving diameter dimension to a circle/arc.

    If diameter_cm is provided, set the dimension value after creation
    (internal units: centimeters).
    """
    dims = sketch.sketchDimensions
    dim = dims.addDiameterDimension(circle, text_point)
    if not dim:
        raise RuntimeError('Failed to add diameter dimension.')
    if diameter_cm is not None:
        # Editing SketchDimension.value updates the associated parameter.
        dim.value = float(diameter_cm)
    return dim


def find_annular_profile(sketch):
    """Find the ring profile formed by two concentric circles.

    Two circles produce two profiles: the inner disk (1 loop) and the
    annulus (2 loops). We need the annulus.
    """
    for i in range(sketch.profiles.count):
        profile = sketch.profiles.item(i)
        if profile.profileLoops.count == 2:
            return profile

    raise RuntimeError(
        'Could not find a ring profile. Expected two concentric circles '
        'forming an annular region.')
