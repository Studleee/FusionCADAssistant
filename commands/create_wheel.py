"""CREATE WHEEL command — spur gear / watch wheel blank.

Geometry strategy
-----------------
1. New component Wheel
2. Compute module from outside diameter + tooth count: m = OD / (z + 2)
3. Build Involute or Cycloidal tooth outline → sketch polyline (+ optional bore)
4. Sketch Only: stop
5. Else: extrude face width

Primary user inputs: Outside Diameter, Tooth Count, Tooth Profile.
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
from geometry.gears import PROFILE_CYCLOIDAL, PROFILE_INVOLUTE, gear_outline_points

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_WHEEL_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_WHEEL_ID,
        defaults.CMD_CREATE_WHEEL_NAME,
        defaults.CMD_CREATE_WHEEL_TOOLTIP,
        '')

    on_created = CreateWheelCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_WHEEL_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_profile(inputs):
    dropdown = inputs.itemById('toothProfile')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.WHEEL_DEFAULT_PROFILE


def _profile_code(label):
    if label == defaults.WHEEL_PROFILE_CYCLOIDAL:
        return PROFILE_CYCLOIDAL
    return PROFILE_INVOLUTE


def _apply_wheel_ui(inputs):
    sketch_only = inputs.itemById('sketchOnly').value
    face = inputs.itemById('faceWidth')
    if face:
        face.isEnabled = not sketch_only

    is_involute = _selected_profile(inputs) == defaults.WHEEL_PROFILE_INVOLUTE
    pa = inputs.itemById('pressureAngle')
    if pa:
        pa.isVisible = is_involute
        pa.isEnabled = is_involute


class CreateWheelCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
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
                    mm_to_cm(defaults.WHEEL_OUTSIDE_DIAMETER_MM)))

            inputs.addIntegerSpinnerCommandInput(
                'teeth',
                'Tooth Count',
                6,
                200,
                1,
                int(defaults.WHEEL_TEETH))

            profile = inputs.addDropDownCommandInput(
                'toothProfile',
                'Tooth Profile',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.WHEEL_PROFILE_CYCLOIDAL,
                    defaults.WHEEL_PROFILE_INVOLUTE):
                profile.listItems.add(
                    label, label == defaults.WHEEL_DEFAULT_PROFILE)

            inputs.addValueInput(
                'faceWidth',
                'Face Width',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.WHEEL_FACE_WIDTH_MM)))

            inputs.addValueInput(
                'boreDiameter',
                'Bore Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.WHEEL_BORE_DIAMETER_MM)))

            inputs.addValueInput(
                'pressureAngle',
                'Pressure Angle',
                'deg',
                adsk.core.ValueInput.createByReal(
                    math.radians(defaults.WHEEL_PRESSURE_ANGLE_DEG)))

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.WHEEL_SKETCH_ONLY)

            _apply_wheel_ui(inputs)

            # No executePreview: dense tooth outlines + live rebuild crash Fusion.
            on_execute = CreateWheelCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateWheelCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateWheelCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Wheel dialog failed:\n{}'.format(traceback.format_exc()))


class CreateWheelCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id in ('sketchOnly', 'toothProfile'):
                _apply_wheel_ui(args.inputs)
        except Exception:
            pass


class CreateWheelCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _wheel_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateWheelCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_wheel_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Wheel failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _wheel_inputs_are_valid(inputs):
    od = inputs.itemById('outsideDiameter').value
    teeth = inputs.itemById('teeth').value
    bore = inputs.itemById('boreDiameter').value
    sketch_only = inputs.itemById('sketchOnly').value
    profile = _selected_profile(inputs)

    if od <= 0 or teeth < 6 or bore < 0 or bore >= od:
        return False
    if profile == defaults.WHEEL_PROFILE_INVOLUTE:
        pa_deg = math.degrees(inputs.itemById('pressureAngle').value)
        if not (5.0 <= pa_deg <= 30.0):
            return False
    if sketch_only:
        return True
    return inputs.itemById('faceWidth').value > 0


def _execute_wheel_from_inputs(inputs):
    pa_deg = math.degrees(inputs.itemById('pressureAngle').value)
    execute_create_wheel(
        outside_cm=inputs.itemById('outsideDiameter').value,
        teeth=int(inputs.itemById('teeth').value),
        face_width_cm=inputs.itemById('faceWidth').value,
        bore_cm=inputs.itemById('boreDiameter').value,
        pressure_angle_deg=pa_deg,
        profile=_profile_code(_selected_profile(inputs)),
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_wheel(outside_cm, teeth, face_width_cm, bore_cm=0.0,
                         pressure_angle_deg=20.0, profile=PROFILE_CYCLOIDAL,
                         sketch_only=False):
    """Build a spur wheel (involute or cycloidal). Sizes in centimeters."""
    teeth = int(teeth)
    outline, module_cm, _pitch_dia_cm, root_dia_cm = gear_outline_points(
        outside_cm, teeth,
        profile=profile,
        pressure_angle_deg=pressure_angle_deg)

    if bore_cm < 0:
        raise ValueError('Bore diameter cannot be negative.')
    if bore_cm > 0 and bore_cm >= root_dia_cm * 0.95:
        raise ValueError(
            'Bore diameter is too large for this gear root diameter ({:.3f} cm).'.format(
                root_dia_cm))

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_WHEEL_OUTSIDE_DIAMETER, outside_cm,
        comment='CREATE WHEEL outside / tip diameter')
    set_user_parameter(
        design, defaults.PARAM_WHEEL_MODULE, module_cm,
        comment='CREATE WHEEL module (derived from OD and teeth)')
    set_user_parameter(
        design, defaults.PARAM_WHEEL_BORE_DIAMETER, max(bore_cm, 0.0),
        comment='CREATE WHEEL bore diameter')
    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_WHEEL_FACE_WIDTH, face_width_cm,
            comment='CREATE WHEEL face width')

    params = design.userParameters
    existing_teeth = params.itemByName(defaults.PARAM_WHEEL_TEETH)
    teeth_vi = adsk.core.ValueInput.createByReal(float(teeth))
    if existing_teeth:
        existing_teeth.expression = str(int(teeth))
    else:
        params.add(
            defaults.PARAM_WHEEL_TEETH, teeth_vi, '',
            'CREATE WHEEL tooth count')

    if profile == PROFILE_INVOLUTE:
        existing_pa = params.itemByName(defaults.PARAM_WHEEL_PRESSURE_ANGLE)
        if existing_pa:
            existing_pa.expression = '{} deg'.format(pressure_angle_deg)
        else:
            try:
                params.add(
                    defaults.PARAM_WHEEL_PRESSURE_ANGLE,
                    adsk.core.ValueInput.createByString(
                        '{} deg'.format(pressure_angle_deg)),
                    'deg',
                    'CREATE WHEEL pressure angle')
            except Exception:
                pass

    tag = 'Cyc' if profile == PROFILE_CYCLOIDAL else 'Inv'
    _occ, component = create_component(design, defaults.WHEEL_COMPONENT_NAME)
    component.name = 'Wheel_{}T_{}'.format(teeth, tag)

    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane, name=defaults.WHEEL_SKETCH_NAME)
    # Polyline (not a fitted spline): splines through tooth points go wavy/hooked.
    add_polyline(sketch, outline, close_loop=True)

    if bore_cm > 0:
        create_circle(sketch, sketch.originPoint, bore_cm * 0.5)

    if sketch_only:
        sketch.isVisible = True
        return component, sketch, None, module_cm

    if sketch.profiles.count < 1:
        raise RuntimeError('Wheel sketch has no profile.')

    sk_profile = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        loops = candidate.profileLoops.count
        if bore_cm > 0 and loops < 2:
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
        name=defaults.WHEEL_EXTRUDE_NAME,
        expression=defaults.PARAM_WHEEL_FACE_WIDTH)
    body = name_first_body(extrude, defaults.WHEEL_BODY_NAME)
    return component, sketch, body, module_cm
