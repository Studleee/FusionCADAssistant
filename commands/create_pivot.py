"""CREATE PIVOT command — cylindrical watch pivot with slight domed ends.

Geometry:
  1. New component
  2. XZ half-profile: cylinder + small spherical caps at each end
  3. Revolve 360° about Z (or sketch-only stop)

Length = cylindrical barrel. Domes sit outside that length (slight tip radius).
Width = diameter.
"""

import math
import traceback

import adsk.core

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_revolve, name_first_body
from fusion.parameters import set_user_parameter
from geometry.jewels import sphere_radius_for_spherical_cap

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_PIVOT_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_PIVOT_ID,
        defaults.CMD_CREATE_PIVOT_NAME,
        defaults.CMD_CREATE_PIVOT_TOOLTIP,
        '')

    on_created = CreatePivotCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_PIVOT_ID)
    if cmd_def:
        cmd_def.deleteMe()


class CreatePivotCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            inputs.addValueInput(
                'pivotLength',
                'Length',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PIVOT_LENGTH_MM)))

            inputs.addValueInput(
                'pivotWidth',
                'Width',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.PIVOT_WIDTH_MM)))

            inputs.addBoolValueInput(
                'domedEnds',
                'Domed Ends',
                True,
                '',
                defaults.PIVOT_DOMED_ENDS)

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.PIVOT_SKETCH_ONLY)

            on_preview = CreatePivotCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreatePivotCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreatePivotCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Pivot dialog failed:\n{}'.format(traceback.format_exc()))


class CreatePivotCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _pivot_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreatePivotCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            if not _pivot_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_pivot_from_inputs(inputs)
            args.isValidResult = True
        except Exception:
            args.isValidResult = False


class CreatePivotCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_pivot_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Pivot failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _pivot_inputs_are_valid(inputs):
    length = inputs.itemById('pivotLength').value
    width = inputs.itemById('pivotWidth').value
    sketch_only = inputs.itemById('sketchOnly').value
    if width <= 0:
        return False
    if not sketch_only and length <= 0:
        return False
    return True


def _execute_pivot_from_inputs(inputs):
    execute_create_pivot(
        length_cm=inputs.itemById('pivotLength').value,
        width_cm=inputs.itemById('pivotWidth').value,
        domed_ends=inputs.itemById('domedEnds').value,
        sketch_only=inputs.itemById('sketchOnly').value)


def _dome_height_cm(radius_cm, length_cm):
    """Slight spherical-cap height — readable but not bulbous."""
    r = float(radius_cm)
    # ~22% of radius, capped so tiny pivots stay subtle vs barrel length.
    h = 0.22 * r
    h = min(h, max(length_cm * 0.12, r * 0.08))
    return max(h, r * 0.06)


def execute_create_pivot(length_cm, width_cm, domed_ends=True, sketch_only=False):
    """Build a cylindrical pivot. Sizes in centimeters. Width = diameter."""
    if width_cm <= 0:
        raise ValueError('Width (diameter) must be greater than zero.')
    if not sketch_only and length_cm <= 0:
        raise ValueError('Length must be greater than zero.')

    radius = width_cm * 0.5
    dome_h = _dome_height_cm(radius, length_cm) if domed_ends else 0.0

    design = get_active_design()
    set_user_parameter(
        design, defaults.PARAM_PIVOT_WIDTH, width_cm,
        comment='CREATE PIVOT width (diameter)')
    if not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_PIVOT_LENGTH, length_cm,
            comment='CREATE PIVOT cylindrical length')
        if domed_ends:
            set_user_parameter(
                design, defaults.PARAM_PIVOT_DOME_HEIGHT, dome_h,
                comment='CREATE PIVOT end dome height (each end)')

    _occ, component = create_component(design, defaults.PIVOT_COMPONENT_NAME)
    component.name = 'Pivot_{:.2f}x{:.2f}'.format(
        length_cm * 10.0, width_cm * 10.0)

    sketch = component.sketches.add(component.xZConstructionPlane)
    sketch.name = defaults.PIVOT_SKETCH_NAME
    _draw_pivot_half_profile(sketch, radius, length_cm, dome_h)

    if sketch_only:
        sketch.isVisible = True
        return component, sketch, None

    if sketch.profiles.count < 1:
        raise RuntimeError('Pivot sketch has no profile.')

    profile = _smallest_profile(sketch)
    revolve = create_revolve(
        component,
        profile,
        component.zConstructionAxis,
        name=defaults.PIVOT_REVOLVE_NAME)
    body = name_first_body(revolve, defaults.PIVOT_BODY_NAME)
    return component, sketch, body


def _smallest_profile(sketch):
    """Prefer the compact closed half-profile over any leftover face."""
    best = sketch.profiles.item(0)
    best_area = None
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if best_area is None or area < best_area:
            best_area = area
            best = candidate
    return best


def _draw_pivot_half_profile(sketch, radius_cm, length_cm, dome_h_cm):
    """Closed XZ half-profile (x >= 0) for revolve about Z.

    Cylinder from z=0..length. Optional spherical caps outside that span.
    """
    r = float(radius_cm)
    L = float(length_cm)
    h = float(dome_h_cm)
    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    def sk(x, z):
        return sketch.modelToSketchSpace(adsk.core.Point3D.create(x, 0.0, z))

    z_bot = -h
    z_top = L + h

    # Axis (centerline) then outer path CCW in the +X half-plane.
    p_axis_bot = sk(0.0, z_bot)
    p_axis_top = sk(0.0, z_top)
    p_rim_bot = sk(r, 0.0)
    p_rim_top = sk(r, L)

    lines.addByTwoPoints(p_axis_bot, p_axis_top)

    if h > 1e-9:
        R = sphere_radius_for_spherical_cap(r, h)
        # Bottom dome: peak (0, -h) → rim (r, 0); sphere center on axis.
        z_c_bot = -h + R
        x_mid = r * 0.5
        z_mid_bot = z_c_bot - math.sqrt(max(R * R - x_mid * x_mid, 0.0))
        p_peak_bot = sk(0.0, z_bot)
        p_mid_bot = sk(x_mid, z_mid_bot)
        arc_bot = arcs.addByThreePoints(p_peak_bot, p_mid_bot, p_rim_bot)
        if not arc_bot:
            raise RuntimeError('Failed to create bottom pivot dome arc.')

        lines.addByTwoPoints(p_rim_bot, p_rim_top)

        z_c_top = L + h - R
        z_mid_top = z_c_top + math.sqrt(max(R * R - x_mid * x_mid, 0.0))
        p_peak_top = sk(0.0, z_top)
        p_mid_top = sk(x_mid, z_mid_top)
        arc_top = arcs.addByThreePoints(p_rim_top, p_mid_top, p_peak_top)
        if not arc_top:
            raise RuntimeError('Failed to create top pivot dome arc.')
    else:
        # Flat ends: rectangle half-profile (axis already spans z=0..L).
        lines.addByTwoPoints(p_axis_bot, p_rim_bot)
        lines.addByTwoPoints(p_rim_bot, p_rim_top)
        lines.addByTwoPoints(p_rim_top, p_axis_top)
