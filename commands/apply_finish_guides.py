"""APPLY FINISH GUIDES — decorative layout sketches on planar faces.

Geometry strategy
-----------------
1. User selects a planar face (+ optional center point)
2. Create a sketch on that face
3. Draw construction curves for the chosen finish:
   - Geneva Stripes / Brushing: parallel lines
   - Perlage: hex/square grid of circles
   - Circular Graining: concentric rings
   - Sunburst: radial rays from center
4. Curves are construction geometry (guides only — no modeled cuts yet)

This is a layout engine for finishing reference, not a polish simulator.
"""

import math
import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm
from fusion.face_utils import (
    add_construction_circle,
    add_construction_line,
    component_from_face,
    face_center_in_sketch,
    require_planar_face,
    sketch_bounds_from_face,
    sketch_point_from_selection,
)
from geometry.finishes import (
    concentric_radii,
    inset_bounds,
    parallel_line_segments,
    perlage_centers,
    sunburst_rays,
)

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_FINISH_GUIDES_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_FINISH_GUIDES_ID,
        defaults.CMD_FINISH_GUIDES_NAME,
        defaults.CMD_FINISH_GUIDES_TOOLTIP,
        '')

    on_created = FinishGuidesCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_FINISH_GUIDES_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_finish(inputs):
    dropdown = inputs.itemById('finishType')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.FINISH_DEFAULT_TYPE


def _apply_finish_ui(inputs):
    finish = _selected_finish(inputs)
    is_geneva = finish in (
        defaults.FINISH_GENEVA, defaults.FINISH_BRUSHING)
    is_perlage = finish == defaults.FINISH_PERLAGE
    is_circular = finish == defaults.FINISH_CIRCULAR
    is_sunburst = finish == defaults.FINISH_SUNBURST

    inputs.itemById('spacing').isVisible = is_geneva or is_perlage or is_circular
    inputs.itemById('angle').isVisible = is_geneva
    inputs.itemById('spotRadius').isVisible = is_perlage
    inputs.itemById('hexGrid').isVisible = is_perlage
    inputs.itemById('rayCount').isVisible = is_sunburst
    inputs.itemById('innerRadius').isVisible = is_sunburst or is_circular
    # Center selection useful for sunburst / circular / perlage origin
    inputs.itemById('center').isVisible = is_sunburst or is_circular or is_perlage


class FinishGuidesCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            face_in = inputs.addSelectionInput(
                'face',
                'Planar Face',
                'Select the face to decorate')
            face_in.addSelectionFilter('PlanarFaces')
            face_in.setSelectionLimits(1, 1)

            center_in = inputs.addSelectionInput(
                'center',
                'Center (optional)',
                'Vertex / sketch point / construction point')
            center_in.addSelectionFilter('Vertices')
            center_in.addSelectionFilter('SketchPoints')
            center_in.addSelectionFilter('ConstructionPoints')
            center_in.setSelectionLimits(0, 1)

            finish = inputs.addDropDownCommandInput(
                'finishType',
                'Finish',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for name in (
                    defaults.FINISH_GENEVA,
                    defaults.FINISH_PERLAGE,
                    defaults.FINISH_CIRCULAR,
                    defaults.FINISH_SUNBURST,
                    defaults.FINISH_BRUSHING):
                finish.listItems.add(name, name == defaults.FINISH_DEFAULT_TYPE)

            inputs.addValueInput(
                'spacing',
                'Spacing',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.FINISH_SPACING_MM)))

            inputs.addValueInput(
                'margin',
                'Edge Margin',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.FINISH_MARGIN_MM)))

            inputs.addValueInput(
                'angle',
                'Angle',
                'deg',
                adsk.core.ValueInput.createByReal(
                    math.radians(defaults.FINISH_ANGLE_DEG)))

            inputs.addValueInput(
                'spotRadius',
                'Spot Radius',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.FINISH_PERLAGE_RADIUS_MM)))

            inputs.addBoolValueInput(
                'hexGrid',
                'Hex Grid',
                True,
                '',
                defaults.FINISH_PERLAGE_HEX)

            inputs.addIntegerSpinnerCommandInput(
                'rayCount',
                'Ray Count',
                3,
                360,
                1,
                int(defaults.FINISH_SUNBURST_RAYS))

            inputs.addValueInput(
                'innerRadius',
                'Inner Radius',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.FINISH_INNER_RADIUS_MM)))

            _apply_finish_ui(inputs)

            # No live preview — dense construction patterns can crash Fusion.
            on_execute = FinishGuidesCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = FinishGuidesCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = FinishGuidesCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Finish Guides dialog failed:\n{}'.format(traceback.format_exc()))


class FinishGuidesCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id == 'finishType':
                _apply_finish_ui(args.inputs)
        except Exception:
            pass


class FinishGuidesCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _finish_guides_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class FinishGuidesCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_finish_guides_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Finish Guides failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _finish_guides_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    if inputs.itemById('face').selectionCount < 1:
        return False

    finish = _selected_finish(inputs)
    margin = inputs.itemById('margin').value
    if margin < 0:
        return False

    if finish in (defaults.FINISH_GENEVA, defaults.FINISH_BRUSHING,
                  defaults.FINISH_PERLAGE, defaults.FINISH_CIRCULAR):
        if inputs.itemById('spacing').value <= 0:
            return False
    if finish == defaults.FINISH_PERLAGE:
        if inputs.itemById('spotRadius').value <= 0:
            return False
    if finish == defaults.FINISH_SUNBURST:
        if int(inputs.itemById('rayCount').value) < 3:
            return False
    if finish in (defaults.FINISH_SUNBURST, defaults.FINISH_CIRCULAR):
        if inputs.itemById('innerRadius').value < 0:
            return False

    return True


def _execute_finish_guides_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    face = require_planar_face(inputs.itemById('face').selection(0).entity)

    center_entity = None
    center_sel = inputs.itemById('center')
    if center_sel.selectionCount > 0:
        center_entity = center_sel.selection(0).entity

    execute_finish_guides(
        face=face,
        finish_type=_selected_finish(inputs),
        spacing_cm=inputs.itemById('spacing').value,
        margin_cm=inputs.itemById('margin').value,
        angle_deg=math.degrees(inputs.itemById('angle').value),
        spot_radius_cm=inputs.itemById('spotRadius').value,
        hex_grid=inputs.itemById('hexGrid').value,
        ray_count=int(inputs.itemById('rayCount').value),
        inner_radius_cm=inputs.itemById('innerRadius').value,
        center_entity=center_entity)


def execute_finish_guides(face, finish_type, spacing_cm, margin_cm, angle_deg=0.0,
                          spot_radius_cm=0.05, hex_grid=True, ray_count=24,
                          inner_radius_cm=0.0, center_entity=None):
    """Draw construction finish guides on a planar face."""
    component = component_from_face(face)
    sketch = component.sketches.add(face)
    if not sketch:
        raise RuntimeError('Failed to create a sketch on the selected face.')

    short = {
        defaults.FINISH_GENEVA: 'Geneva',
        defaults.FINISH_PERLAGE: 'Perlage',
        defaults.FINISH_CIRCULAR: 'CircularGrain',
        defaults.FINISH_SUNBURST: 'Sunburst',
        defaults.FINISH_BRUSHING: 'Brushing',
    }.get(finish_type, 'Finish')
    sketch.name = 'FinishGuides_{}'.format(short)

    min_x, min_y, max_x, max_y = sketch_bounds_from_face(sketch, face)
    x0, y0, x1, y1 = inset_bounds(min_x, min_y, max_x, max_y, margin_cm)

    if center_entity is not None:
        cpt = sketch_point_from_selection(sketch, center_entity)
    else:
        cpt = face_center_in_sketch(sketch, face)
    cx, cy = cpt.x, cpt.y

    # Clamp center into inset bounds for radial finishes.
    cx = min(max(cx, x0), x1)
    cy = min(max(cy, y0), y1)

    half_w = 0.5 * (x1 - x0)
    half_h = 0.5 * (y1 - y0)
    outer_r = math.hypot(half_w, half_h)

    if finish_type in (defaults.FINISH_GENEVA, defaults.FINISH_BRUSHING):
        segs = parallel_line_segments(x0, y0, x1, y1, spacing_cm, angle_deg)
        for (p0, p1) in segs:
            add_construction_line(sketch, p0[0], p0[1], p1[0], p1[1])

    elif finish_type == defaults.FINISH_PERLAGE:
        centers = perlage_centers(x0, y0, x1, y1, spacing_cm, hex_grid=hex_grid)
        for px, py in centers:
            add_construction_circle(sketch, px, py, spot_radius_cm)

    elif finish_type == defaults.FINISH_CIRCULAR:
        # Outer limit: distance from center to farthest inset corner.
        corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
        outer = max(math.hypot(px - cx, py - cy) for px, py in corners)
        radii = concentric_radii(inner_radius_cm, outer, spacing_cm)
        for r in radii:
            add_construction_circle(sketch, cx, cy, r)

    elif finish_type == defaults.FINISH_SUNBURST:
        corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
        outer = max(math.hypot(px - cx, py - cy) for px, py in corners)
        rays = sunburst_rays(cx, cy, inner_radius_cm, outer, ray_count)
        for (p0, p1) in rays:
            add_construction_line(sketch, p0[0], p0[1], p1[0], p1[1])

    else:
        raise ValueError('Unknown finish type: {!r}'.format(finish_type))

    sketch.isVisible = True
    return sketch
