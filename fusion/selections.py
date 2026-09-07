"""Selection validation helpers for future commands."""

import adsk.core
import adsk.fusion


def require_selection(selection, expected_type_name):
    """Return selection.entity or raise if nothing is selected."""
    if not selection or selection.count < 1:
        raise RuntimeError('Select a {} before running this command.'.format(expected_type_name))
    return selection.item(0).entity


def is_circular_edge(entity):
    """True if entity is a circular BRepEdge (full circle preferred for bosses)."""
    edge = adsk.fusion.BRepEdge.cast(entity)
    if not edge:
        return False
    # Circular edges expose geometry as Circle3D or Arc3D.
    geom = edge.geometry
    return geom and (
        geom.objectType == adsk.core.Circle3D.classType() or
        geom.objectType == adsk.core.Arc3D.classType())


def is_planar_face(entity):
    """True if entity is a planar BRepFace."""
    face = adsk.fusion.BRepFace.cast(entity)
    if not face:
        return False
    return face.geometry and face.geometry.objectType == adsk.core.Plane.classType()
