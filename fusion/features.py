"""Feature creation helpers (extrude, etc.)."""

import math

import adsk.core
import adsk.fusion


def _distance_value_input(distance_cm=None, expression=None):
    """Build a ValueInput from a cm float or a parameter expression string."""
    if expression:
        return adsk.core.ValueInput.createByString(expression)
    if distance_cm is None:
        raise ValueError('Provide distance_cm or expression for extrude distance.')
    return adsk.core.ValueInput.createByReal(float(distance_cm))


def create_extrude(component, profile, distance_cm=None, operation=None, name=None,
                   expression=None):
    """Extrude a profile by a distance.

    distance_cm: length in centimeters (used when expression is None).
    expression: optional parameter expression (e.g. 'ringThickness').
    Creates a new body by default. Returns the ExtrudeFeature.
    """
    value_input = _distance_value_input(distance_cm, expression)
    if distance_cm is not None and distance_cm == 0 and not expression:
        raise ValueError('Extrude distance cannot be zero.')

    if operation is None:
        operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(profile, operation)
    if not ext_input:
        raise RuntimeError('Failed to create extrude input.')

    # setDistanceExtent(isSymmetric, distance)
    # False = one-sided extrusion in the positive direction.
    ext_input.setDistanceExtent(False, value_input)
    ext_input.isSolid = True

    extrude = extrudes.add(ext_input)
    if not extrude:
        raise RuntimeError('Failed to create extrude feature.')

    if name:
        extrude.name = name
    return extrude


def create_symmetric_extrude(component, profile, distance_cm=None, operation=None,
                             name=None, expression=None):
    """Extrude symmetrically about the sketch plane.

    distance_cm / expression describe the extent on each side.
    """
    value_input = _distance_value_input(distance_cm, expression)
    if distance_cm is not None and distance_cm <= 0 and not expression:
        raise ValueError('Symmetric extrude distance must be greater than zero.')

    if operation is None:
        operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(profile, operation)
    if not ext_input:
        raise RuntimeError('Failed to create symmetric extrude input.')

    ext_input.setSymmetricExtent(value_input, True)
    ext_input.isSolid = True

    extrude = extrudes.add(ext_input)
    if not extrude:
        raise RuntimeError('Failed to create symmetric extrude feature.')

    if name:
        extrude.name = name
    return extrude


def name_first_body(feature, body_name):
    """Rename the first body produced by a feature."""
    if feature.bodies.count < 1:
        raise RuntimeError('Feature produced no bodies to rename.')
    body = feature.bodies.item(0)
    body.name = body_name
    return body


def create_cut_extrude(component, profile, distance_cm=None, name=None, expression=None,
                       participant_bodies=None, into_solid=False):
    """Cut-extrude a profile into existing bodies by a distance (cm).

    into_solid=True: extrude opposite the sketch-plane normal (typical when the
    sketch sits on the outside face of the body and the cut should go inward).
    """
    value_input = _distance_value_input(distance_cm, expression)
    if distance_cm is not None and distance_cm <= 0 and not expression:
        raise ValueError('Cut extrude distance must be greater than zero.')

    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profile, adsk.fusion.FeatureOperations.CutFeatureOperation)
    if not ext_input:
        raise RuntimeError('Failed to create cut-extrude input.')

    if into_solid:
        # distanceOne = along sketch normal; distanceTwo = opposite.
        # Zero along the outward normal, full depth into the solid.
        ext_input.setTwoSidesDistanceExtent(
            adsk.core.ValueInput.createByReal(0.0),
            value_input)
    else:
        ext_input.setDistanceExtent(False, value_input)
    ext_input.isSolid = True

    if participant_bodies:
        ext_input.participantBodies = list(participant_bodies)

    extrude = extrudes.add(ext_input)
    if not extrude:
        raise RuntimeError('Failed to create cut-extrude feature.')

    if name:
        extrude.name = name
    return extrude


def create_revolve(component, profile, axis, operation=None, name=None,
                   participant_bodies=None):
    """Full 360° revolve of a profile about an axis.

    Defaults to NewBody. Use CutFeatureOperation / JoinFeatureOperation as needed.
    participant_bodies: optional list of BRepBody targets (join/cut).
    """
    if operation is None:
        operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    revolves = component.features.revolveFeatures
    rev_input = revolves.createInput(profile, axis, operation)
    if not rev_input:
        raise RuntimeError('Failed to create revolve input.')

    rev_input.setAngleExtent(False, adsk.core.ValueInput.createByReal(2.0 * math.pi))
    rev_input.isSolid = True

    if participant_bodies:
        rev_input.participantBodies = list(participant_bodies)

    revolve = revolves.add(rev_input)
    if not revolve:
        raise RuntimeError('Failed to create revolve feature.')

    if name:
        revolve.name = name
    return revolve


def create_revolve_cut(component, profile, axis, name=None, participant_bodies=None):
    """Full 360° revolve cut of a profile about an axis.

    participant_bodies: optional list of BRepBody targets for the cut.
    """
    return create_revolve(
        component,
        profile,
        axis,
        operation=adsk.fusion.FeatureOperations.CutFeatureOperation,
        name=name,
        participant_bodies=participant_bodies)


def create_loft(component, profiles, operation=None, name=None, participant_bodies=None):
    """Loft solid through two or more profiles (in order).

    profiles: iterable of Profile objects.
    """
    if operation is None:
        operation = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    lofts = component.features.loftFeatures
    loft_input = lofts.createInput(operation)
    if not loft_input:
        raise RuntimeError('Failed to create loft input.')

    for profile in profiles:
        loft_input.loftSections.add(profile)
    loft_input.isSolid = True

    if participant_bodies:
        loft_input.participantBodies = list(participant_bodies)

    loft = lofts.add(loft_input)
    if not loft:
        raise RuntimeError('Failed to create loft feature.')
    if name:
        loft.name = name
    return loft


def create_combine_join(component, target_body, tool_bodies, name=None):
    """Boolean-join tool bodies into target_body (tools are consumed)."""
    tools = adsk.core.ObjectCollection.create()
    for body in tool_bodies:
        if body:
            tools.add(body)
    if tools.count < 1:
        raise ValueError('No tool bodies provided for combine join.')

    combines = component.features.combineFeatures
    combine_input = combines.createInput(target_body, tools)
    if not combine_input:
        raise RuntimeError('Failed to create combine input.')
    combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combine_input.isKeepToolBodies = False

    combine = combines.add(combine_input)
    if not combine:
        raise RuntimeError('Failed to combine/join bodies.')
    if name:
        combine.name = name
    return combine


def find_cylindrical_face(body, radius_cm, tolerance_cm=0.02):
    """Return a cylindrical face on body whose radius is near radius_cm."""
    if not body:
        raise ValueError('Body is required.')
    target = float(radius_cm)
    best = None
    best_err = None
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if not geom or geom.objectType != adsk.core.Cylinder.classType():
            continue
        err = abs(float(geom.radius) - target)
        if err <= float(tolerance_cm) and (best_err is None or err < best_err):
            best = face
            best_err = err
    if not best:
        raise RuntimeError(
            'Could not find a cylindrical face near diameter {:.3f} cm.'.format(
                target * 2.0))
    return best


def create_constant_fillet(component, edges, radius_cm, name=None):
    """Constant-radius fillet on one or more edges."""
    if radius_cm <= 0:
        raise ValueError('Fillet radius must be greater than zero.')
    collection = adsk.core.ObjectCollection.create()
    for edge in edges:
        if edge:
            collection.add(edge)
    if collection.count < 1:
        raise ValueError('No edges provided for fillet.')

    fillets = component.features.filletFeatures
    fillet_input = fillets.createInput()
    if not fillet_input:
        raise RuntimeError('Failed to create fillet input.')

    # addConstantRadiusEdgeSet(edges, radius, isTangentChain)
    fillet_input.addConstantRadiusEdgeSet(
        collection,
        adsk.core.ValueInput.createByReal(float(radius_cm)),
        True)

    fillet = fillets.add(fillet_input)
    if not fillet:
        raise RuntimeError('Failed to create fillet feature.')
    if name:
        fillet.name = name
    return fillet


def create_circular_pattern(component, entities, axis, quantity, name=None):
    """Circular-pattern features/bodies about an axis through a full 360°.

    entities: iterable of Feature or BRepBody (all same type).
    quantity: total instance count including the original.
    """
    collection = adsk.core.ObjectCollection.create()
    for entity in entities:
        collection.add(entity)

    patterns = component.features.circularPatternFeatures
    pattern_input = patterns.createInput(collection, axis)
    if not pattern_input:
        raise RuntimeError('Failed to create circular pattern input.')

    pattern_input.quantity = adsk.core.ValueInput.createByReal(int(quantity))
    pattern_input.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    pattern_input.isSymmetric = False

    pattern = patterns.add(pattern_input)
    if not pattern:
        raise RuntimeError('Failed to create circular pattern.')

    if name:
        pattern.name = name
    return pattern
