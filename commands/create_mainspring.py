"""CREATE MAINSPRING command.

Geometry strategy
-----------------
1. New component Mainspring
2. Archimedean spiral centerline (CW or CCW) → fitted spline
3. Sketch Only: stop after centerline
4. Else: offset blade edges (± half blade thickness), end caps, extrude spring height

Handedness is swappable in the dialog:
  Clockwise (CW) / Counterclockwise (CCW)

Geometry generator only — not a barrel torque / turns calculator.
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

# Dialog labels ↔ internal spiral codes used by geometry.spirals
_HAND_LABEL_TO_CODE = {
    'Clockwise (CW)': 'CW',
    'Counterclockwise (CCW)': 'CCW',
}
_HAND_CODE_TO_LABEL = {
    'CW': 'Clockwise (CW)',
    'CCW': 'Counterclockwise (CCW)',
}


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_MAINSPRING_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_MAINSPRING_ID,
        defaults.CMD_CREATE_MAINSPRING_NAME,
        defaults.CMD_CREATE_MAINSPRING_TOOLTIP,
        '')

    on_created = CreateMainspringCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_MAINSPRING_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_handedness_code(inputs):
    dropdown = inputs.itemById('handedness')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return _HAND_LABEL_TO_CODE.get(item.name, item.name)
    return defaults.MAINSPRING_HANDEDNESS


def _apply_mainspring_ui(inputs):
    sketch_only = inputs.itemById('sketchOnly').value
    for input_id in ('bladeThickness', 'springHeight'):
        item = inputs.itemById(input_id)
        if item:
            item.isEnabled = not sketch_only


class CreateMainspringCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
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
                    mm_to_cm(defaults.MAINSPRING_OUTER_DIAMETER_MM)))

            inputs.addValueInput(
                'innerDiameter',
                'Inner Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.MAINSPRING_INNER_DIAMETER_MM)))

            inputs.addValueInput(
                'turns',
                'Turns',
                '',
                adsk.core.ValueInput.createByReal(defaults.MAINSPRING_TURNS))

            inputs.addValueInput(
                'bladeThickness',
                'Blade Thickness',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.MAINSPRING_BLADE_THICKNESS_MM)))

            inputs.addValueInput(
                'springHeight',
                'Spring Height',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.MAINSPRING_SPRING_HEIGHT_MM)))

            # Explicit CW/CCW swap control.
            hand = inputs.addDropDownCommandInput(
                'handedness',
                'Winding Direction',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            default_label = _HAND_CODE_TO_LABEL.get(
                defaults.MAINSPRING_HANDEDNESS.upper(), 'Clockwise (CW)')
            for label in ('Clockwise (CW)', 'Counterclockwise (CCW)'):
                hand.listItems.add(label, label == default_label)

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only (centerline)',
                True,
                '',
                defaults.MAINSPRING_SKETCH_ONLY)

            _apply_mainspring_ui(inputs)

            # No live preview — spiral polylines are heavy and can crash Fusion.
            on_execute = CreateMainspringCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateMainspringCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateMainspringCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Mainspring dialog failed:\n{}'.format(traceback.format_exc()))


class CreateMainspringCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id == 'sketchOnly':
                _apply_mainspring_ui(args.inputs)
        except Exception:
            pass


class CreateMainspringCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _mainspring_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateMainspringCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_mainspring_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Mainspring failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _mainspring_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    outer = inputs.itemById('outerDiameter').value
    inner = inputs.itemById('innerDiameter').value
    turns = inputs.itemById('turns').value
    sketch_only = inputs.itemById('sketchOnly').value

    if not (outer > inner > 0 and turns > 0):
        return False
    if sketch_only:
        return True

    blade = inputs.itemById('bladeThickness').value
    height = inputs.itemById('springHeight').value
    pitch = spiral_pitch(inner * 0.5, outer * 0.5, turns)
    return blade > 0 and height > 0 and blade < pitch * 0.95


def _execute_mainspring_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    execute_create_mainspring(
        outer_cm=inputs.itemById('outerDiameter').value,
        inner_cm=inputs.itemById('innerDiameter').value,
        turns=inputs.itemById('turns').value,
        blade_thickness_cm=inputs.itemById('bladeThickness').value,
        spring_height_cm=inputs.itemById('springHeight').value,
        handedness=_selected_handedness_code(inputs),
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_mainspring(outer_cm, inner_cm, turns, blade_thickness_cm,
                              spring_height_cm, handedness='CW',
                              sketch_only=False):
    """Build mainspring geometry. Linear sizes in centimeters.

    handedness: 'CW' or 'CCW'
    """
    r_outer = float(outer_cm) * 0.5
    r_inner = float(inner_cm) * 0.5
    turns = float(turns)
    hand = 'CW' if str(handedness).upper() == 'CW' else 'CCW'

    centerline = archimedean_spiral_points(
        r_inner,
        r_outer,
        turns,
        handedness=hand,
        samples_per_turn=defaults.MAINSPRING_SAMPLES_PER_TURN)

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_MAINSPRING_OUTER_DIAMETER, outer_cm,
        comment='CREATE MAINSPRING outer diameter')
    set_user_parameter(
        design, defaults.PARAM_MAINSPRING_INNER_DIAMETER, inner_cm,
        comment='CREATE MAINSPRING inner diameter')

    params = design.userParameters
    existing_turns = params.itemByName(defaults.PARAM_MAINSPRING_TURNS)
    turns_input = adsk.core.ValueInput.createByReal(turns)
    if existing_turns:
        existing_turns.expression = str(turns)
    else:
        params.add(
            defaults.PARAM_MAINSPRING_TURNS, turns_input, '',
            'CREATE MAINSPRING number of turns')

    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_MAINSPRING_BLADE_THICKNESS, blade_thickness_cm,
            comment='CREATE MAINSPRING blade thickness (in-plane)')
        set_user_parameter(
            design, defaults.PARAM_MAINSPRING_SPRING_HEIGHT, spring_height_cm,
            comment='CREATE MAINSPRING spring height (extrude)')

    _occ, component = create_component(design, defaults.MAINSPRING_COMPONENT_NAME)
    # Encode handedness in the component name for quick browser identification.
    component.name = '{}_{}'.format(defaults.MAINSPRING_COMPONENT_NAME, hand)

    if sketch_only:
        sketch = create_sketch_on_plane(
            component, component.xYConstructionPlane,
            name=defaults.MAINSPRING_CENTERLINE_SKETCH_NAME)
        add_fitted_spline(sketch, centerline, name='Centerline_{}'.format(hand))
        sketch.isVisible = True
        return component, sketch, None

    half_blade = float(blade_thickness_cm) * 0.5
    pitch = spiral_pitch(r_inner, r_outer, turns)
    if half_blade * 2 >= pitch:
        raise ValueError(
            'Blade thickness ({:.4g} cm) is too wide for spiral pitch ({:.4g} cm). '
            'Reduce blade thickness, increase OD, or reduce turns.'.format(
                blade_thickness_cm, pitch))

    outer_pts = offset_polyline_2d(centerline, half_blade)
    inner_pts = offset_polyline_2d(centerline, -half_blade)

    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane,
        name=defaults.MAINSPRING_PROFILE_SKETCH_NAME)

    outer_spline = add_fitted_spline(sketch, outer_pts, name='OuterEdge')
    inner_rev = list(reversed(inner_pts))
    inner_spline = add_fitted_spline(sketch, inner_rev, name='InnerEdge')

    lines = sketch.sketchCurves.sketchLines
    lines.addByTwoPoints(
        outer_spline.endSketchPoint, inner_spline.startSketchPoint)
    lines.addByTwoPoints(
        inner_spline.endSketchPoint, outer_spline.startSketchPoint)

    if sketch.profiles.count < 1:
        raise RuntimeError(
            'Mainspring strip sketch has no profile. '
            'Try fewer turns or a slightly wider pitch.')

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
        distance_cm=spring_height_cm,
        name=defaults.MAINSPRING_EXTRUDE_NAME,
        expression=defaults.PARAM_MAINSPRING_SPRING_HEIGHT)
    body = name_first_body(extrude, defaults.MAINSPRING_BODY_NAME)
    return component, sketch, body
