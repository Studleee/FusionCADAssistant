"""Helpers for working with planar faces and sketches on them."""

import adsk.core
import adsk.fusion


def require_planar_face(entity):
    """Cast/validate a planar BRepFace or raise."""
    face = adsk.fusion.BRepFace.cast(entity)
    if not face:
        raise ValueError('Select a planar face.')
    if not face.geometry or face.geometry.objectType != adsk.core.Plane.classType():
        raise ValueError('The selected face must be planar.')
    return face


def component_from_face(face):
    """Return the component that owns this face's body."""
    body = face.body
    if not body:
        raise RuntimeError('Face has no parent body.')
    component = body.parentComponent
    if not component:
        raise RuntimeError('Could not resolve the face parent component.')
    return component


def sketch_bounds_from_face(sketch, face):
    """Axis-aligned bounds of the face in sketch coordinates (minx,miny,maxx,maxy)."""
    min_x = min_y = 1e100
    max_x = max_y = -1e100
    found = False

    for i in range(face.edges.count):
        edge = face.edges.item(i)
        for vertex in (edge.startVertex, edge.endVertex):
            if not vertex:
                continue
            sp = sketch.modelToSketchSpace(vertex.geometry)
            min_x = min(min_x, sp.x)
            min_y = min(min_y, sp.y)
            max_x = max(max_x, sp.x)
            max_y = max(max_y, sp.y)
            found = True

        # Sample midpoints for curved edges on otherwise planar faces.
        try:
            evaluator = edge.evaluator
            ok, start_p, end_p = evaluator.getParameterExtents()
            if ok:
                for t in (0.25, 0.5, 0.75):
                    param = start_p + (end_p - start_p) * t
                    ok2, mid = evaluator.getPointAtParameter(param)
                    if ok2 and mid:
                        sp = sketch.modelToSketchSpace(mid)
                        min_x = min(min_x, sp.x)
                        min_y = min(min_y, sp.y)
                        max_x = max(max_x, sp.x)
                        max_y = max(max_y, sp.y)
                        found = True
        except Exception:
            pass

    if not found or max_x <= min_x or max_y <= min_y:
        raise RuntimeError('Could not measure the selected face in sketch space.')
    return min_x, min_y, max_x, max_y


def sketch_point_from_selection(sketch, entity):
    """Map a selected point-like entity into sketch XY, or None."""
    if entity is None:
        return None

    # SketchPoint
    sp = adsk.fusion.SketchPoint.cast(entity)
    if sp:
        return sketch.modelToSketchSpace(sp.worldGeometry)

    # Vertex
    vx = adsk.fusion.BRepVertex.cast(entity)
    if vx:
        return sketch.modelToSketchSpace(vx.geometry)

    # Construction point
    cp = adsk.fusion.ConstructionPoint.cast(entity)
    if cp:
        return sketch.modelToSketchSpace(cp.geometry)

    # Point3D-ish via geometry attribute
    if hasattr(entity, 'geometry'):
        geom = entity.geometry
        if geom and geom.objectType == adsk.core.Point3D.classType():
            return sketch.modelToSketchSpace(geom)

    raise ValueError('Center selection must be a vertex, sketch point, or construction point.')


def face_center_in_sketch(sketch, face):
    """Approximate face center in sketch space (vertex average)."""
    min_x, min_y, max_x, max_y = sketch_bounds_from_face(sketch, face)
    return adsk.core.Point3D.create(
        0.5 * (min_x + max_x),
        0.5 * (min_y + max_y),
        0.0)


def add_construction_line(sketch, x0, y0, x1, y1):
    line = sketch.sketchCurves.sketchLines.addByTwoPoints(
        adsk.core.Point3D.create(float(x0), float(y0), 0.0),
        adsk.core.Point3D.create(float(x1), float(y1), 0.0))
    if not line:
        raise RuntimeError('Failed to create guide line.')
    try:
        line.isConstruction = True
    except Exception:
        pass
    return line


def add_construction_circle(sketch, cx, cy, radius):
    if radius <= 0:
        raise ValueError('Circle radius must be greater than zero.')
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(float(cx), float(cy), 0.0),
        float(radius))
    if not circle:
        raise RuntimeError('Failed to create guide circle.')
    try:
        circle.isConstruction = True
    except Exception:
        pass
    return circle
