"""CREATE PINION command — watch pinion leaves for mating with wheels.

Geometry strategy
-----------------
Same spur outline as Create Wheel (shared geometry.gears): Involute or Cycloidal.

Sizing modes:
  1. By Outside Diameter — OD + leaf count
  2. By Module — module + leaf count → OD = m*(z+2)
  3. Match Wheel Module — wheel OD + wheel teeth → module, then pinion leaves

This keeps pinion/wheel pairs on the same module for meshing.
"""

import math
import traceback

import adsk.core

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_extrude, name_first_body
from fusion.parameters import set_user_parameter
from fusion.polylines import add_polyline
from fusion.sketches import create_circle, create_sketch_on_plane
from geometry.gears import (
    PROFILE_CYCLOIDAL,
    PROFILE_INVOLUTE,
    gear_outline_points,
    module_from_outside_diameter,
    outside_diameter_from_module,
)

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_PINION_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_PINION_ID,
        defaults.CMD_CREATE_PINION_NAME,
        defaults.CMD_CREATE_PINION_TOOLTIP,
        '')

    on_created = CreatePinionCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_PINION_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_size_mode(inputs):
    dropdown = inputs.itemById('sizeMode')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.PINION_DEFAULT_SIZE_MODE


def _selected_profile(inputs):
    dropdown = inputs.itemById('toothProfile')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.PINION_DEFAULT_PROFILE


def _profile_code(label):
    if label == defaults.PINION_PROFILE_CYCLOIDAL:
        return PROFILE_CYCLOIDAL
    return PROFILE_INVOLUTE


def _apply_pinion_ui(inputs):
    mode = _selected_size_mode(inputs)
    sketch_only = inputs.itemById('sketchOnly').value

    by_od = mode == defaults.PINION_SIZE_BY_OD
    by_mod = mode == defaults.PINION_SIZE_BY_MODULE
    match = mode == defaults.PINION_SIZE_MATCH_WHEEL

    inputs.itemById('outsideDiameter').isVisible = by_od
    inputs.itemById('module').isVisible = by_mod
    inputs.itemById('wheelOutsideDiameter').isVisible = match
    inputs.itemById('wheelTeeth').isVisible = match

    face = inputs.itemById('faceWidth')
    if face:
        face.isEnabled = not sketch_only

    is_involute = _selected_profile(inputs) == defaults.PINION_PROFILE_INVOLUTE
    pa = inputs.itemById('pressureAngle')
    if pa:
        pa.isVisible = is_involute
        pa.isEnabled = is_involute


class CreatePinionCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            mode = inputs.addDropDownCommandInput(
                'sizeMode',
                'Sizing',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.PINION_SIZE_BY_OD,
                    defaults.PINION_SIZE_BY_MODULE,
                    defaults.PINION_SIZE_MATCH_WHEEL):
                mode.listItems.add(
                    label, label == defaults.PINION_DEFAULT_SIZE_MODE)

            inputs.addValueInput(
                'outsideDiameter',
                'Outside Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PINION_OUTSIDE_DIAMETER_MM)))

            inputs.addValueInput(
                'module',
                'Module',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PINION_MODULE_MM)))

            inputs.addValueInput(
                'wheelOutsideDiameter',
                'Wheel Outside Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PINION_MATCH_WHEEL_OD_MM)))

            inputs.addIntegerSpinnerCommandInput(
                'wheelTeeth',
                'Wheel Tooth Count',
                6,
                300,
                1,
                int(defaults.PINION_MATCH_WHEEL_TEETH))

            inputs.addIntegerSpinnerCommandInput(
                'leaves',
                'Leaf Count',
                6,
                40,
                1,
                int(defaults.PINION_LEAVES))

            profile = inputs.addDropDownCommandInput(
                'toothProfile',
                'Tooth Profile',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.PINION_PROFILE_CYCLOIDAL,
                    defaults.PINION_PROFILE_INVOLUTE):
                profile.listItems.add(
                    label, label == defaults.PINION_DEFAULT_PROFILE)

            inputs.addValueInput(
                'faceWidth',
                'Face Width',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PINION_FACE_WIDTH_MM)))

            inputs.addValueInput(
                'boreDiameter',
                'Bore / Pivot Hole',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PINION_BORE_DIAMETER_MM)))

            inputs.addValueInput(
                'pressureAngle',
                'Pressure Angle',
                'deg',
                adsk.core.ValueInput.createByReal(
                    math.radians(defaults.PINION_PRESSURE_ANGLE_DEG)))

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.PINION_SKETCH_ONLY)

            _apply_pinion_ui(inputs)

            # No executePreview: dense tooth outlines + live rebuild crash Fusion.
            on_execute = CreatePinionCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreatePinionCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreatePinionCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Pinion dialog failed:\n{}'.format(traceback.format_exc()))


class CreatePinionCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id in ('sizeMode', 'sketchOnly', 'toothProfile'):
                _apply_pinion_ui(args.inputs)
        except Exception:
            pass


class CreatePinionCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _pinion_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreatePinionCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        # Fallback execute (no live preview on this command).
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_pinion_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Pinion failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _pinion_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    mode = _selected_size_mode(inputs)
    leaves = int(inputs.itemById('leaves').value)
    bore = inputs.itemById('boreDiameter').value
    sketch_only = inputs.itemById('sketchOnly').value
    profile = _selected_profile(inputs)

    if leaves < 6 or bore < 0:
        return False
    if profile == defaults.PINION_PROFILE_INVOLUTE:
        pa_deg = math.degrees(inputs.itemById('pressureAngle').value)
        if not (5.0 <= pa_deg <= 30.0):
            return False

    if mode == defaults.PINION_SIZE_BY_OD:
        od = inputs.itemById('outsideDiameter').value
        if od <= 0 or bore >= od:
            return False
    elif mode == defaults.PINION_SIZE_BY_MODULE:
        if inputs.itemById('module').value <= 0:
            return False
    else:
        wod = inputs.itemById('wheelOutsideDiameter').value
        wt = int(inputs.itemById('wheelTeeth').value)
        if wod <= 0 or wt < 6:
            return False

    if sketch_only:
        return True
    return inputs.itemById('faceWidth').value > 0


def _execute_pinion_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    mode = _selected_size_mode(inputs)
    leaves = int(inputs.itemById('leaves').value)
    pa_deg = math.degrees(inputs.itemById('pressureAngle').value)

    if mode == defaults.PINION_SIZE_BY_OD:
        outside_cm = inputs.itemById('outsideDiameter').value
        module_cm = module_from_outside_diameter(outside_cm, leaves)
    elif mode == defaults.PINION_SIZE_BY_MODULE:
        module_cm = inputs.itemById('module').value
        outside_cm = outside_diameter_from_module(module_cm, leaves)
    else:
        wheel_od = inputs.itemById('wheelOutsideDiameter').value
        wheel_teeth = int(inputs.itemById('wheelTeeth').value)
        module_cm = module_from_outside_diameter(wheel_od, wheel_teeth)
        outside_cm = outside_diameter_from_module(module_cm, leaves)

    execute_create_pinion(
        outside_cm=outside_cm,
        leaves=leaves,
        face_width_cm=inputs.itemById('faceWidth').value,
        bore_cm=inputs.itemById('boreDiameter').value,
        pressure_angle_deg=pa_deg,
        module_cm=module_cm,
        profile=_profile_code(_selected_profile(inputs)),
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_pinion(outside_cm, leaves, face_width_cm, bore_cm=0.0,
                          pressure_angle_deg=20.0, module_cm=None,
                          profile=PROFILE_CYCLOIDAL, sketch_only=False):
    """Build a pinion (involute or cycloidal). Sizes in centimeters."""
    leaves = int(leaves)
    outline, derived_module, _pitch_dia, root_dia = gear_outline_points(
        outside_cm, leaves,
        profile=profile,
        pressure_angle_deg=pressure_angle_deg)
    if module_cm is None:
        module_cm = derived_module

    if bore_cm < 0:
        raise ValueError('Bore diameter cannot be negative.')
    if bore_cm > 0 and bore_cm >= root_dia * 0.95:
        raise ValueError(
            'Bore / pivot hole is too large for this pinion root diameter '
            '({:.3f} cm).'.format(root_dia))

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_PINION_OUTSIDE_DIAMETER, outside_cm,
        comment='CREATE PINION outside / tip diameter')
    set_user_parameter(
        design, defaults.PARAM_PINION_MODULE, module_cm,
        comment='CREATE PINION module')
    set_user_parameter(
        design, defaults.PARAM_PINION_BORE_DIAMETER, max(bore_cm, 0.0),
        comment='CREATE PINION bore / pivot hole')
    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_PINION_FACE_WIDTH, face_width_cm,
            comment='CREATE PINION face width')

    params = design.userParameters
    existing_leaves = params.itemByName(defaults.PARAM_PINION_LEAVES)
    leaves_vi = adsk.core.ValueInput.createByReal(float(leaves))
    if existing_leaves:
        existing_leaves.expression = str(int(leaves))
    else:
        params.add(
            defaults.PARAM_PINION_LEAVES, leaves_vi, '',
            'CREATE PINION leaf count')

    if profile == PROFILE_INVOLUTE:
        existing_pa = params.itemByName(defaults.PARAM_PINION_PRESSURE_ANGLE)
        if existing_pa:
            existing_pa.expression = '{} deg'.format(pressure_angle_deg)
        else:
            try:
                params.add(
                    defaults.PARAM_PINION_PRESSURE_ANGLE,
                    adsk.core.ValueInput.createByString(
                        '{} deg'.format(pressure_angle_deg)),
                    'deg',
                    'CREATE PINION pressure angle')
            except Exception:
                pass

    tag = 'Cyc' if profile == PROFILE_CYCLOIDAL else 'Inv'
    _occ, component = create_component(design, defaults.PINION_COMPONENT_NAME)
    component.name = 'Pinion_{}L_{}'.format(leaves, tag)

    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane, name=defaults.PINION_SKETCH_NAME)
    # Polyline (not a fitted spline): splines through tooth points go wavy/hooked.
    add_polyline(sketch, outline, close_loop=True)

    if bore_cm > 0:
        create_circle(sketch, sketch.originPoint, bore_cm * 0.5)

    if sketch_only:
        sketch.isVisible = True
        return component, sketch, None, module_cm

    if sketch.profiles.count < 1:
        raise RuntimeError('Pinion sketch has no profile.')

    sk_profile = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        if bore_cm > 0 and candidate.profileLoops.count < 2:
            continue
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if area > best_area:
            best_area = area
            sk_profile = candidate
    if sk_profile is None:
        sk_profile = sketch.profiles.item(0)

    extrude = create_extrude(
        component,
        sk_profile,
        distance_cm=face_width_cm,
        name=defaults.PINION_EXTRUDE_NAME,
        expression=defaults.PARAM_PINION_FACE_WIDTH)
    body = name_first_body(extrude, defaults.PINION_BODY_NAME)
    return component, sketch, body, module_cm
