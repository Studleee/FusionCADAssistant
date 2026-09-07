"""CREATE RING GEAR — differential-style crown / face ring gear (90° mesh).

Teeth sit on the outer ring with their broad side facing out (OD) and tips
pointing up (+Z). Each period is a tooth plus a U-arc pit, extruded OD→ID,
then circular-patterned and joined to the blank.
"""

import math
import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import (
    create_circular_pattern,
    create_constant_fillet,
    create_extrude,
    name_first_body,
)
from fusion.parameters import set_user_parameter
from fusion.polylines import add_polyline
from fusion.sketches import (
    create_circle,
    create_sketch_on_plane,
    create_yz_offset_plane,
)
from geometry.gears import (
    PROFILE_CYCLOIDAL,
    PROFILE_INVOLUTE,
    _u_root_fillet,
    gear_one_tooth_points,
)

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_RING_GEAR_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_RING_GEAR_ID,
        defaults.CMD_CREATE_RING_GEAR_NAME,
        defaults.CMD_CREATE_RING_GEAR_TOOLTIP,
        '')

    on_created = CreateRingGearCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_RING_GEAR_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_profile(inputs):
    dropdown = inputs.itemById('toothProfile')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.RING_GEAR_DEFAULT_PROFILE


def _profile_code(label):
    if label == defaults.RING_GEAR_PROFILE_CYCLOIDAL:
        return PROFILE_CYCLOIDAL
    return PROFILE_INVOLUTE


def _apply_ring_gear_ui(inputs):
    sketch_only = inputs.itemById('sketchOnly').value
    for input_id in ('ringThickness', 'toothHeight'):
        item = inputs.itemById(input_id)
        if item:
            item.isEnabled = not sketch_only

    is_involute = _selected_profile(inputs) == defaults.RING_GEAR_PROFILE_INVOLUTE
    pa = inputs.itemById('pressureAngle')
    if pa:
        pa.isVisible = is_involute
        pa.isEnabled = is_involute


class CreateRingGearCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            inputs.addValueInput(
                'outsideDiameter',
                'Outside Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.RING_GEAR_OUTSIDE_DIAMETER_MM)))

            inputs.addValueInput(
                'innerDiameter',
                'Inner Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.RING_GEAR_INNER_DIAMETER_MM)))

            inputs.addIntegerSpinnerCommandInput(
                'teeth',
                'Tooth Count',
                12,
                300,
                1,
                int(defaults.RING_GEAR_TEETH))

            profile = inputs.addDropDownCommandInput(
                'toothProfile',
                'Tooth Profile',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.RING_GEAR_PROFILE_CYCLOIDAL,
                    defaults.RING_GEAR_PROFILE_INVOLUTE):
                profile.listItems.add(
                    label, label == defaults.RING_GEAR_DEFAULT_PROFILE)

            inputs.addValueInput(
                'ringThickness',
                'Ring Thickness',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.RING_GEAR_RING_THICKNESS_MM)))

            inputs.addValueInput(
                'toothHeight',
                'Tooth Height',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.RING_GEAR_TOOTH_HEIGHT_MM)))

            inputs.addValueInput(
                'pressureAngle',
                'Pressure Angle',
                'deg',
                adsk.core.ValueInput.createByReal(
                    math.radians(defaults.RING_GEAR_PRESSURE_ANGLE_DEG)))

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.RING_GEAR_SKETCH_ONLY)

            _apply_ring_gear_ui(inputs)

            on_preview = CreateRingGearCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreateRingGearCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateRingGearCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateRingGearCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Ring Gear dialog failed:\n{}'.format(
                        traceback.format_exc()))


class CreateRingGearCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id in ('sketchOnly', 'toothProfile'):
                _apply_ring_gear_ui(args.inputs)
        except Exception:
            pass


class CreateRingGearCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _ring_gear_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateRingGearCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            if not _ring_gear_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_ring_gear_from_inputs(inputs)
            args.isValidResult = True
        except Exception as exc:
            args.isValidResult = False
            app = adsk.core.Application.get()
            if app:
                try:
                    app.log('Create Ring Gear preview failed: {}'.format(exc))
                except Exception:
                    pass


class CreateRingGearCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_ring_gear_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Ring Gear failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _ring_gear_inputs_are_valid(inputs):
    od = inputs.itemById('outsideDiameter').value
    inner = inputs.itemById('innerDiameter').value
    teeth = inputs.itemById('teeth').value
    sketch_only = inputs.itemById('sketchOnly').value
    profile = _selected_profile(inputs)

    if od <= 0 or inner <= 0 or inner >= od or teeth < 12:
        return False
    if profile == defaults.RING_GEAR_PROFILE_INVOLUTE:
        pa_deg = math.degrees(inputs.itemById('pressureAngle').value)
        if not (5.0 <= pa_deg <= 30.0):
            return False
    if sketch_only:
        return True
    return (
        inputs.itemById('ringThickness').value > 0
        and inputs.itemById('toothHeight').value > 0)


def _execute_ring_gear_from_inputs(inputs):
    pa_deg = math.degrees(inputs.itemById('pressureAngle').value)
    execute_create_ring_gear(
        outside_cm=inputs.itemById('outsideDiameter').value,
        inner_cm=inputs.itemById('innerDiameter').value,
        teeth=int(inputs.itemById('teeth').value),
        ring_thickness_cm=inputs.itemById('ringThickness').value,
        tooth_height_cm=inputs.itemById('toothHeight').value,
        pressure_angle_deg=pa_deg,
        profile=_profile_code(_selected_profile(inputs)),
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_ring_gear(outside_cm, inner_cm, teeth, ring_thickness_cm,
                             tooth_height_cm, pressure_angle_deg=20.0,
                             profile=PROFILE_CYCLOIDAL, sketch_only=False):
    """Build a 90° crown / differential-style ring gear. Sizes in centimeters."""
    teeth = int(teeth)
    if teeth < 12:
        raise ValueError('Ring gear tooth count must be at least 12.')
    if outside_cm <= 0:
        raise ValueError('Outside diameter must be greater than zero.')
    if inner_cm <= 0 or inner_cm >= outside_cm:
        raise ValueError('Inner diameter must be between zero and outside diameter.')

    ra = outside_cm * 0.5
    ri = inner_cm * 0.5
    # Module only — final Z seating is computed from the blank body top.
    _tooth_preview, module_cm = _od_tooth_period_with_arc_pits(
        outside_cm, teeth, 0.0, tooth_height_cm,
        profile=profile, pressure_angle_deg=pressure_angle_deg)

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_RING_GEAR_OUTSIDE_DIAMETER, outside_cm,
        comment='CREATE RING GEAR outside / tip diameter')
    set_user_parameter(
        design, defaults.PARAM_RING_GEAR_INNER_DIAMETER, inner_cm,
        comment='CREATE RING GEAR inner diameter')
    set_user_parameter(
        design, defaults.PARAM_RING_GEAR_MODULE, module_cm,
        comment='CREATE RING GEAR module (derived from OD and teeth)')
    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_RING_GEAR_RING_THICKNESS, ring_thickness_cm,
            comment='CREATE RING GEAR blank thickness')
        set_user_parameter(
            design, defaults.PARAM_RING_GEAR_TOOTH_HEIGHT, tooth_height_cm,
            comment='CREATE RING GEAR face tooth height (90°)')

    params = design.userParameters
    existing_teeth = params.itemByName(defaults.PARAM_RING_GEAR_TEETH)
    teeth_vi = adsk.core.ValueInput.createByReal(float(teeth))
    if existing_teeth:
        existing_teeth.expression = str(int(teeth))
    else:
        params.add(
            defaults.PARAM_RING_GEAR_TEETH, teeth_vi, '',
            'CREATE RING GEAR tooth count')

    if profile == PROFILE_INVOLUTE:
        existing_pa = params.itemByName(defaults.PARAM_RING_GEAR_PRESSURE_ANGLE)
        if existing_pa:
            existing_pa.expression = '{} deg'.format(pressure_angle_deg)
        else:
            try:
                params.add(
                    defaults.PARAM_RING_GEAR_PRESSURE_ANGLE,
                    adsk.core.ValueInput.createByString(
                        '{} deg'.format(pressure_angle_deg)),
                    'deg',
                    'CREATE RING GEAR pressure angle')
            except Exception:
                pass

    tag = 'Cyc' if profile == PROFILE_CYCLOIDAL else 'Inv'
    _occ, component = create_component(design, defaults.RING_GEAR_COMPONENT_NAME)
    component.name = 'RingGear_{}T_90_{}'.format(teeth, tag)

    blank_sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane,
        name=defaults.RING_GEAR_BLANK_SKETCH_NAME)
    create_circle(blank_sketch, blank_sketch.originPoint, outside_cm * 0.5)
    create_circle(blank_sketch, blank_sketch.originPoint, inner_cm * 0.5)

    if sketch_only:
        od_plane = create_yz_offset_plane(component, ra)
        tooth_sketch = create_sketch_on_plane(
            component, od_plane, name=defaults.RING_GEAR_TOOTH_SKETCH_NAME)
        _add_model_polyline(tooth_sketch, _tooth_preview, close_loop=True)
        blank_sketch.isVisible = True
        tooth_sketch.isVisible = True
        return component, blank_sketch, None, module_cm

    if ring_thickness_cm <= 0:
        raise ValueError('Ring thickness must be greater than zero.')
    if tooth_height_cm <= 0:
        raise ValueError('Tooth height must be greater than zero.')
    if ra - ri <= 0:
        raise ValueError('Outside diameter must be larger than inner diameter.')

    blank_profile = _annular_profile(blank_sketch)
    # Use the numeric distance (not the user-parameter expression) so tooth Z
    # seating matches the blank top exactly.
    blank_extrude = create_extrude(
        component,
        blank_profile,
        distance_cm=ring_thickness_cm,
        name=defaults.RING_GEAR_BLANK_EXTRUDE_NAME)
    body = name_first_body(blank_extrude, defaults.RING_GEAR_BODY_NAME)

    z_top = float(body.boundingBox.maxPoint.z)
    # Sink root feet into the plate so Join has volume overlap (coplanar
    # contact left a visible hairline gap under the teeth).
    embed_cm = min(0.05, max(float(tooth_height_cm) * 0.15, 0.02))
    tooth_od, _module = _od_tooth_period_with_arc_pits(
        outside_cm, teeth,
        z_base=z_top - embed_cm,
        tooth_height=float(tooth_height_cm) + embed_cm,
        profile=profile, pressure_angle_deg=pressure_angle_deg)

    od_plane = create_yz_offset_plane(component, ra)
    od_sketch = create_sketch_on_plane(
        component, od_plane, name=defaults.RING_GEAR_TOOTH_SKETCH_NAME)
    _add_model_polyline(od_sketch, tooth_od, close_loop=True)
    od_profile = _largest_profile(od_sketch)
    if od_profile is None:
        raise RuntimeError('Ring gear OD tooth sketch has no profile.')

    tooth_ext = _extrude_join_into_ring(
        component, od_profile, ra - ri, [body],
        name=defaults.RING_GEAR_TOOTH_EXTRUDE_NAME)

    create_circular_pattern(
        component,
        [tooth_ext],
        component.zConstructionAxis,
        teeth,
        name=defaults.RING_GEAR_TOOTH_PATTERN_NAME)

    # Little cove arcs where tooth walls meet the plate (watch-style roots).
    _add_tooth_plate_root_fillets(
        component, body, z_top, ra, ri, tooth_height_cm, module_cm)

    return component, blank_sketch, body, module_cm


def _largest_profile(sketch):
    """Return the largest closed profile in a sketch, or None."""
    best = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if area > best_area:
            best_area = area
            best = candidate
    return best


def _add_tooth_plate_root_fillets(component, body, z_top, ra, ri,
                                  tooth_height_cm, module_cm):
    """Fillet the edges where tooth flanks meet the blank top face."""
    radius = min(
        float(tooth_height_cm) * 0.45,
        float(module_cm) * 0.75,
        0.12,
        max(float(ra) - float(ri), 0.0) * 0.25)
    if radius < 0.01:
        return

    edges = _find_plate_tooth_junction_edges(body, z_top, ra, ri)
    if not edges:
        return
    try:
        create_constant_fillet(
            component, edges, radius,
            name=defaults.RING_GEAR_ROOT_FILLET_NAME)
    except Exception:
        # Fillet can fail on dense faceted edges — teeth still usable without it.
        pass


def _find_plate_tooth_junction_edges(body, z_top, ra, ri, tol_cm=0.05):
    """Edges on the plate top that join a horizontal face to a tooth wall."""
    plane_type = adsk.core.Plane.classType()
    z_top = float(z_top)
    ra = float(ra)
    ri = float(ri)
    tol = float(tol_cm)
    found = []
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        try:
            sp = edge.startVertex.geometry
            ep = edge.endVertex.geometry
        except Exception:
            continue
        if abs(0.5 * (float(sp.z) + float(ep.z)) - z_top) > tol:
            continue
        if abs(float(sp.z) - float(ep.z)) > tol * 2.0:
            continue
        r0 = math.hypot(float(sp.x), float(sp.y))
        r1 = math.hypot(float(ep.x), float(ep.y))
        # Skip blank OD / ID rim circles on the top face.
        if abs(r0 - ra) <= tol and abs(r1 - ra) <= tol:
            continue
        if abs(r0 - ri) <= tol and abs(r1 - ri) <= tol:
            continue
        if not _edge_joins_plate_and_wall(edge, plane_type):
            continue
        found.append(edge)
    return found


def _edge_joins_plate_and_wall(edge, plane_type):
    """True if the edge bounds a near-horizontal plate face and a tooth wall."""
    try:
        faces = edge.faces
    except Exception:
        return False
    has_plate = False
    has_wall = False
    for j in range(faces.count):
        face = faces.item(j)
        geom = face.geometry
        if not geom:
            continue
        if geom.objectType == plane_type:
            try:
                nz = abs(float(geom.normal.z))
            except Exception:
                continue
            if nz > 0.85:
                has_plate = True
            elif nz < 0.55:
                has_wall = True
        else:
            has_wall = True
    return has_plate and has_wall


def _extrude_join_into_ring(component, profile, depth_cm, participant_bodies,
                            name=None):
    """Join-extrude opposite the sketch-plane normal (OD toward ID)."""
    if depth_cm <= 0:
        raise ValueError('Tooth radial depth must be greater than zero.')
    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profile, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    if not ext_input:
        raise RuntimeError('Failed to create tooth extrude input.')
    # distanceOne = +normal, distanceTwo = -normal. OD plane normal is +X,
    # so -normal carries the tooth into the ring toward the ID.
    ext_input.setTwoSidesDistanceExtent(
        adsk.core.ValueInput.createByReal(0.0),
        adsk.core.ValueInput.createByReal(float(depth_cm)))
    ext_input.isSolid = True
    if participant_bodies:
        ext_input.participantBodies = list(participant_bodies)
    extrude = extrudes.add(ext_input)
    if not extrude:
        raise RuntimeError('Failed to extrude ring-gear tooth.')
    if name:
        extrude.name = name
    return extrude


def _od_tooth_period_with_arc_pits(outside_cm, teeth, z_base, tooth_height,
                                  profile=PROFILE_CYCLOIDAL,
                                  pressure_angle_deg=20.0):
    """One pitch on the OD face: tooth (tips up) + U-arc pit.

    Uses normal cycloidal/involute tooth flanks (not the wide base-slope look).
    The pit between teeth is the gear root fillet arc, mapped onto the face.
    """
    tooth, module_cm, _d, root_dia = gear_one_tooth_points(
        outside_cm, teeth,
        profile=profile,
        pressure_angle_deg=pressure_angle_deg)
    ra = float(outside_cm) * 0.5
    rf = float(root_dia) * 0.5
    pitch = 2.0 * math.pi / float(teeth)

    tpts = list(tooth[:-1]) if (
        len(tooth) > 1 and tooth[0] == tooth[-1]) else list(tooth)

    a_left = math.atan2(tpts[0][1], tpts[0][0])
    a_right = math.atan2(tpts[-1][1], tpts[-1][0])
    a_next_left = a_left + pitch
    while a_next_left <= a_right:
        a_next_left += 2.0 * math.pi
    gullet = _u_root_fillet(rf, a_right, a_next_left, 8)

    chain = tpts + list(gullet[1:])
    od_pts = _map_xy_chain_to_od_face(chain, ra, rf, z_base, tooth_height)
    if od_pts and od_pts[0] != od_pts[-1]:
        od_pts.append(od_pts[0])
    return od_pts, module_cm


def _map_xy_chain_to_od_face(chain_xy, ra, rf, z_base, tooth_height):
    """Map planar gear points onto OD face: tip up (+Z), side out (+X).

    Root radius rf → blank top (z_base). Tip radius → z_base + tooth_height.
    Gullet points with r < rf go below the plate so pits cut into the ring.
    Unwrapped polar angle → tangential Y.
    """
    ra = float(ra)
    rf = float(rf)
    z0 = float(z_base)
    h = float(tooth_height)
    tip_span = max(ra - rf, 1e-9)

    angs = [math.atan2(p[1], p[0]) for p in chain_xy]
    unwrapped = [angs[0]]
    for a in angs[1:]:
        aa = a
        while aa < unwrapped[-1] - math.pi:
            aa += 2.0 * math.pi
        while aa > unwrapped[-1] + math.pi:
            aa -= 2.0 * math.pi
        unwrapped.append(aa)

    mid_ang = 0.5 * (unwrapped[0] + unwrapped[-1])
    pts = []
    for p, ang in zip(chain_xy, unwrapped):
        r = math.hypot(p[0], p[1])
        tip_h = (r - rf) / tip_span * h
        y_t = ra * (ang - mid_ang)
        pts.append((ra, y_t, z0 + tip_h))
    return pts


def _add_model_polyline(sketch, model_pts, close_loop=True):
    """Draw a polyline from model-space points (converts into sketch space)."""
    sk_pts = []
    for x, y, z in model_pts:
        p = sketch.modelToSketchSpace(
            adsk.core.Point3D.create(float(x), float(y), float(z)))
        sk_pts.append((p.x, p.y, p.z))
    return add_polyline(sketch, sk_pts, close_loop=close_loop)


def _annular_profile(sketch):
    """Largest two-loop profile (ring between OD and ID)."""
    best = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        if candidate.profileLoops.count < 2:
            continue
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if area > best_area:
            best_area = area
            best = candidate
    if best is None:
        raise RuntimeError('Ring blank sketch has no annular profile.')
    return best
