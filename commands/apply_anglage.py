"""APPLY ANGLAGE — watch-style edge bevels via native Fusion chamfers.

Geometry strategy
-----------------
1. Select one or more edges (bridges, plates, cutouts, etc.)
2. Choose Equal Distance or Distance + Angle
3. Create a parametric ChamferFeature (editable in the timeline)

This produces real solid bevels — the CAD counterpart of anglage layout.
Polishing the facet is still a finishing step outside Fusion.
"""

import math
import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm

_handlers = []


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_ANGLAGE_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_ANGLAGE_ID,
        defaults.CMD_ANGLAGE_NAME,
        defaults.CMD_ANGLAGE_TOOLTIP,
        '')

    on_created = AnglageCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_ANGLAGE_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_mode(inputs):
    dropdown = inputs.itemById('mode')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.ANGLAGE_DEFAULT_MODE


def _apply_anglage_ui(inputs):
    mode = _selected_mode(inputs)
    is_angle = mode == defaults.ANGLAGE_MODE_DISTANCE_ANGLE
    inputs.itemById('angle').isVisible = is_angle
    inputs.itemById('flip').isVisible = is_angle


class AnglageCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            edge_in = inputs.addSelectionInput(
                'edges',
                'Edges',
                'Select edges to bevel (anglage)')
            edge_in.addSelectionFilter('Edges')
            edge_in.setSelectionLimits(1, 0)  # 1..unlimited

            mode = inputs.addDropDownCommandInput(
                'mode',
                'Chamfer Type',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.ANGLAGE_MODE_EQUAL,
                    defaults.ANGLAGE_MODE_DISTANCE_ANGLE):
                mode.listItems.add(
                    label, label == defaults.ANGLAGE_DEFAULT_MODE)

            inputs.addValueInput(
                'width',
                'Bevel Width',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.ANGLAGE_WIDTH_MM)))

            inputs.addValueInput(
                'angle',
                'Bevel Angle',
                'deg',
                adsk.core.ValueInput.createByReal(
                    math.radians(defaults.ANGLAGE_ANGLE_DEG)))

            inputs.addBoolValueInput(
                'tangentChain',
                'Tangent Chain',
                True,
                '',
                defaults.ANGLAGE_TANGENT_CHAIN)

            inputs.addBoolValueInput(
                'flip',
                'Flip Direction',
                True,
                '',
                defaults.ANGLAGE_FLIP)

            _apply_anglage_ui(inputs)

            # Live viewport preview while the dialog is open (Fusion rolls it
            # back on each input change; OK keeps the last valid preview).
            on_preview = AnglageCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = AnglageCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = AnglageCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = AnglageCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Anglage dialog failed:\n{}'.format(traceback.format_exc()))


class AnglageCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id == 'mode':
                _apply_anglage_ui(args.inputs)
        except Exception:
            pass


class AnglageCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _anglage_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class AnglageCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """Rebuild geometry as inputs change; commit last preview on OK."""
        try:
            inputs = args.command.commandInputs
            if not _anglage_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_anglage_from_inputs(inputs)
            args.isValidResult = True
        except Exception:
            # Invalid preview → Fusion aborts the preview transaction.
            args.isValidResult = False


class AnglageCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        # Only runs if preview did not set isValidResult=True (fallback).
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_anglage_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Anglage failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _anglage_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    if inputs.itemById('edges').selectionCount < 1:
        return False
    if inputs.itemById('width').value <= 0:
        return False
    mode = _selected_mode(inputs)
    if mode == defaults.ANGLAGE_MODE_DISTANCE_ANGLE:
        ang = math.degrees(inputs.itemById('angle').value)
        if not (1.0 < ang < 89.0):
            return False
    return True


def _execute_anglage_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    edge_sel = inputs.itemById('edges')
    edges = []
    for i in range(edge_sel.selectionCount):
        edge = adsk.fusion.BRepEdge.cast(edge_sel.selection(i).entity)
        if edge:
            edges.append(edge)
    if not edges:
        raise RuntimeError('No valid edges selected.')

    execute_anglage(
        edges=edges,
        mode=_selected_mode(inputs),
        width_cm=inputs.itemById('width').value,
        angle_deg=math.degrees(inputs.itemById('angle').value),
        tangent_chain=inputs.itemById('tangentChain').value,
        flip=inputs.itemById('flip').value)


def execute_anglage(edges, mode, width_cm, angle_deg=45.0,
                    tangent_chain=True, flip=False):
    """Create a native Fusion chamfer (anglage) on the given edges."""
    if width_cm <= 0:
        raise ValueError('Bevel width must be greater than zero.')

    first = edges[0]
    body = first.body
    if not body:
        raise RuntimeError('Selected edge has no parent body.')
    component = body.parentComponent
    if not component:
        raise RuntimeError('Could not resolve the parent component.')

    # Keep all edges in the same component when possible.
    for edge in edges:
        if edge.body and edge.body.parentComponent != component:
            raise RuntimeError(
                'Select edges from the same component/body for one Anglage feature.')

    collection = adsk.core.ObjectCollection.create()
    for edge in edges:
        collection.add(edge)

    chamfers = component.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    if not chamfer_input:
        raise RuntimeError('Failed to create chamfer input.')

    distance = adsk.core.ValueInput.createByReal(float(width_cm))

    if mode == defaults.ANGLAGE_MODE_EQUAL:
        # Equal distance ≈ classic 45° facet when faces meet at right angles.
        chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            collection, distance, bool(tangent_chain))
    else:
        if not (1.0 < float(angle_deg) < 89.0):
            raise ValueError('Bevel angle must be between 1° and 89°.')
        angle = adsk.core.ValueInput.createByString('{} deg'.format(angle_deg))
        chamfer_input.chamferEdgeSets.addDistanceAndAngleChamferEdgeSet(
            collection, distance, angle, bool(flip), bool(tangent_chain))

    chamfer = chamfers.add(chamfer_input)
    if not chamfer:
        raise RuntimeError(
            'Failed to create anglage chamfer. Check edge selection and width.')

    chamfer.name = defaults.ANGLAGE_FEATURE_NAME
    return chamfer
