"""CREATE JEWEL command — watch hole jewels and cap jewels.

Geometry strategy
-----------------
Hole jewel:
  1. New component
  2. Concentric OD + bore circles, diameter dimensions + user parameters
  3. Extrude annular profile (or sketch-only stop)
  4. Optional oil sink: spherical-cap revolve cut (concave oil cup)

Cap jewel:
  1. New component
  2. Single OD circle → extrude disk
  3. Optional spherical oil cup on the top face (no through hole)

Native sketches / extrude / revolve only — no meshes.
"""

import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_extrude, create_revolve_cut, name_first_body
from fusion.parameters import link_dimension_to_parameter, set_user_parameter
from fusion.sketches import (
    add_diameter_dimension,
    create_circle,
    create_sketch_on_plane,
    find_annular_profile,
)
from geometry.jewels import (
    sphere_radius_for_spherical_cap,
    spherical_surface_height,
)

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_JEWEL_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_JEWEL_ID,
        defaults.CMD_CREATE_JEWEL_NAME,
        defaults.CMD_CREATE_JEWEL_TOOLTIP,
        '')

    on_created = CreateJewelCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_JEWEL_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_jewel_type(inputs):
    dropdown = inputs.itemById('jewelType')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.JEWEL_DEFAULT_TYPE


def _apply_jewel_ui(inputs):
    jewel_type = _selected_jewel_type(inputs)
    is_hole = jewel_type == defaults.JEWEL_TYPE_HOLE
    sketch_only = inputs.itemById('sketchOnly').value
    oil_sink = inputs.itemById('oilSink').value

    hole_dia = inputs.itemById('holeDiameter')
    if hole_dia:
        hole_dia.isVisible = is_hole
        hole_dia.isEnabled = is_hole

    oil_sink_input = inputs.itemById('oilSink')
    if oil_sink_input:
        oil_sink_input.isEnabled = not sketch_only

    sink_dia = inputs.itemById('oilSinkDiameter')
    sink_depth = inputs.itemById('oilSinkDepth')
    enable_sink_dims = (not sketch_only) and oil_sink
    if sink_dia:
        sink_dia.isEnabled = enable_sink_dims
    if sink_depth:
        sink_depth.isEnabled = enable_sink_dims


class CreateJewelCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            type_input = inputs.addDropDownCommandInput(
                'jewelType',
                'Jewel Type',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            type_input.listItems.add(
                defaults.JEWEL_TYPE_HOLE,
                defaults.JEWEL_DEFAULT_TYPE == defaults.JEWEL_TYPE_HOLE)
            type_input.listItems.add(
                defaults.JEWEL_TYPE_CAP,
                defaults.JEWEL_DEFAULT_TYPE == defaults.JEWEL_TYPE_CAP)

            inputs.addValueInput(
                'outerDiameter',
                'Outer Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.JEWEL_OUTER_DIAMETER_MM)))

            inputs.addValueInput(
                'holeDiameter',
                'Hole Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.JEWEL_HOLE_DIAMETER_MM)))

            inputs.addValueInput(
                'thickness',
                'Thickness',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.JEWEL_THICKNESS_MM)))

            inputs.addBoolValueInput(
                'oilSink',
                'Oil Sink',
                True,
                '',
                defaults.JEWEL_OIL_SINK)

            inputs.addValueInput(
                'oilSinkDiameter',
                'Oil Sink Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.JEWEL_OIL_SINK_DIAMETER_MM)))

            inputs.addValueInput(
                'oilSinkDepth',
                'Oil Sink Depth',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.JEWEL_OIL_SINK_DEPTH_MM)))

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.JEWEL_SKETCH_ONLY)

            _apply_jewel_ui(inputs)

            # Live viewport preview while the dialog is open (Fusion rolls it
            # back on each input change; OK keeps the last valid preview).
            on_preview = CreateJewelCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreateJewelCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateJewelCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateJewelCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox('Create Jewel dialog failed:\n{}'.format(traceback.format_exc()))


class CreateJewelCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id in ('jewelType', 'oilSink', 'sketchOnly'):
                _apply_jewel_ui(args.inputs)
        except Exception:
            pass


class CreateJewelCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _jewel_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateJewelCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """Rebuild geometry as inputs change; commit last preview on OK."""
        try:
            inputs = args.command.commandInputs
            if not _jewel_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_jewel_from_inputs(inputs)
            args.isValidResult = True
        except Exception:
            # Invalid preview → Fusion aborts the preview transaction.
            args.isValidResult = False


class CreateJewelCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        # Only runs if preview did not set isValidResult=True (fallback).
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_jewel_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Jewel failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _jewel_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    outer = inputs.itemById('outerDiameter').value
    thickness = inputs.itemById('thickness').value
    sketch_only = inputs.itemById('sketchOnly').value
    jewel_type = _selected_jewel_type(inputs)

    if outer <= 0 or (not sketch_only and thickness <= 0):
        return False

    if jewel_type == defaults.JEWEL_TYPE_HOLE:
        hole = inputs.itemById('holeDiameter').value
        if not (outer > hole > 0):
            return False

    if (not sketch_only) and inputs.itemById('oilSink').value:
        sink_dia = inputs.itemById('oilSinkDiameter').value
        sink_depth = inputs.itemById('oilSinkDepth').value
        if sink_dia <= 0 or sink_depth <= 0 or sink_dia >= outer:
            return False
        if jewel_type == defaults.JEWEL_TYPE_HOLE:
            hole = inputs.itemById('holeDiameter').value
            if sink_dia <= hole:
                return False
        if sink_depth >= thickness:
            return False

    return True


def _execute_jewel_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    execute_create_jewel(
        jewel_type=_selected_jewel_type(inputs),
        outer_cm=inputs.itemById('outerDiameter').value,
        hole_cm=inputs.itemById('holeDiameter').value,
        thickness_cm=inputs.itemById('thickness').value,
        oil_sink=inputs.itemById('oilSink').value,
        oil_sink_dia_cm=inputs.itemById('oilSinkDiameter').value,
        oil_sink_depth_cm=inputs.itemById('oilSinkDepth').value,
        sketch_only=inputs.itemById('sketchOnly').value)


def execute_create_jewel(jewel_type, outer_cm, hole_cm, thickness_cm,
                         oil_sink=True, oil_sink_dia_cm=None, oil_sink_depth_cm=None,
                         sketch_only=False):
    """Build a hole or cap jewel. Dimensions in centimeters."""
    if outer_cm <= 0:
        raise ValueError('Outer diameter must be greater than zero.')
    if not sketch_only and thickness_cm <= 0:
        raise ValueError('Thickness must be greater than zero.')

    is_hole = jewel_type == defaults.JEWEL_TYPE_HOLE
    if is_hole and not (outer_cm > hole_cm > 0):
        raise ValueError('Hole diameter must be smaller than outer diameter.')

    design = get_active_design()

    set_user_parameter(
        design, defaults.PARAM_JEWEL_OUTER_DIAMETER, outer_cm,
        comment='CREATE JEWEL outer diameter')
    set_user_parameter(
        design, defaults.PARAM_JEWEL_THICKNESS, thickness_cm,
        comment='CREATE JEWEL thickness')
    if is_hole:
        set_user_parameter(
            design, defaults.PARAM_JEWEL_HOLE_DIAMETER, hole_cm,
            comment='CREATE JEWEL pivot bore')
    if oil_sink and not sketch_only:
        set_user_parameter(
            design, defaults.PARAM_JEWEL_OIL_SINK_DIAMETER, oil_sink_dia_cm,
            comment='CREATE JEWEL oil sink diameter')
        set_user_parameter(
            design, defaults.PARAM_JEWEL_OIL_SINK_DEPTH, oil_sink_depth_cm,
            comment='CREATE JEWEL oil sink depth')

    comp_name = (
        defaults.JEWEL_COMPONENT_NAME_HOLE if is_hole
        else defaults.JEWEL_COMPONENT_NAME_CAP)
    _occ, component = create_component(design, comp_name)

    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane, name=defaults.JEWEL_SKETCH_NAME)
    center = sketch.originPoint
    outer_r = outer_cm * 0.5

    outer_circle = create_circle(sketch, center, outer_r)
    outer_dim = add_diameter_dimension(
        sketch,
        outer_circle,
        adsk.core.Point3D.create(outer_r * 1.2, 0, 0),
        diameter_cm=outer_cm)
    link_dimension_to_parameter(outer_dim, defaults.PARAM_JEWEL_OUTER_DIAMETER)

    if is_hole:
        hole_r = hole_cm * 0.5
        hole_circle = create_circle(sketch, center, hole_r)
        hole_dim = add_diameter_dimension(
            sketch,
            hole_circle,
            adsk.core.Point3D.create(hole_r * 0.8, hole_r * 0.8, 0),
            diameter_cm=hole_cm)
        link_dimension_to_parameter(hole_dim, defaults.PARAM_JEWEL_HOLE_DIAMETER)
        try:
            sketch.geometricConstraints.addConcentric(outer_circle, hole_circle)
        except Exception:
            pass

    if sketch_only:
        sketch.isVisible = True
        return component, sketch, None

    if is_hole:
        profile = find_annular_profile(sketch)
    else:
        if sketch.profiles.count < 1:
            raise RuntimeError('Cap jewel sketch has no profile.')
        profile = sketch.profiles.item(0)

    extrude = create_extrude(
        component,
        profile,
        distance_cm=thickness_cm,
        name=defaults.JEWEL_EXTRUDE_NAME,
        expression=defaults.PARAM_JEWEL_THICKNESS)
    body = name_first_body(extrude, defaults.JEWEL_BODY_NAME)

    if oil_sink:
        _add_spherical_oil_sink(
            component,
            target_body=body,
            thickness_cm=thickness_cm,
            oil_sink_dia_cm=oil_sink_dia_cm,
            oil_sink_depth_cm=oil_sink_depth_cm,
            hole_cm=hole_cm if is_hole else 0.0)

    return component, sketch, body


def _add_spherical_oil_sink(component, target_body, thickness_cm, oil_sink_dia_cm,
                            oil_sink_depth_cm, hole_cm=0.0):
    """Cut a concave spherical oil cup by revolving an arc profile.

    The cup is a spherical cap:
      rim diameter = oil sink diameter
      center depth = oil sink depth
      R = (a^2 + h^2) / (2h)

    Points are defined in model space (Z = jewel axis) and converted into the
    XZ sketch with modelToSketchSpace so the cut lands on the jewel body.
    """
    a = float(oil_sink_dia_cm) * 0.5
    h = float(oil_sink_depth_cm)
    r_inner = max(float(hole_cm) * 0.5, 0.0)
    z_top = float(thickness_cm)

    if a <= r_inner + 1e-8:
        raise ValueError('Oil sink diameter must be larger than the hole diameter.')
    if h <= 0 or h >= z_top:
        raise ValueError('Oil sink depth must be between zero and the jewel thickness.')

    R = sphere_radius_for_spherical_cap(a, h)
    z_inner = spherical_surface_height(r_inner, z_top, h, R)
    z_mid = spherical_surface_height((a + r_inner) * 0.5, z_top, h, R)

    sink_sketch = component.sketches.add(component.xZConstructionPlane)
    sink_sketch.name = defaults.JEWEL_OIL_SINK_SKETCH_NAME
    lines = sink_sketch.sketchCurves.sketchLines
    arcs = sink_sketch.sketchCurves.sketchArcs

    # Model-space points in the XZ half-plane (Y = 0), then map to sketch space.
    # This avoids XZ sketch-axis sign/orientation mistakes.
    def sk(x, z):
        return sink_sketch.modelToSketchSpace(adsk.core.Point3D.create(x, 0.0, z))

    p_rim = sk(a, z_top)
    p_top_inner = sk(r_inner, z_top)
    p_cup_inner = sk(r_inner, z_inner)
    p_mid = sk((a + r_inner) * 0.5, z_mid)

    # Closed cut profile: top rim → spherical arc → up bore/centerline.
    lines.addByTwoPoints(p_top_inner, p_rim)
    arc = arcs.addByThreePoints(p_rim, p_mid, p_cup_inner)
    if not arc:
        raise RuntimeError('Failed to create spherical oil-sink arc.')
    lines.addByTwoPoints(p_cup_inner, p_top_inner)

    if sink_sketch.profiles.count < 1:
        raise RuntimeError('Oil sink revolve sketch has no profile.')

    # Prefer the smallest closed profile (the cup wedge).
    profile = sink_sketch.profiles.item(0)
    best_area = None
    for i in range(sink_sketch.profiles.count):
        candidate = sink_sketch.profiles.item(i)
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if best_area is None or area < best_area:
            best_area = area
            profile = candidate

    create_revolve_cut(
        component,
        profile,
        component.zConstructionAxis,
        name=defaults.JEWEL_OIL_SINK_CUT_NAME,
        participant_bodies=[target_body])
