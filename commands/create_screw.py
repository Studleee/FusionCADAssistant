"""CREATE SCREW command.

Geometry strategy
-----------------
1. New component named Screw
2. Choose head style: None / Hex / Flathead / Tri-Slot
3. Stem diameter + stem length (thread blank)
4. Head width + head length when a head is selected
   - Hex: polygon on shank end + join extrude (width = across flats)
   - Flathead: revolved frustum + stem (width = head OD)
   - Tri-Slot: cheese-head cylinder with three radial kerfs (solid hub)
5. Head shape: Squared (square shoulder), Cove (concave), or Countersunk (cone)
6. Optional flat drive slot (or three parallel slots when Reversing is on)
7. Native Fusion Thread on the stem cylinder (cosmetic or modeled);
   Reversing uses left-hand thread

Size presets seed thread designation and suggested dimensions; all sizes
remain user-editable.
"""

import math
import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import (
    mm_to_cm,
    screw_head_dims_mm,
    screw_matching_thread_designation,
    screw_preset_by_designation,
    screw_slot_dims_mm,
    screw_stem_length_mm,
)
from fusion.components import create_component, get_active_design
from fusion.features import (
    create_constant_fillet,
    create_cut_extrude,
    create_extrude,
    create_revolve,
    find_cylindrical_face,
    name_first_body,
)
from fusion.parameters import link_dimension_to_parameter, set_user_parameter
from fusion.polygons import add_regular_polygon, hex_vertex_radius_from_across_flats
from fusion.sketches import (
    add_diameter_dimension,
    create_circle,
    create_offset_plane,
    create_sketch_on_plane,
)
from fusion.threads import create_external_thread, find_thread_type

_handlers = []


def start(ui):
    """Register the Create Screw command definition."""
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_SCREW_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_SCREW_ID,
        defaults.CMD_CREATE_SCREW_NAME,
        defaults.CMD_CREATE_SCREW_TOOLTIP,
        '')

    on_created = CreateScrewCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    """Remove the command definition."""
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_SCREW_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _selected_designation(inputs):
    dropdown = inputs.itemById('screwSize')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.SCREW_DEFAULT_DESIGNATION


def _selected_head_style(inputs):
    dropdown = inputs.itemById('headStyle')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.SCREW_DEFAULT_HEAD_STYLE


def _selected_head_shape(inputs):
    dropdown = inputs.itemById('headShape')
    for i in range(dropdown.listItems.count):
        item = dropdown.listItems.item(i)
        if item.isSelected:
            return item.name
    return defaults.SCREW_DEFAULT_HEAD_SHAPE


def _apply_screw_ui(inputs):
    full_thread = inputs.itemById('fullThread').value
    thread_length = inputs.itemById('threadLength')
    if thread_length:
        thread_length.isEnabled = not full_thread

    head_style = _selected_head_style(inputs)
    has_head = head_style != defaults.SCREW_HEAD_NONE
    is_tri_slot = head_style == defaults.SCREW_HEAD_TRI_SLOT

    for input_id in ('headWidth', 'headLength'):
        item = inputs.itemById(input_id)
        if item:
            item.isVisible = has_head
            item.isEnabled = has_head

    shape = inputs.itemById('headShape')
    if shape:
        shape.isVisible = has_head and not is_tri_slot
        shape.isEnabled = has_head and not is_tri_slot

    drive = inputs.itemById('driveSlot')
    if drive:
        # Tri-Slot head has built-in radial kerfs; hide the optional flat slot.
        drive.isVisible = has_head and not is_tri_slot
        drive.isEnabled = has_head and not is_tri_slot

    reversing_input = inputs.itemById('reversing')
    if reversing_input:
        reversing_input.isVisible = True
        reversing_input.isEnabled = True

    reversing = inputs.itemById('reversing').value
    drive_on = (
        False if is_tri_slot
        else (has_head and inputs.itemById('driveSlot').value))
    slot_on = has_head and (drive_on or reversing or is_tri_slot)
    for input_id in ('slotWidth', 'slotDepth'):
        item = inputs.itemById(input_id)
        if item:
            item.isVisible = slot_on
            item.isEnabled = slot_on


def _seed_dims_from_preset(inputs, designation=None, head_style=None):
    """Push preset-suggested values into the dialog (stem + head)."""
    designation = designation or _selected_designation(inputs)
    head_style = head_style or _selected_head_style(inputs)
    preset = screw_preset_by_designation(designation)
    if not preset:
        return

    major_mm = preset[1]
    stem = inputs.itemById('stemDiameter')
    if stem:
        stem.value = mm_to_cm(major_mm)

    stem_len = inputs.itemById('stemLength')
    if stem_len:
        length_mm = screw_stem_length_mm(preset)
        stem_len.value = mm_to_cm(length_mm)

    thread_len = inputs.itemById('threadLength')
    if thread_len:
        # Default partial thread ~80% of stem, leave full-thread toggle alone.
        thread_len.value = mm_to_cm(screw_stem_length_mm(preset) * 0.85)

    if head_style == defaults.SCREW_HEAD_NONE:
        return

    width_mm, height_mm = screw_head_dims_mm(preset, head_style)
    head_width = inputs.itemById('headWidth')
    head_length = inputs.itemById('headLength')
    if head_width:
        head_width.value = mm_to_cm(width_mm)
    if head_length:
        head_length.value = mm_to_cm(height_mm)

    _seed_slot_dims(inputs, width_mm, height_mm)


def _seed_slot_dims(inputs, head_width_mm=None, head_length_mm=None):
    """Refresh suggested slot width/depth from current head fields."""
    if head_width_mm is None:
        head_width_mm = inputs.itemById('headWidth').value * 10.0
    if head_length_mm is None:
        head_length_mm = inputs.itemById('headLength').value * 10.0
    slot_w_mm, slot_d_mm = screw_slot_dims_mm(head_width_mm, head_length_mm)
    slot_w = inputs.itemById('slotWidth')
    slot_d = inputs.itemById('slotDepth')
    if slot_w:
        slot_w.value = mm_to_cm(slot_w_mm)
    if slot_d:
        slot_d.value = mm_to_cm(slot_d_mm)


class CreateScrewCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            default_preset = screw_preset_by_designation(
                defaults.SCREW_DEFAULT_DESIGNATION)
            default_head = defaults.SCREW_DEFAULT_HEAD_STYLE
            head_w_mm, head_h_mm = screw_head_dims_mm(default_preset, default_head)
            stem_mm = default_preset[1] if default_preset else 6.0

            size_input = inputs.addDropDownCommandInput(
                'screwSize',
                'Thread Size',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            size_input.tooltip = (
                'ISO thread preset. Seeds stem/head sizes; change Stem Diameter '
                'freely afterward. Thread texture only applies when stem Ø matches.')
            for designation, *_rest in defaults.SCREW_SIZE_PRESETS:
                is_default = designation == defaults.SCREW_DEFAULT_DESIGNATION
                size_input.listItems.add(designation, is_default)

            head_input = inputs.addDropDownCommandInput(
                'headStyle',
                'Head Style',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.SCREW_HEAD_HEX,
                    defaults.SCREW_HEAD_FLAT,
                    defaults.SCREW_HEAD_TRI_SLOT,
                    defaults.SCREW_HEAD_NONE):
                head_input.listItems.add(label, label == default_head)

            shape_input = inputs.addDropDownCommandInput(
                'headShape',
                'Head Shape',
                adsk.core.DropDownStyles.TextListDropDownStyle)
            for label in (
                    defaults.SCREW_SHAPE_SQUARED,
                    defaults.SCREW_SHAPE_COVE,
                    defaults.SCREW_SHAPE_COUNTERSUNK):
                shape_input.listItems.add(
                    label, label == defaults.SCREW_DEFAULT_HEAD_SHAPE)

            stem_input = inputs.addValueInput(
                'stemDiameter',
                'Stem Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(stem_mm)))
            stem_input.tooltip = (
                'Blank / major diameter — freely editable. '
                'Cosmetic thread applies only when this matches Thread Size.')

            inputs.addValueInput(
                'stemLength',
                'Stem Length',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(defaults.SCREW_LENGTH_MM)))

            inputs.addValueInput(
                'headWidth',
                'Head Width',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(head_w_mm)))

            inputs.addValueInput(
                'headLength',
                'Head Length',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(head_h_mm)))

            slot_w_mm, slot_d_mm = screw_slot_dims_mm(head_w_mm, head_h_mm)
            inputs.addBoolValueInput(
                'driveSlot',
                'Drive Slot',
                True,
                '',
                defaults.SCREW_DRIVE_SLOT)

            inputs.addBoolValueInput(
                'reversing',
                'Reversing',
                True,
                '',
                defaults.SCREW_REVERSING)

            inputs.addValueInput(
                'slotWidth',
                'Slot Width',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(slot_w_mm)))

            inputs.addValueInput(
                'slotDepth',
                'Slot Depth',
                'mm',
                adsk.core.ValueInput.createByReal(mm_to_cm(slot_d_mm)))

            inputs.addBoolValueInput(
                'fullThread',
                'Full Thread',
                True,
                '',
                defaults.SCREW_FULL_THREAD)

            inputs.addValueInput(
                'threadLength',
                'Thread Length',
                'mm',
                adsk.core.ValueInput.createByReal(
                    mm_to_cm(defaults.SCREW_THREAD_LENGTH_MM)))

            inputs.addBoolValueInput(
                'modeled',
                'Modeled Thread',
                True,
                '',
                defaults.SCREW_MODELED)

            _apply_screw_ui(inputs)

            # Live viewport preview while the dialog is open (Fusion rolls it
            # back on each input change; OK keeps the last valid preview).
            on_preview = CreateScrewCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreateScrewCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateScrewCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateScrewCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox('Create Screw dialog failed:\n{}'.format(traceback.format_exc()))


class CreateScrewCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            changed = args.input.id
            if changed in (
                    'fullThread', 'headStyle', 'screwSize', 'driveSlot',
                    'reversing'):
                _apply_screw_ui(args.inputs)
            if changed == 'screwSize':
                _seed_dims_from_preset(args.inputs)
            elif changed == 'headStyle':
                # Refresh head suggestions for the new style; keep stem as-is.
                designation = _selected_designation(args.inputs)
                head_style = _selected_head_style(args.inputs)
                preset = screw_preset_by_designation(designation)
                if preset and head_style != defaults.SCREW_HEAD_NONE:
                    width_mm, height_mm = screw_head_dims_mm(preset, head_style)
                    args.inputs.itemById('headWidth').value = mm_to_cm(width_mm)
                    args.inputs.itemById('headLength').value = mm_to_cm(height_mm)
                    _seed_slot_dims(args.inputs, width_mm, height_mm)
            elif changed in ('headWidth', 'headLength'):
                head_style = _selected_head_style(args.inputs)
                drive_on = args.inputs.itemById('driveSlot').value
                reversing = args.inputs.itemById('reversing').value
                is_tri = head_style == defaults.SCREW_HEAD_TRI_SLOT
                if drive_on or reversing or is_tri:
                    _seed_slot_dims(args.inputs)
        except Exception:
            pass


class CreateScrewCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _screw_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateScrewCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        """Rebuild geometry as inputs change; commit last preview on OK."""
        try:
            inputs = args.command.commandInputs
            if not _screw_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_screw_from_inputs(inputs)
            args.isValidResult = True
        except Exception:
            # Invalid preview → Fusion aborts the preview transaction.
            args.isValidResult = False


class CreateScrewCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        # Only runs if preview did not set isValidResult=True (fallback).
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_screw_from_inputs(args.command.commandInputs)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Screw failed:\n{}\n\n{}'.format(exc, traceback.format_exc()))


def _screw_inputs_are_valid(inputs):
    """Same rules as the dialog ValidateInputs handler."""
    stem_dia = inputs.itemById('stemDiameter').value
    stem_len = inputs.itemById('stemLength').value
    if stem_dia <= 0 or stem_len <= 0:
        return False

    if not inputs.itemById('fullThread').value:
        thread_length = inputs.itemById('threadLength').value
        if thread_length <= 0 or thread_length > stem_len + 1e-6:
            return False

    head_style = _selected_head_style(inputs)
    if head_style != defaults.SCREW_HEAD_NONE:
        head_w = inputs.itemById('headWidth').value
        head_h = inputs.itemById('headLength').value
        if head_w <= 0 or head_h <= 0:
            return False
        if head_style in (
                defaults.SCREW_HEAD_FLAT,
                defaults.SCREW_HEAD_HEX,
                defaults.SCREW_HEAD_TRI_SLOT):
            if head_w <= stem_dia + 1e-6:
                return False
        needs_slots = (
            head_style == defaults.SCREW_HEAD_TRI_SLOT
            or inputs.itemById('driveSlot').value
            or inputs.itemById('reversing').value)
        if needs_slots:
            slot_w = inputs.itemById('slotWidth').value
            slot_d = inputs.itemById('slotDepth').value
            if slot_w <= 0 or slot_d <= 0 or slot_d >= head_h - 1e-6:
                return False
            if slot_w >= head_w - 1e-6:
                return False
    return True


def _execute_screw_from_inputs(inputs):
    """Build from the current dialog values (shared by preview + execute)."""
    reversing = inputs.itemById('reversing').value
    head_style = _selected_head_style(inputs)
    is_tri = head_style == defaults.SCREW_HEAD_TRI_SLOT
    drive_slot = (
        True if is_tri
        else (inputs.itemById('driveSlot').value or reversing))
    execute_create_screw(
        designation=_selected_designation(inputs),
        head_style=head_style,
        head_shape=_selected_head_shape(inputs),
        stem_diameter_cm=inputs.itemById('stemDiameter').value,
        stem_length_cm=inputs.itemById('stemLength').value,
        head_width_cm=inputs.itemById('headWidth').value,
        head_length_cm=inputs.itemById('headLength').value,
        drive_slot=drive_slot,
        slot_width_cm=inputs.itemById('slotWidth').value,
        slot_depth_cm=inputs.itemById('slotDepth').value,
        full_thread=inputs.itemById('fullThread').value,
        thread_length_cm=inputs.itemById('threadLength').value,
        modeled=inputs.itemById('modeled').value,
        reversing=reversing)


def execute_create_screw(designation, head_style, stem_diameter_cm, stem_length_cm,
                         head_width_cm=None, head_length_cm=None,
                         head_shape=None, drive_slot=False,
                         slot_width_cm=None, slot_depth_cm=None,
                         full_thread=True, thread_length_cm=None,
                         modeled=False, reversing=False):
    """Build a metric screw blank with optional hex/flat head + Fusion thread.

    Stem diameter is always taken from the dialog. Fusion threads require the
    cylinder Ø to match an ISO designation — if the stem does not match, the
    blank is still created and the thread step is skipped.

    reversing: left-hand thread and three parallel drive slots.
    """
    if head_shape is None:
        head_shape = defaults.SCREW_DEFAULT_HEAD_SHAPE

    if stem_diameter_cm <= 0:
        raise ValueError('Stem diameter must be greater than zero.')
    if stem_length_cm <= 0:
        raise ValueError('Stem length must be greater than zero.')

    has_head = head_style != defaults.SCREW_HEAD_NONE
    is_tri_slot = head_style == defaults.SCREW_HEAD_TRI_SLOT
    if reversing and has_head and not is_tri_slot:
        drive_slot = True
    if is_tri_slot:
        drive_slot = True
        head_shape = defaults.SCREW_SHAPE_SQUARED
    if has_head:
        if head_width_cm is None or head_length_cm is None:
            raise ValueError('Head width and head length are required.')
        if head_width_cm <= stem_diameter_cm:
            raise ValueError('Head width must be larger than stem diameter.')
        if head_length_cm <= 0:
            raise ValueError('Head length must be greater than zero.')
        if drive_slot:
            if slot_width_cm is None or slot_depth_cm is None:
                raise ValueError('Slot width and depth are required.')
            if slot_width_cm <= 0 or slot_depth_cm <= 0:
                raise ValueError('Slot width and depth must be greater than zero.')
            if slot_depth_cm >= head_length_cm:
                raise ValueError('Slot depth must be less than head length.')
            if slot_width_cm >= head_width_cm:
                raise ValueError('Slot width must be less than head width.')

    design = get_active_design()

    set_user_parameter(
        design, defaults.PARAM_SCREW_STEM_DIAMETER, stem_diameter_cm,
        comment='CREATE SCREW stem / blank diameter')
    set_user_parameter(
        design, defaults.PARAM_SCREW_MAJOR_DIAMETER, stem_diameter_cm,
        comment='CREATE SCREW major diameter (stem)')
    set_user_parameter(
        design, defaults.PARAM_SCREW_LENGTH, stem_length_cm,
        comment='CREATE SCREW stem length')
    if not full_thread and thread_length_cm is not None:
        set_user_parameter(
            design, defaults.PARAM_SCREW_THREAD_LENGTH, thread_length_cm,
            comment='CREATE SCREW partial thread length')
    if has_head:
        set_user_parameter(
            design, defaults.PARAM_SCREW_HEAD_WIDTH, head_width_cm,
            comment='CREATE SCREW head width (OD or hex AF)')
        set_user_parameter(
            design, defaults.PARAM_SCREW_HEAD_HEIGHT, head_length_cm,
            comment='CREATE SCREW head length')
        if head_style == defaults.SCREW_HEAD_HEX:
            set_user_parameter(
                design, defaults.PARAM_SCREW_HEX_AF, head_width_cm,
                comment='CREATE SCREW hex across flats')
        if drive_slot:
            set_user_parameter(
                design, defaults.PARAM_SCREW_SLOT_WIDTH, slot_width_cm,
                comment='CREATE SCREW drive slot width')
            set_user_parameter(
                design, defaults.PARAM_SCREW_SLOT_DEPTH, slot_depth_cm,
                comment='CREATE SCREW drive slot depth')

    _occ, component = create_component(design, defaults.SCREW_COMPONENT_NAME)

    if head_style in (defaults.SCREW_HEAD_FLAT, defaults.SCREW_HEAD_TRI_SLOT):
        body, cylinder_face = _build_flathead_screw(
            component, stem_diameter_cm, stem_length_cm,
            head_width_cm, head_length_cm, head_shape=head_shape)
        z_top_cm = float(head_length_cm)
    else:
        body, cylinder_face = _build_shank_screw(
            component, stem_diameter_cm, stem_length_cm)
        z_top_cm = float(stem_length_cm)
        if head_style == defaults.SCREW_HEAD_HEX:
            _add_hex_head(
                component, body, stem_diameter_cm,
                head_width_cm, head_length_cm)
            if head_shape == defaults.SCREW_SHAPE_COVE:
                _add_hex_cove_fillet(
                    component, body, stem_diameter_cm, stem_length_cm,
                    head_width_cm, head_length_cm)
            cylinder_face = find_cylindrical_face(body, stem_diameter_cm * 0.5)
            z_top_cm = float(stem_length_cm) + float(head_length_cm)

    if is_tri_slot:
        _add_radial_tri_slots(
            component, body, head_width_cm, slot_width_cm, slot_depth_cm,
            z_top_cm=z_top_cm)
        cylinder_face = find_cylindrical_face(body, stem_diameter_cm * 0.5)
    elif has_head and drive_slot:
        slot_count = (
            int(defaults.SCREW_REVERSING_SLOT_COUNT) if reversing else 1)
        _add_drive_slot(
            component, body, head_width_cm, slot_width_cm, slot_depth_cm,
            z_top_cm=z_top_cm, slot_count=slot_count)
        # Slot cut can invalidate the prior face reference.
        cylinder_face = find_cylindrical_face(body, stem_diameter_cm * 0.5)

    thread = None
    thread_des = screw_matching_thread_designation(
        stem_diameter_cm, preferred=designation)
    if thread_des:
        try:
            thread_type = find_thread_type(
                component.features.threadFeatures, defaults.SCREW_THREAD_TYPE)
            thread = create_external_thread(
                component,
                cylinder_face,
                thread_type=thread_type,
                designation=thread_des,
                thread_class=defaults.SCREW_THREAD_CLASS_EXTERNAL,
                is_modeled=modeled,
                is_full_length=full_thread,
                thread_length_cm=None if full_thread else thread_length_cm,
                is_right_handed=not reversing,
                name=defaults.SCREW_THREAD_NAME)
        except Exception:
            # Stem Ø may be close but Fusion thread data still rejects it.
            thread = None

    return component, body, thread


def _add_radial_tri_slots(component, body, head_width_cm, slot_width_cm,
                          slot_depth_cm, z_top_cm):
    """Cut three radial slots at 120° that stop short of a solid center hub."""
    ra = float(head_width_cm) * 0.5
    r_inner = ra * float(defaults.SCREW_TRI_SLOT_HUB_FRACTION)
    r_outer = ra * 1.08
    half_w = float(slot_width_cm) * 0.5
    # Keep the hub from being cut away by an oversized kerf.
    max_half = max(r_inner * 0.75, float(slot_width_cm) * 0.25)
    if half_w > max_half:
        half_w = max_half

    count = int(defaults.SCREW_TRI_SLOT_COUNT)
    for index in range(count):
        angle = (2.0 * math.pi / float(count)) * float(index)
        sketch_name = '{}{}'.format(defaults.SCREW_SLOT_SKETCH_NAME, index + 1)
        cut_name = '{}{}'.format(defaults.SCREW_SLOT_CUT_NAME, index + 1)
        plane = create_offset_plane(component, z_top_cm)
        sketch = create_sketch_on_plane(component, plane, name=sketch_name)
        _add_radial_slot_rectangle(sketch, r_inner, r_outer, half_w, angle)

        if sketch.profiles.count < 1:
            raise RuntimeError('Tri-slot sketch has no profile.')
        profile = _largest_sketch_profile(sketch)
        create_cut_extrude(
            component,
            profile,
            distance_cm=slot_depth_cm,
            name=cut_name,
            expression=(
                defaults.PARAM_SCREW_SLOT_DEPTH if index == 0 else None),
            participant_bodies=[body],
            into_solid=True)


def _add_radial_slot_rectangle(sketch, r_inner, r_outer, half_w, angle_rad):
    """Rectangle from r_inner→r_outer, width 2*half_w, rotated about origin."""
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    local = (
        (r_inner, -half_w),
        (r_outer, -half_w),
        (r_outer, half_w),
        (r_inner, half_w),
    )
    pts = []
    for x, y in local:
        pts.append(adsk.core.Point3D.create(
            x * cos_a - y * sin_a,
            x * sin_a + y * cos_a,
            0.0))
    lines = sketch.sketchCurves.sketchLines
    for i in range(4):
        line = lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])
        if not line:
            raise RuntimeError('Failed to create tri-slot rectangle.')


def _add_drive_slot(component, body, head_width_cm, slot_width_cm, slot_depth_cm,
                    z_top_cm, slot_count=1):
    """Cut flat screwdriver slot(s) across the head top face.

    slot_count=1 → single diametral kerf.
    slot_count=3 → three parallel kerfs (center + one each side), like rails.
    """
    slot_count = max(1, int(slot_count))
    half_len = float(head_width_cm) * 0.55
    half_w = float(slot_width_cm) * 0.5
    y_offsets = _parallel_slot_offsets(slot_count, slot_width_cm, head_width_cm)

    for index, y_off in enumerate(y_offsets):
        sketch_name = defaults.SCREW_SLOT_SKETCH_NAME
        cut_name = defaults.SCREW_SLOT_CUT_NAME
        if slot_count > 1:
            sketch_name = '{}{}'.format(sketch_name, index + 1)
            cut_name = '{}{}'.format(cut_name, index + 1)

        plane = create_offset_plane(component, z_top_cm)
        sketch = create_sketch_on_plane(component, plane, name=sketch_name)
        p0 = adsk.core.Point3D.create(-half_len, y_off - half_w, 0.0)
        p1 = adsk.core.Point3D.create(half_len, y_off + half_w, 0.0)
        rect = sketch.sketchCurves.sketchLines.addTwoPointRectangle(p0, p1)
        if not rect:
            raise RuntimeError('Failed to create drive-slot rectangle.')

        if sketch.profiles.count < 1:
            raise RuntimeError('Drive-slot sketch has no profile.')

        profile = _largest_sketch_profile(sketch)
        create_cut_extrude(
            component,
            profile,
            distance_cm=slot_depth_cm,
            name=cut_name,
            expression=(
                defaults.PARAM_SCREW_SLOT_DEPTH if index == 0 else None),
            participant_bodies=[body],
            into_solid=True)


def _parallel_slot_offsets(slot_count, slot_width_cm, head_width_cm):
    """Y offsets for parallel slots centered on the head (middle at 0)."""
    if slot_count <= 1:
        return (0.0,)
    # Center-to-center ≈ 2× kerf so a clear land sits between each rail.
    spacing = float(slot_width_cm) * 2.0
    max_spacing = float(head_width_cm) * 0.28
    if spacing > max_spacing:
        spacing = max(max_spacing, float(slot_width_cm) * 1.35)
    if slot_count == 3:
        return (-spacing, 0.0, spacing)
    # Generic odd count: symmetric about center.
    half = slot_count // 2
    return tuple((i - half) * spacing for i in range(slot_count))


def _largest_sketch_profile(sketch):
    """Pick the largest closed profile in a sketch."""
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
    if best is None:
        raise RuntimeError('Drive-slot sketch has no usable profile.')
    return best


def _build_shank_screw(component, stem_diameter_cm, stem_length_cm):
    """Extrude a cylindrical stem; return (body, side_face)."""
    sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane,
        name=defaults.SCREW_SHANK_SKETCH_NAME)
    radius_cm = stem_diameter_cm * 0.5
    circle = create_circle(sketch, sketch.originPoint, radius_cm)
    dim = add_diameter_dimension(
        sketch,
        circle,
        adsk.core.Point3D.create(radius_cm * 1.4, 0, 0),
        diameter_cm=stem_diameter_cm)
    link_dimension_to_parameter(dim, defaults.PARAM_SCREW_STEM_DIAMETER)

    if sketch.profiles.count < 1:
        raise RuntimeError('Screw stem sketch has no profile.')
    profile = sketch.profiles.item(0)

    shank = create_extrude(
        component,
        profile,
        distance_cm=stem_length_cm,
        name=defaults.SCREW_SHANK_EXTRUDE_NAME,
        expression=defaults.PARAM_SCREW_LENGTH)
    body = name_first_body(shank, defaults.SCREW_BODY_NAME)

    if shank.sideFaces.count < 1:
        raise RuntimeError('Stem extrude has no cylindrical side face.')
    return body, shank.sideFaces.item(0)


def _build_flathead_screw(component, stem_diameter_cm, stem_length_cm,
                          head_width_cm, head_length_cm,
                          head_shape=None):
    """Revolve a flat-top head + stem.

    Squared      — cheese/fillister: vertical OD wall, sharp 90° shoulder
    Cove         — concave underside from head OD to stem
    Countersunk  — straight conical taper (classic flat-head screw)
    """
    if head_shape is None:
        head_shape = defaults.SCREW_SHAPE_SQUARED

    head_r = float(head_width_cm) * 0.5
    stem_r = float(stem_diameter_cm) * 0.5
    z_top = float(head_length_cm)
    z_tip = -float(stem_length_cm)

    sketch = component.sketches.add(component.xZConstructionPlane)
    sketch.name = defaults.SCREW_PROFILE_SKETCH_NAME
    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    def sk(x, z):
        return sketch.modelToSketchSpace(adsk.core.Point3D.create(x, 0.0, z))

    # Shared points: top flat + stem + axis close.
    p0 = sk(0.0, z_top)          # axis @ head top
    p1 = sk(head_r, z_top)       # outer head top
    p_stem = sk(stem_r, 0.0)     # stem at head/stem joint plane
    p3 = sk(stem_r, z_tip)
    p4 = sk(0.0, z_tip)

    lines.addByTwoPoints(p0, p1)

    if head_shape == defaults.SCREW_SHAPE_SQUARED:
        # Vertical wall down the head height, then square step to the stem.
        p_outer_bottom = sk(head_r, 0.0)
        lines.addByTwoPoints(p1, p_outer_bottom)
        lines.addByTwoPoints(p_outer_bottom, p_stem)
    elif head_shape == defaults.SCREW_SHAPE_COVE:
        # Concave underside: mid point toward the axis (hollow under the head).
        span = head_r - stem_r
        x_mid = (head_r + stem_r) * 0.5 - span * 0.35
        z_mid = z_top * 0.5
        if x_mid <= stem_r + 1e-8:
            x_mid = stem_r + max(span * 0.15, 1e-4)
        p_mid = sk(x_mid, z_mid)
        arc = arcs.addByThreePoints(p1, p_mid, p_stem)
        if not arc:
            raise RuntimeError('Failed to create cove arc for flathead.')
    else:
        # Countersunk: straight conical generators.
        lines.addByTwoPoints(p1, p_stem)

    lines.addByTwoPoints(p_stem, p3)
    lines.addByTwoPoints(p3, p4)
    lines.addByTwoPoints(p4, p0)

    if sketch.profiles.count < 1:
        raise RuntimeError('Flathead profile sketch has no profile.')

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

    revolve = create_revolve(
        component,
        profile,
        component.zConstructionAxis,
        name=defaults.SCREW_REVOLVE_NAME)
    body = name_first_body(revolve, defaults.SCREW_BODY_NAME)
    side = find_cylindrical_face(body, stem_r)
    return body, side


def _add_hex_cove_fillet(component, body, stem_diameter_cm, stem_length_cm,
                         head_width_cm, head_length_cm):
    """Blend hex head into stem with a cove fillet at the junction circle."""
    stem_r = float(stem_diameter_cm) * 0.5
    overhang = (float(head_width_cm) * 0.5) - stem_r
    radius = min(float(head_length_cm) * 0.4, overhang * 0.45)
    if radius <= 1e-4:
        return

    edges = _find_circular_edges_near(
        body, radius_cm=stem_r, z_cm=float(stem_length_cm))
    if not edges:
        # Fallback: any circular edge matching stem radius.
        edges = _find_circular_edges_near(body, radius_cm=stem_r, z_cm=None)
    if not edges:
        raise RuntimeError(
            'Could not find the head–stem edge for a cove fillet.')

    create_constant_fillet(
        component, edges, radius,
        name=defaults.SCREW_HEAD_FILLET_NAME)


def _find_circular_edges_near(body, radius_cm, z_cm=None, tol_cm=0.05):
    """Collect circular/arc edges near a radius (and optional Z)."""
    circle_type = adsk.core.Circle3D.classType()
    arc_type = adsk.core.Arc3D.classType()
    found = []
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        geom = edge.geometry
        if not geom:
            continue
        if geom.objectType not in (circle_type, arc_type):
            continue
        if abs(float(geom.radius) - float(radius_cm)) > float(tol_cm):
            continue
        if z_cm is not None:
            try:
                if abs(float(geom.center.z) - float(z_cm)) > float(tol_cm):
                    continue
            except Exception:
                continue
        found.append(edge)
    return found


def _add_hex_head(component, body, stem_diameter_cm, across_flats_cm, head_height_cm):
    """Join a hex head onto the stem end farthest from the origin (Z+ tip)."""
    # Prefer a planar end face whose center is near z = stem length.
    end_face = _find_stem_end_face(body, stem_diameter_cm)
    head_sketch = component.sketches.add(end_face)
    head_sketch.name = defaults.SCREW_HEAD_SKETCH_NAME

    radius = hex_vertex_radius_from_across_flats(across_flats_cm)
    add_regular_polygon(head_sketch, head_sketch.originPoint, radius, 6)

    if head_sketch.profiles.count < 1:
        raise RuntimeError('Hex head sketch has no profile.')

    profile = head_sketch.profiles.item(0)
    best_area = -1.0
    for i in range(head_sketch.profiles.count):
        p = head_sketch.profiles.item(i)
        try:
            area = abs(p.areaProperties().area)
        except Exception:
            area = 0.0
        if area > best_area:
            best_area = area
            profile = p

    create_extrude(
        component,
        profile,
        distance_cm=head_height_cm,
        operation=adsk.fusion.FeatureOperations.JoinFeatureOperation,
        name=defaults.SCREW_HEAD_EXTRUDE_NAME,
        expression=defaults.PARAM_SCREW_HEAD_HEIGHT)


def _find_stem_end_face(body, stem_diameter_cm):
    """Pick a planar circular-ish end face on the stem (prefer +Z)."""
    target_r = float(stem_diameter_cm) * 0.5
    best = None
    best_z = None
    for i in range(body.faces.count):
        face = body.faces.item(i)
        if not face.geometry or face.geometry.objectType != adsk.core.Plane.classType():
            continue
        # Approximate radius from bounding box diagonal / area.
        try:
            props = face.areaProperties(
                adsk.fusion.CalculationAccuracy.MediumCalculationAccuracy)
            area = abs(props.area)
        except Exception:
            continue
        # Circle area ≈ π r^2
        equiv_r = math.sqrt(max(area, 0.0) / math.pi)
        if abs(equiv_r - target_r) > 0.05:
            continue
        z = props.centroid.z
        if best is None or z > best_z:
            best = face
            best_z = z
    if not best:
        # Fallback: any planar face with largest +Z centroid.
        for i in range(body.faces.count):
            face = body.faces.item(i)
            if not face.geometry or face.geometry.objectType != adsk.core.Plane.classType():
                continue
            try:
                z = face.areaProperties().centroid.z
            except Exception:
                continue
            if best is None or z > best_z:
                best = face
                best_z = z
    if not best:
        raise RuntimeError('Cannot find stem end face for hex head.')
    return best
