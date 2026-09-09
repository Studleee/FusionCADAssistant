"""CREATE WATCH CASE — revolved round case with slider-driven profile + lugs.

Geometry:
  1. New component
  2. XZ half-profile (hollow midcase + bezel + caseback)
  3. Revolve 360° about Z
  4. Optional strap lugs at 12 and 6 o'clock (join-extrude)

Live preview rebuilds as sliders move. Section profile can stay visible.
"""

import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_revolve, name_first_body
from fusion.parameters import set_user_parameter
from fusion.polylines import add_polyline
from fusion.sketches import create_offset_plane, create_sketch_on_plane
from geometry.watch_case import (
    watch_case_half_profile_points,
    watch_case_lug_rects_xy,
    watch_case_lugs_are_valid,
    watch_case_profile_is_valid,
)

_handlers = []
_preview_error_shown = False


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_WATCH_CASE_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_WATCH_CASE_ID,
        defaults.CMD_CREATE_WATCH_CASE_NAME,
        defaults.CMD_CREATE_WATCH_CASE_TOOLTIP,
        '')

    on_created = CreateWatchCaseCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_WATCH_CASE_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _add_mm_slider(inputs, input_id, label, value_mm, min_mm, max_mm):
    """Float slider labeled in mm; min/max/value use Fusion database cm."""
    # API requires min/max in database units (cm), even when unitType is 'mm'.
    slider = inputs.addFloatSliderCommandInput(
        input_id, label, 'mm',
        mm_to_cm(min_mm), mm_to_cm(max_mm), False)
    if not slider:
        raise RuntimeError('Failed to create slider {!r}.'.format(input_id))
    slider.valueOne = mm_to_cm(value_mm)
    try:
        slider.spinStep = mm_to_cm(0.1)
    except Exception:
        pass
    return slider


def _slider_cm(inputs, input_id):
    return float(inputs.itemById(input_id).valueOne)


class CreateWatchCaseCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _preview_error_shown
        _preview_error_shown = False
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            _add_mm_slider(
                inputs, 'caseDiameter', 'Case Diameter',
                defaults.WATCH_CASE_DIAMETER_MM,
                defaults.WATCH_CASE_DIAMETER_MIN_MM,
                defaults.WATCH_CASE_DIAMETER_MAX_MM)

            _add_mm_slider(
                inputs, 'caseHeight', 'Case Height',
                defaults.WATCH_CASE_HEIGHT_MM,
                defaults.WATCH_CASE_HEIGHT_MIN_MM,
                defaults.WATCH_CASE_HEIGHT_MAX_MM)

            _add_mm_slider(
                inputs, 'crystalDiameter', 'Crystal Opening',
                defaults.WATCH_CASE_CRYSTAL_DIAMETER_MM,
                10.0, 50.0)

            _add_mm_slider(
                inputs, 'cavityDiameter', 'Movement Cavity',
                defaults.WATCH_CASE_CAVITY_DIAMETER_MM,
                12.0, 52.0)

            _add_mm_slider(
                inputs, 'bezelHeight', 'Bezel Height',
                defaults.WATCH_CASE_BEZEL_HEIGHT_MM,
                0.4, 6.0)

            _add_mm_slider(
                inputs, 'bezelInset', 'Bezel Inset',
                defaults.WATCH_CASE_BEZEL_INSET_MM,
                0.0, 4.0)

            _add_mm_slider(
                inputs, 'casebackHeight', 'Caseback Height',
                defaults.WATCH_CASE_CASEBACK_HEIGHT_MM,
                0.4, 6.0)

            _add_mm_slider(
                inputs, 'casebackInset', 'Caseback Inset',
                defaults.WATCH_CASE_CASEBACK_INSET_MM,
                0.0, 4.0)

            _add_mm_slider(
                inputs, 'casebackOpening', 'Caseback Opening',
                defaults.WATCH_CASE_CASEBACK_OPENING_MM,
                8.0, 50.0)

            soft = inputs.addFloatSliderCommandInput(
                'edgeSoftness', 'Edge Softness', '',
                float(defaults.WATCH_CASE_SOFTNESS_MIN),
                float(defaults.WATCH_CASE_SOFTNESS_MAX), False)
            soft.valueOne = float(defaults.WATCH_CASE_EDGE_SOFTNESS)

            inputs.addBoolValueInput(
                'addLugs',
                'Add Lugs',
                True,
                '',
                defaults.WATCH_CASE_ADD_LUGS)

            _add_mm_slider(
                inputs, 'lugLength', 'Lug Length',
                defaults.WATCH_CASE_LUG_LENGTH_MM, 1.0, 12.0)

            _add_mm_slider(
                inputs, 'lugWidth', 'Lug Width',
                defaults.WATCH_CASE_LUG_WIDTH_MM, 0.8, 8.0)

            _add_mm_slider(
                inputs, 'lugGap', 'Lug Gap (strap)',
                defaults.WATCH_CASE_LUG_GAP_MM, 8.0, 40.0)

            _add_mm_slider(
                inputs, 'lugThickness', 'Lug Thickness',
                defaults.WATCH_CASE_LUG_THICKNESS_MM, 1.0, 8.0)

            inputs.addBoolValueInput(
                'showProfile',
                'Show Section Profile',
                True,
                '',
                True)

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.WATCH_CASE_SKETCH_ONLY)

            _apply_watch_case_ui(inputs)

            on_preview = CreateWatchCaseCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreateWatchCaseCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateWatchCaseCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateWatchCaseCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Watch Case dialog failed:\n{}'.format(
                        traceback.format_exc()))


def _apply_watch_case_ui(inputs):
    add_lugs = inputs.itemById('addLugs').value
    for input_id in ('lugLength', 'lugWidth', 'lugGap', 'lugThickness'):
        item = inputs.itemById(input_id)
        if item:
            item.isVisible = add_lugs
            item.isEnabled = add_lugs


class CreateWatchCaseCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id == 'addLugs':
                _apply_watch_case_ui(args.inputs)
        except Exception:
            pass


class CreateWatchCaseCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _watch_case_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateWatchCaseCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        global _preview_error_shown
        try:
            inputs = args.command.commandInputs
            if not _watch_case_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_watch_case_from_inputs(inputs, commit_params=False)
            args.isValidResult = True
        except Exception as exc:
            args.isValidResult = False
            app = adsk.core.Application.get()
            if app:
                try:
                    app.log('Create Watch Case preview failed: {}'.format(exc))
                except Exception:
                    pass
            if not _preview_error_shown:
                _preview_error_shown = True
                ui = app.userInterface if app else None
                if ui:
                    ui.messageBox(
                        'Create Watch Case preview failed:\n{}'.format(exc))


class CreateWatchCaseCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_watch_case_from_inputs(
                args.command.commandInputs, commit_params=True)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Watch Case failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _watch_case_inputs_are_valid(inputs):
    case_od = _slider_cm(inputs, 'caseDiameter')
    case_h = _slider_cm(inputs, 'caseHeight')
    crystal = _slider_cm(inputs, 'crystalDiameter')
    cavity = _slider_cm(inputs, 'cavityDiameter')
    bezel_h = _slider_cm(inputs, 'bezelHeight')
    bezel_inset = _slider_cm(inputs, 'bezelInset')
    back_h = _slider_cm(inputs, 'casebackHeight')
    back_inset = _slider_cm(inputs, 'casebackInset')
    back_open = _slider_cm(inputs, 'casebackOpening')
    if not watch_case_profile_is_valid(
            case_od, case_h, crystal, cavity,
            bezel_h, bezel_inset, back_h, back_inset, back_open):
        return False
    if inputs.itemById('addLugs').value:
        return watch_case_lugs_are_valid(
            case_od,
            _slider_cm(inputs, 'lugLength'),
            _slider_cm(inputs, 'lugWidth'),
            _slider_cm(inputs, 'lugGap'),
            _slider_cm(inputs, 'lugThickness'),
            case_h)
    return True


def _execute_watch_case_from_inputs(inputs, commit_params=False):
    execute_create_watch_case(
        case_od_cm=_slider_cm(inputs, 'caseDiameter'),
        case_height_cm=_slider_cm(inputs, 'caseHeight'),
        crystal_od_cm=_slider_cm(inputs, 'crystalDiameter'),
        cavity_od_cm=_slider_cm(inputs, 'cavityDiameter'),
        bezel_height_cm=_slider_cm(inputs, 'bezelHeight'),
        bezel_inset_cm=_slider_cm(inputs, 'bezelInset'),
        caseback_height_cm=_slider_cm(inputs, 'casebackHeight'),
        caseback_inset_cm=_slider_cm(inputs, 'casebackInset'),
        caseback_opening_cm=_slider_cm(inputs, 'casebackOpening'),
        edge_softness=float(inputs.itemById('edgeSoftness').valueOne),
        add_lugs=inputs.itemById('addLugs').value,
        lug_length_cm=_slider_cm(inputs, 'lugLength'),
        lug_width_cm=_slider_cm(inputs, 'lugWidth'),
        lug_gap_cm=_slider_cm(inputs, 'lugGap'),
        lug_thickness_cm=_slider_cm(inputs, 'lugThickness'),
        sketch_only=inputs.itemById('sketchOnly').value,
        show_profile=inputs.itemById('showProfile').value,
        commit_params=commit_params)


def execute_create_watch_case(
        case_od_cm,
        case_height_cm,
        crystal_od_cm,
        cavity_od_cm,
        bezel_height_cm,
        bezel_inset_cm,
        caseback_height_cm,
        caseback_inset_cm,
        caseback_opening_cm,
        edge_softness=0.0,
        add_lugs=True,
        lug_length_cm=None,
        lug_width_cm=None,
        lug_gap_cm=None,
        lug_thickness_cm=None,
        sketch_only=False,
        show_profile=True,
        commit_params=True):
    """Build a round hollow watch case with optional strap lugs. Sizes in cm."""
    if lug_length_cm is None:
        lug_length_cm = mm_to_cm(defaults.WATCH_CASE_LUG_LENGTH_MM)
    if lug_width_cm is None:
        lug_width_cm = mm_to_cm(defaults.WATCH_CASE_LUG_WIDTH_MM)
    if lug_gap_cm is None:
        lug_gap_cm = mm_to_cm(defaults.WATCH_CASE_LUG_GAP_MM)
    if lug_thickness_cm is None:
        lug_thickness_cm = mm_to_cm(defaults.WATCH_CASE_LUG_THICKNESS_MM)

    xz = watch_case_half_profile_points(
        case_od_cm, case_height_cm, crystal_od_cm, cavity_od_cm,
        bezel_height_cm, bezel_inset_cm, caseback_height_cm,
        caseback_inset_cm, caseback_opening_cm, edge_softness)

    design = get_active_design()
    if commit_params:
        _commit_watch_case_parameters(
            design, case_od_cm, case_height_cm, crystal_od_cm, cavity_od_cm,
            bezel_height_cm, bezel_inset_cm, caseback_height_cm,
            caseback_inset_cm, caseback_opening_cm, edge_softness,
            add_lugs, lug_length_cm, lug_width_cm, lug_gap_cm, lug_thickness_cm)

    _occ, component = create_component(
        design, defaults.WATCH_CASE_COMPONENT_NAME)
    component.name = 'WatchCase_{:.0f}x{:.0f}'.format(
        case_od_cm * 10.0, case_height_cm * 10.0)

    sketch = component.sketches.add(component.xZConstructionPlane)
    sketch.name = defaults.WATCH_CASE_PROFILE_SKETCH_NAME

    sk_pts = []
    for x, z in xz:
        p = sketch.modelToSketchSpace(
            adsk.core.Point3D.create(float(x), 0.0, float(z)))
        sk_pts.append((p.x, p.y, p.z))
    add_polyline(sketch, sk_pts, close_loop=True)

    try:
        sketch.sketchCurves.sketchLines.addByTwoPoints(
            sketch.modelToSketchSpace(
                adsk.core.Point3D.create(0.0, 0.0, 0.0)),
            sketch.modelToSketchSpace(
                adsk.core.Point3D.create(0.0, 0.0, float(case_height_cm))))
    except Exception:
        pass

    sketch.isVisible = bool(show_profile or sketch_only)

    if sketch_only:
        if add_lugs:
            _sketch_lugs_only(
                component, case_od_cm, case_height_cm, caseback_height_cm,
                lug_length_cm, lug_width_cm, lug_gap_cm, lug_thickness_cm)
        _fit_view()
        return component, sketch, None

    profile = _largest_profile(sketch)
    if profile is None:
        raise RuntimeError('Watch case profile sketch has no profile.')

    revolve = create_revolve(
        component,
        profile,
        component.zConstructionAxis,
        name=defaults.WATCH_CASE_REVOLVE_NAME)
    body = name_first_body(revolve, defaults.WATCH_CASE_BODY_NAME)

    if add_lugs:
        _add_strap_lugs(
            component, body, case_od_cm, case_height_cm, caseback_height_cm,
            lug_length_cm, lug_width_cm, lug_gap_cm, lug_thickness_cm)

    sketch.isVisible = bool(show_profile)
    _fit_view()
    return component, sketch, body


def _add_strap_lugs(
        component, body, case_od_cm, case_height_cm, caseback_height_cm,
        lug_length_cm, lug_width_cm, lug_gap_cm, lug_thickness_cm):
    """Join-extrude four lug horns at 12 and 6 o'clock."""
    # Sit lugs on the midcase band (above caseback step).
    z0 = float(caseback_height_cm)
    max_z = float(case_height_cm) - float(lug_thickness_cm)
    if z0 > max_z:
        z0 = max(0.0, max_z * 0.5)

    plane = create_offset_plane(component, z0)
    lug_sketch = create_sketch_on_plane(
        component, plane, name=defaults.WATCH_CASE_LUG_SKETCH_NAME)

    rects = watch_case_lug_rects_xy(
        case_od_cm, lug_length_cm, lug_width_cm, lug_gap_cm)
    lines = lug_sketch.sketchCurves.sketchLines
    for xmin, ymin, xmax, ymax in rects:
        p0 = adsk.core.Point3D.create(float(xmin), float(ymin), 0.0)
        p1 = adsk.core.Point3D.create(float(xmax), float(ymax), 0.0)
        rect = lines.addTwoPointRectangle(p0, p1)
        if not rect:
            raise RuntimeError('Failed to sketch a lug footprint.')

    if lug_sketch.profiles.count < 1:
        raise RuntimeError('Lug sketch has no profiles.')

    # Extrude all lug profiles in one join when possible.
    profiles = adsk.core.ObjectCollection.create()
    for i in range(lug_sketch.profiles.count):
        profiles.add(lug_sketch.profiles.item(i))

    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    if not ext_input:
        raise RuntimeError('Failed to create lug extrude input.')
    ext_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(float(lug_thickness_cm)))
    ext_input.isSolid = True
    ext_input.participantBodies = [body]
    lug_ext = extrudes.add(ext_input)
    if not lug_ext:
        raise RuntimeError('Failed to extrude watch-case lugs.')
    lug_ext.name = defaults.WATCH_CASE_LUG_EXTRUDE_NAME
    lug_sketch.isVisible = False
    return lug_ext


def _sketch_lugs_only(
        component, case_od_cm, case_height_cm, caseback_height_cm,
        lug_length_cm, lug_width_cm, lug_gap_cm, lug_thickness_cm):
    """Draw lug footprints only (sketch-only mode)."""
    z0 = float(caseback_height_cm)
    max_z = float(case_height_cm) - float(lug_thickness_cm)
    if z0 > max_z:
        z0 = max(0.0, max_z * 0.5)
    plane = create_offset_plane(component, z0)
    lug_sketch = create_sketch_on_plane(
        component, plane, name=defaults.WATCH_CASE_LUG_SKETCH_NAME)
    rects = watch_case_lug_rects_xy(
        case_od_cm, lug_length_cm, lug_width_cm, lug_gap_cm)
    lines = lug_sketch.sketchCurves.sketchLines
    for xmin, ymin, xmax, ymax in rects:
        lines.addTwoPointRectangle(
            adsk.core.Point3D.create(float(xmin), float(ymin), 0.0),
            adsk.core.Point3D.create(float(xmax), float(ymax), 0.0))
    lug_sketch.isVisible = True


def _commit_watch_case_parameters(
        design, case_od_cm, case_height_cm, crystal_od_cm, cavity_od_cm,
        bezel_height_cm, bezel_inset_cm, caseback_height_cm,
        caseback_inset_cm, caseback_opening_cm, edge_softness,
        add_lugs=False, lug_length_cm=None, lug_width_cm=None,
        lug_gap_cm=None, lug_thickness_cm=None):
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_DIAMETER, case_od_cm,
        comment='CREATE WATCH CASE outer diameter')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_HEIGHT, case_height_cm,
        comment='CREATE WATCH CASE overall height')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_CRYSTAL_DIAMETER, crystal_od_cm,
        comment='CREATE WATCH CASE crystal opening')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_CAVITY_DIAMETER, cavity_od_cm,
        comment='CREATE WATCH CASE movement cavity')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_BEZEL_HEIGHT, bezel_height_cm,
        comment='CREATE WATCH CASE bezel height')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_BEZEL_INSET, bezel_inset_cm,
        comment='CREATE WATCH CASE bezel inset from OD')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_CASEBACK_HEIGHT, caseback_height_cm,
        comment='CREATE WATCH CASE caseback height')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_CASEBACK_INSET, caseback_inset_cm,
        comment='CREATE WATCH CASE caseback inset from OD')
    set_user_parameter(
        design, defaults.PARAM_WATCH_CASE_CASEBACK_OPENING, caseback_opening_cm,
        comment='CREATE WATCH CASE caseback opening')

    soft_param = design.userParameters.itemByName(
        defaults.PARAM_WATCH_CASE_EDGE_SOFTNESS)
    soft_vi = adsk.core.ValueInput.createByReal(float(edge_softness))
    if soft_param:
        soft_param.expression = str(float(edge_softness))
    else:
        try:
            design.userParameters.add(
                defaults.PARAM_WATCH_CASE_EDGE_SOFTNESS, soft_vi, '',
                'CREATE WATCH CASE outer edge softness 0-1')
        except Exception:
            pass

    if add_lugs and lug_length_cm is not None:
        set_user_parameter(
            design, defaults.PARAM_WATCH_CASE_LUG_LENGTH, lug_length_cm,
            comment='CREATE WATCH CASE lug length')
        set_user_parameter(
            design, defaults.PARAM_WATCH_CASE_LUG_WIDTH, lug_width_cm,
            comment='CREATE WATCH CASE lug width')
        set_user_parameter(
            design, defaults.PARAM_WATCH_CASE_LUG_GAP, lug_gap_cm,
            comment='CREATE WATCH CASE lug gap / strap width')
        set_user_parameter(
            design, defaults.PARAM_WATCH_CASE_LUG_THICKNESS, lug_thickness_cm,
            comment='CREATE WATCH CASE lug thickness')


def _fit_view():
    """Zoom the active viewport so the live case is visible."""
    try:
        app = adsk.core.Application.get()
        viewport = app.activeViewport if app else None
        if viewport:
            viewport.fit()
    except Exception:
        pass


def _largest_profile(sketch):
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
