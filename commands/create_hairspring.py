"""CREATE HAIRSPRING command.

Geometry strategy
-----------------
1. New component Hairspring
2. Archimedean spiral centerline points → fitted spline sketch
3. If Sketch Only: stop (editable centerline draft)
4. Else: offset strip edges (± width/2), fitted outer/inner splines + end caps
5. Extrude the closed strip profile by strip thickness

This is a geometry generator, not a balance-design solver.
"""

import traceback

import adsk.core

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_extrude, name_first_body
from fusion.parameters import set_user_parameter
from fusion.sketches import create_sketch_on_plane
from fusion.splines import add_fitted_spline
from geometry.spirals import (
    archimedean_spiral_points,
    offset_polyline_2d,
    spiral_pitch,
)

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_HAIRSPRING_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_HAIRSPRING_ID,
        defaults.CMD_CREATE_HAIRSPRING_NAME,
        defaults.CMD_CREATE_HAIRSPRING_TOOLTIP,
        '')

    on_created = CreateHairspringCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_HAIRSPRING_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_handedness(inputs):
    dropdown = inputs.itemById('handedness')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.HAIRSPRING_HANDEDNESS


def _apply_hairspring_ui(inputs):
    sketch_only = inputs.itemById('sketchOnly').value
    for input_id in ('stripWidth', 'stripThickness'):
        item = inputs.itemById(input_id)
        if item:
            item.isEnabled = not sketch_only


class CreateHairspringCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            inputs.addValueInput(
                'outerDiameter',
                'Outer Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.HAIRSPRING_OUTER_DIAMETER_MM)))

            inputs.addValueInput(
                'innerDiameter',
                'Inner Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.HAIRSPRING_INNER_DIAMETER_MM)))

            inputs.addValueInput(
                'turns',
                'Turns',
                '',
                adsk.core.ValueInput.createByReal(defaults.HAIRSPRING_TURNS))

            inputs.addValueInput(
                'stripWidth',
                'Strip Width',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.HAIRSPRING_STRIP_WIDTH_MM)))

            inputs.addValueInput(
                'stripThickness',
                'Strip Thickness',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.HAIRSPRING_STRIP_THICKNESS_MM)))

            hand = inputs.addDropDownCommandInput(
                'handedness',
                'Handedness',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            hand.listItems.add(
                'CCW', defaults.HAIRSPRING_HANDEDNESS.upper() == 'CCW')
            hand.listItems.add(
                'CW', defaults.HAIRSPRING_HANDEDNESS.upper() == 'CW')

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only (centerline)',
                True,
                '',
                defaults.HAIRSPRING_SKETCH_ONLY)

            _apply_hairspring_ui(inputs)

            # No live preview — spiral polylines are heavy and can crash Fusion.
            on_execute = CreateHairspringCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateHairspringCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateHairspringCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Hairspring dialog failed:\n{}'.format(traceback.format_exc()))


class CreateHairspringCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id == 'sketchOnly':
                _apply_hairspring_ui(args.inputs)
        except Exception:
            pass


class CreateHairspringCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _hairspring_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateHairspringCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_hairspring_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Hairspring failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _hairspring_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    outer = inputs.itemById('outerDiameter').value
    inner = inputs.itemById('innerDiameter').value
    turns = inputs.itemById('turns').value
    sketch_only = inputs.itemById('sketchOnly').value

    if not (outer > inner > 0 and turns > 0):
        return False
    if sketch_only:
        return True

    width = inputs.itemById('stripWidth').value
    thickness = inputs.itemById('stripThickness').value
    # Strip must fit between coils: pitch ≈ (ro-ri)/turns in radius terms.
    r_outer = outer * 0.5
    r_inner = inner * 0.5
    pitch = spiral_pitch(r_inner, r_outer, turns)
    return width > 0 and thickness > 0 and width < pitch * 0.95


def _execute_hairspring_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    execute_create_hairspring(
        outer_cm=inputs.itemById('outerDiameter').value,
        inner_cm=inputs.itemById('innerDiameter').value,
        turns=inputs.itemById('turns').value,
        strip_width_cm=inputs.itemById('stripWidth').value,
        strip_thickness_cm=inputs.itemById('stripThickness').value,
        handedness=_selected_handedness(inputs),
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_hairspring(outer_cm, inner_cm, turns, strip_width_cm,
                              strip_thickness_cm, handedness='CCW',
                              sketch_only=False):
    """Build hairspring geometry. Linear sizes in centimeters."""
    r_outer = float(outer_cm) * 0.5
    r_inner = float(inner_cm) * 0.5
    turns = float(turns)

    centerline = archimedean_spiral_points(
        r_inner,
        r_outer,
        turns,
        handedness=handedness,
        samples_per_turn=defaults.HAIRSPRING_SAMPLES_PER_TURN)

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_HAIRSPRING_OUTER_DIAMETER, outer_cm,
        comment='CREATE HAIRSPRING outer diameter')
    set_user_parameter(
        design, defaults.PARAM_HAIRSPRING_INNER_DIAMETER, inner_cm,
        comment='CREATE HAIRSPRING inner diameter')
    # Unitless turn count stored as a real length-less parameter via expression.
    params = design.userParameters
    existing_turns = params.itemByName(defaults.PARAM_HAIRSPRING_TURNS)
    turns_input = adsk.core.ValueInput.createByReal(turns)
    if existing_turns:
        existing_turns.expression = str(turns)
    else:
        params.add(
            defaults.PARAM_HAIRSPRING_TURNS, turns_input, '',
            'CREATE HAIRSPRING number of turns')

    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_HAIRSPRING_STRIP_WIDTH, strip_width_cm,
            comment='CREATE HAIRSPRING strip width')
        set_user_parameter(
            design, defaults.PARAM_HAIRSPRING_STRIP_THICKNESS, strip_thickness_cm,
            comment='CREATE HAIRSPRING strip thickness')

    _occ, component = create_component(design, defaults.HAIRSPRING_COMPONENT_NAME)

    if sketch_only:
        sketch = create_sketch_on_plane(
            component, component.xYConstructionPlane,
            name=defaults.HAIRSPRING_CENTERLINE_SKETCH_NAME)
        add_fitted_spline(sketch, centerline, name='Centerline')
        sketch.isVisible = True
        return component, sketch, None

    half_w = float(strip_width_cm) * 0.5
    pitch = spiral_pitch(r_inner, r_outer, turns)
    if half_w * 2 >= pitch:
        raise ValueError(
            'Strip width ({:.4g} cm) is too wide for spiral pitch ({:.4g} cm). '
            'Reduce width, increase OD, or reduce turns.'.format(
                strip_width_cm, pitch))

    outer_pts = offset_polyline_2d(centerline, half_w)
    inner_pts = offset_polyline_2d(centerline, -half_w)

    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane,
        name=defaults.HAIRSPRING_PROFILE_SKETCH_NAME)

    outer_spline = add_fitted_spline(sketch, outer_pts, name='OuterEdge')
    # Reverse inner so the closed loop travels consistently.
    inner_rev = list(reversed(inner_pts))
    inner_spline = add_fitted_spline(sketch, inner_rev, name='InnerEdge')

    lines = sketch.sketchCurves.sketchLines
    # Cap at outer end: outer end → inner end (inner_rev start).
    lines.addByTwoPoints(
        outer_spline.endSketchPoint, inner_spline.startSketchPoint)
    # Cap at inner end: inner start (inner_rev end) → outer start.
    lines.addByTwoPoints(
        inner_spline.endSketchPoint, outer_spline.startSketchPoint)

    if sketch.profiles.count < 1:
        raise RuntimeError(
            'Hairspring strip sketch has no profile. '
            'Try fewer turns or a slightly wider pitch.')

    # Prefer the profile with the largest area (the strip ribbon).
    profile = sketch.profiles.item(0)
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if area > best_area:
            best_area = area
            profile = candidate

    extrude = create_extrude(
        component,
        profile,
        distance_cm=strip_thickness_cm,
        name=defaults.HAIRSPRING_EXTRUDE_NAME,
        expression=defaults.PARAM_HAIRSPRING_STRIP_THICKNESS)
    body = name_first_body(extrude, defaults.HAIRSPRING_BODY_NAME)
    return component, sketch, body
