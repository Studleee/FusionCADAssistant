"""CREATE DIAL — round watch dial with chapter ring and hour indices.

Geometry:
  1. Extrude dial blank (OD × thickness)
  2. Cut center / cannon-pinion hole
  3. Optional raised chapter ring (annular join on top)
  4. Optional 12 hour baton indices (join-extrude)
  5. Optional minute-track construction sketch
"""

import traceback

import adsk.core
import adsk.fusion

from config import defaults
from config.defaults import mm_to_cm
from fusion.components import create_component, get_active_design
from fusion.features import create_extrude, name_first_body
from fusion.parameters import set_user_parameter
from fusion.sketches import create_circle, create_offset_plane, create_sketch_on_plane
from geometry.dial import (
    dial_dims_are_valid,
    hour_index_rects_xy,
    minute_track_ticks_xy,
)

_handlers = []
_preview_error_shown = False


def start(ui):
    cmd_defs = ui.commandDefinitions
    cmd_def = cmd_defs.itemById(defaults.CMD_CREATE_DIAL_ID)
    if cmd_def:
        cmd_def.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(
        defaults.CMD_CREATE_DIAL_ID,
        defaults.CMD_CREATE_DIAL_NAME,
        defaults.CMD_CREATE_DIAL_TOOLTIP,
        '')

    on_created = CreateDialCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)
    return cmd_def


def stop(ui):
    cmd_def = ui.commandDefinitions.itemById(defaults.CMD_CREATE_DIAL_ID)
    if cmd_def:
        cmd_def.deleteMe()


def _add_mm_slider(inputs, input_id, label, value_mm, min_mm, max_mm):
    """Float slider labeled in mm; min/max/value use Fusion database cm."""
    slider = inputs.addFloatSliderCommandInput(
        input_id, label, 'mm',
        mm_to_cm(min_mm), mm_to_cm(max_mm), False)
    if not slider:
        raise RuntimeError('Failed to create slider {!r}.'.format(input_id))
    slider.valueOne = mm_to_cm(value_mm)
    try:
        slider.spinStep = mm_to_cm(0.05)
    except Exception:
        pass
    return slider


def _slider_cm(inputs, input_id):
    return float(inputs.itemById(input_id).valueOne)


def _apply_dial_ui(inputs):
    chapter = inputs.itemById('chapterRing').value
    for input_id in ('chapterWidth', 'chapterHeight'):
        item = inputs.itemById(input_id)
        if item:
            item.isVisible = chapter
            item.isEnabled = chapter

    indices = inputs.itemById('hourIndices').value
    for input_id in (
            'indexLength', 'indexWidth', 'indexHeight', 'indexInset'):
        item = inputs.itemById(input_id)
        if item:
            item.isVisible = indices
            item.isEnabled = indices


class CreateDialCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        global _preview_error_shown
        _preview_error_shown = False
        try:
            cmd = args.command
            cmd.isRepeatable = False
            inputs = cmd.commandInputs

            _add_mm_slider(
                inputs, 'dialDiameter', 'Dial Diameter',
                defaults.DIAL_DIAMETER_MM,
                defaults.DIAL_DIAMETER_MIN_MM,
                defaults.DIAL_DIAMETER_MAX_MM)

            _add_mm_slider(
                inputs, 'dialThickness', 'Thickness',
                defaults.DIAL_THICKNESS_MM,
                defaults.DIAL_THICKNESS_MIN_MM,
                defaults.DIAL_THICKNESS_MAX_MM)

            _add_mm_slider(
                inputs, 'centerHole', 'Center Hole',
                defaults.DIAL_CENTER_HOLE_MM, 0.0, 6.0)

            inputs.addBoolValueInput(
                'chapterRing',
                'Chapter Ring',
                True,
                '',
                defaults.DIAL_CHAPTER_RING)

            _add_mm_slider(
                inputs, 'chapterWidth', 'Chapter Width',
                defaults.DIAL_CHAPTER_WIDTH_MM, 0.4, 4.0)

            _add_mm_slider(
                inputs, 'chapterHeight', 'Chapter Height',
                defaults.DIAL_CHAPTER_HEIGHT_MM, 0.05, 0.8)

            inputs.addBoolValueInput(
                'hourIndices',
                'Hour Indices',
                True,
                '',
                defaults.DIAL_HOUR_INDICES)

            _add_mm_slider(
                inputs, 'indexLength', 'Index Length',
                defaults.DIAL_INDEX_LENGTH_MM, 0.6, 6.0)

            _add_mm_slider(
                inputs, 'indexWidth', 'Index Width',
                defaults.DIAL_INDEX_WIDTH_MM, 0.2, 2.0)

            _add_mm_slider(
                inputs, 'indexHeight', 'Index Height',
                defaults.DIAL_INDEX_HEIGHT_MM, 0.05, 0.8)

            _add_mm_slider(
                inputs, 'indexInset', 'Index Inset',
                defaults.DIAL_INDEX_INSET_MM, 0.2, 4.0)

            inputs.addBoolValueInput(
                'minuteTrack',
                'Minute Track Guides',
                True,
                '',
                defaults.DIAL_MINUTE_TRACK)

            inputs.addBoolValueInput(
                'sketchOnly',
                'Sketch Only',
                True,
                '',
                defaults.DIAL_SKETCH_ONLY)

            _apply_dial_ui(inputs)

            on_preview = CreateDialCommandPreviewHandler()
            cmd.executePreview.add(on_preview)
            _handlers.append(on_preview)

            on_execute = CreateDialCommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = CreateDialCommandValidateHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            on_change = CreateDialCommandInputChangedHandler()
            cmd.inputChanged.add(on_change)
            _handlers.append(on_change)

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface if app else None
            if ui:
                ui.messageBox(
                    'Create Dial dialog failed:\n{}'.format(
                        traceback.format_exc()))


class CreateDialCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            if args.input.id in ('chapterRing', 'hourIndices'):
                _apply_dial_ui(args.inputs)
        except Exception:
            pass


class CreateDialCommandValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args.areInputsValid = _dial_inputs_are_valid(args.inputs)
        except Exception:
            args.areInputsValid = False


class CreateDialCommandPreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        global _preview_error_shown
        try:
            inputs = args.command.commandInputs
            if not _dial_inputs_are_valid(inputs):
                args.isValidResult = False
                return
            _execute_dial_from_inputs(inputs, commit_params=False)
            args.isValidResult = True
        except Exception as exc:
            args.isValidResult = False
            app = adsk.core.Application.get()
            if app:
                try:
                    app.log('Create Dial preview failed: {}'.format(exc))
                except Exception:
                    pass
            if not _preview_error_shown:
                _preview_error_shown = True
                ui = app.userInterface if app else None
                if ui:
                    ui.messageBox(
                        'Create Dial preview failed:\n{}'.format(exc))


class CreateDialCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface if app else None
        try:
            _execute_dial_from_inputs(
                args.command.commandInputs, commit_params=True)
        except Exception as exc:
            if ui:
                ui.messageBox(
                    'Create Dial failed:\n{}\n\n{}'.format(
                        exc, traceback.format_exc()))


def _dial_inputs_are_valid(inputs):
    return dial_dims_are_valid(
        _slider_cm(inputs, 'dialDiameter'),
        _slider_cm(inputs, 'dialThickness'),
        _slider_cm(inputs, 'centerHole'),
        chapter_ring=inputs.itemById('chapterRing').value,
        chapter_width_cm=_slider_cm(inputs, 'chapterWidth'),
        hour_indices=inputs.itemById('hourIndices').value,
        index_length_cm=_slider_cm(inputs, 'indexLength'),
        index_width_cm=_slider_cm(inputs, 'indexWidth'),
        index_inset_cm=_slider_cm(inputs, 'indexInset'))


def _execute_dial_from_inputs(inputs, commit_params=False):
    execute_create_dial(
        diameter_cm=_slider_cm(inputs, 'dialDiameter'),
        thickness_cm=_slider_cm(inputs, 'dialThickness'),
        center_hole_cm=_slider_cm(inputs, 'centerHole'),
        chapter_ring=inputs.itemById('chapterRing').value,
        chapter_width_cm=_slider_cm(inputs, 'chapterWidth'),
        chapter_height_cm=_slider_cm(inputs, 'chapterHeight'),
        hour_indices=inputs.itemById('hourIndices').value,
        index_length_cm=_slider_cm(inputs, 'indexLength'),
        index_width_cm=_slider_cm(inputs, 'indexWidth'),
        index_height_cm=_slider_cm(inputs, 'indexHeight'),
        index_inset_cm=_slider_cm(inputs, 'indexInset'),
        minute_track=inputs.itemById('minuteTrack').value,
        sketch_only=inputs.itemById('sketchOnly').value,
        commit_params=commit_params)


def execute_create_dial(
        diameter_cm,
        thickness_cm,
        center_hole_cm,
        chapter_ring=True,
        chapter_width_cm=None,
        chapter_height_cm=None,
        hour_indices=True,
        index_length_cm=None,
        index_width_cm=None,
        index_height_cm=None,
        index_inset_cm=None,
        minute_track=True,
        sketch_only=False,
        commit_params=True):
    """Build a round watch dial. Sizes in centimeters."""
    if chapter_width_cm is None:
        chapter_width_cm = mm_to_cm(defaults.DIAL_CHAPTER_WIDTH_MM)
    if chapter_height_cm is None:
        chapter_height_cm = mm_to_cm(defaults.DIAL_CHAPTER_HEIGHT_MM)
    if index_length_cm is None:
        index_length_cm = mm_to_cm(defaults.DIAL_INDEX_LENGTH_MM)
    if index_width_cm is None:
        index_width_cm = mm_to_cm(defaults.DIAL_INDEX_WIDTH_MM)
    if index_height_cm is None:
        index_height_cm = mm_to_cm(defaults.DIAL_INDEX_HEIGHT_MM)
    if index_inset_cm is None:
        index_inset_cm = mm_to_cm(defaults.DIAL_INDEX_INSET_MM)

    if not dial_dims_are_valid(
            diameter_cm, thickness_cm, center_hole_cm,
            chapter_ring=chapter_ring, chapter_width_cm=chapter_width_cm,
            hour_indices=hour_indices, index_length_cm=index_length_cm,
            index_width_cm=index_width_cm, index_inset_cm=index_inset_cm):
        raise ValueError('Dial dimensions are invalid.')

    design = get_active_design()
    if commit_params:
        _commit_dial_parameters(
            design, diameter_cm, thickness_cm, center_hole_cm,
            chapter_ring, chapter_width_cm, chapter_height_cm,
            hour_indices, index_length_cm, index_width_cm,
            index_height_cm, index_inset_cm)

    _occ, component = create_component(design, defaults.DIAL_COMPONENT_NAME)
    component.name = 'Dial_{:.1f}'.format(diameter_cm * 10.0)

    ra = float(diameter_cm) * 0.5
    blank_sketch = create_sketch_on_plane(
        component, component.xYConstructionPlane,
        name=defaults.DIAL_BLANK_SKETCH_NAME)
    create_circle(blank_sketch, blank_sketch.originPoint, ra)
    if center_hole_cm > 1e-6:
        create_circle(
            blank_sketch, blank_sketch.originPoint, float(center_hole_cm) * 0.5)

    if sketch_only:
        blank_sketch.isVisible = True
        if hour_indices:
            _sketch_hour_indices(
                component, diameter_cm, index_length_cm, index_width_cm,
                index_inset_cm, z_cm=float(thickness_cm))
        if minute_track:
            _sketch_minute_track(
                component, diameter_cm, index_inset_cm, index_length_cm,
                z_cm=float(thickness_cm))
        _fit_view()
        return component, blank_sketch, None

    if center_hole_cm > 1e-6:
        blank_profile = _annular_profile(blank_sketch)
        if blank_profile is None:
            blank_profile = _largest_profile(blank_sketch)
    else:
        blank_profile = _largest_profile(blank_sketch)
    if blank_profile is None:
        raise RuntimeError('Dial blank sketch has no profile.')

    blank_ext = create_extrude(
        component,
        blank_profile,
        distance_cm=thickness_cm,
        name=defaults.DIAL_BLANK_EXTRUDE_NAME)
    body = name_first_body(blank_ext, defaults.DIAL_BODY_NAME)

    if chapter_ring and chapter_height_cm > 1e-6:
        _add_chapter_ring(
            component, body, diameter_cm, thickness_cm,
            chapter_width_cm, chapter_height_cm)

    if hour_indices and index_height_cm > 1e-6:
        _add_hour_indices(
            component, body, diameter_cm, thickness_cm,
            index_length_cm, index_width_cm, index_height_cm, index_inset_cm)

    if minute_track:
        _sketch_minute_track(
            component, diameter_cm, index_inset_cm, index_length_cm,
            z_cm=float(thickness_cm))

    _fit_view()
    return component, blank_sketch, body


def _add_chapter_ring(component, body, diameter_cm, thickness_cm,
                      chapter_width_cm, chapter_height_cm):
    """Raised annular ring on the dial top face."""
    ra = float(diameter_cm) * 0.5
    ri = ra - float(chapter_width_cm)
    if ri <= 0:
        raise ValueError('Chapter ring width is too large.')

    plane = create_offset_plane(component, thickness_cm)
    sketch = create_sketch_on_plane(
        component, plane, name=defaults.DIAL_CHAPTER_SKETCH_NAME)
    create_circle(sketch, sketch.originPoint, ra)
    create_circle(sketch, sketch.originPoint, ri)
    profile = _annular_profile(sketch)
    if profile is None:
        raise RuntimeError('Chapter ring sketch has no annular profile.')

    create_extrude(
        component,
        profile,
        distance_cm=chapter_height_cm,
        operation=adsk.fusion.FeatureOperations.JoinFeatureOperation,
        name=defaults.DIAL_CHAPTER_EXTRUDE_NAME,
        participant_bodies=[body])
    sketch.isVisible = False


def _add_hour_indices(component, body, diameter_cm, thickness_cm,
                      index_length_cm, index_width_cm, index_height_cm,
                      index_inset_cm):
    """Twelve raised baton hour markers on the dial face."""
    plane = create_offset_plane(component, thickness_cm)
    sketch = create_sketch_on_plane(
        component, plane, name=defaults.DIAL_INDEX_SKETCH_NAME)
    _draw_index_rects(
        sketch, diameter_cm, index_length_cm, index_width_cm, index_inset_cm)

    if sketch.profiles.count < 1:
        raise RuntimeError('Hour index sketch has no profiles.')

    profiles = adsk.core.ObjectCollection.create()
    for i in range(sketch.profiles.count):
        profiles.add(sketch.profiles.item(i))

    extrudes = component.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    if not ext_input:
        raise RuntimeError('Failed to create hour-index extrude input.')
    ext_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(float(index_height_cm)))
    ext_input.isSolid = True
    ext_input.participantBodies = [body]
    feature = extrudes.add(ext_input)
    if not feature:
        raise RuntimeError('Failed to extrude hour indices.')
    feature.name = defaults.DIAL_INDEX_EXTRUDE_NAME
    sketch.isVisible = False


def _sketch_hour_indices(component, diameter_cm, index_length_cm, index_width_cm,
                         index_inset_cm, z_cm):
    plane = create_offset_plane(component, z_cm)
    sketch = create_sketch_on_plane(
        component, plane, name=defaults.DIAL_INDEX_SKETCH_NAME)
    _draw_index_rects(
        sketch, diameter_cm, index_length_cm, index_width_cm, index_inset_cm)
    sketch.isVisible = True


def _draw_index_rects(sketch, diameter_cm, index_length_cm, index_width_cm,
                      index_inset_cm):
    rects = hour_index_rects_xy(
        diameter_cm, index_length_cm, index_width_cm, index_inset_cm)
    lines = sketch.sketchCurves.sketchLines
    for corners in rects:
        pts = [
            adsk.core.Point3D.create(float(x), float(y), 0.0)
            for x, y in corners
        ]
        for i in range(4):
            line = lines.addByTwoPoints(pts[i], pts[(i + 1) % 4])
            if not line:
                raise RuntimeError('Failed to sketch an hour index.')


def _sketch_minute_track(component, diameter_cm, index_inset_cm, index_length_cm,
                         z_cm):
    """Construction minute track (60 radial ticks) on the dial face."""
    plane = create_offset_plane(component, z_cm)
    sketch = create_sketch_on_plane(
        component, plane, name=defaults.DIAL_TRACK_SKETCH_NAME)
    short = max(float(index_length_cm) * 0.35, mm_to_cm(0.4))
    long = max(float(index_length_cm) * 0.7, short * 1.5)
    ticks = minute_track_ticks_xy(
        diameter_cm, index_inset_cm * 0.35, short, hour_length_cm=long)
    lines = sketch.sketchCurves.sketchLines
    for (x0, y0), (x1, y1) in ticks:
        line = lines.addByTwoPoints(
            adsk.core.Point3D.create(float(x0), float(y0), 0.0),
            adsk.core.Point3D.create(float(x1), float(y1), 0.0))
        if line:
            try:
                line.isConstruction = True
            except Exception:
                pass
    sketch.isVisible = True


def _largest_profile(sketch):
    """Largest profile in a sketch (any loop count)."""
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


def _annular_profile(sketch):
    """Largest two-loop profile (ring)."""
    best = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        candidate = sketch.profiles.item(i)
        if candidate.profileLoops.count < 2:
            continue
        try:
            area = abs(candidate.areaProperties().area)
        except Exception:
            continue
        if area > best_area:
            best_area = area
            best = candidate
    return best


def _commit_dial_parameters(
        design, diameter_cm, thickness_cm, center_hole_cm,
        chapter_ring, chapter_width_cm, chapter_height_cm,
        hour_indices, index_length_cm, index_width_cm,
        index_height_cm, index_inset_cm):
    set_user_parameter(
        design, defaults.PARAM_DIAL_DIAMETER, diameter_cm,
        comment='CREATE DIAL outer diameter')
    set_user_parameter(
        design, defaults.PARAM_DIAL_THICKNESS, thickness_cm,
        comment='CREATE DIAL thickness')
    set_user_parameter(
        design, defaults.PARAM_DIAL_CENTER_HOLE, center_hole_cm,
        comment='CREATE DIAL center hole')
    if chapter_ring:
        set_user_parameter(
            design, defaults.PARAM_DIAL_CHAPTER_WIDTH, chapter_width_cm,
            comment='CREATE DIAL chapter ring width')
        set_user_parameter(
            design, defaults.PARAM_DIAL_CHAPTER_HEIGHT, chapter_height_cm,
            comment='CREATE DIAL chapter ring height')
    if hour_indices:
        set_user_parameter(
            design, defaults.PARAM_DIAL_INDEX_LENGTH, index_length_cm,
            comment='CREATE DIAL hour index length')
        set_user_parameter(
            design, defaults.PARAM_DIAL_INDEX_WIDTH, index_width_cm,
            comment='CREATE DIAL hour index width')
        set_user_parameter(
            design, defaults.PARAM_DIAL_INDEX_HEIGHT, index_height_cm,
            comment='CREATE DIAL hour index height')
        set_user_parameter(
            design, defaults.PARAM_DIAL_INDEX_INSET, index_inset_cm,
            comment='CREATE DIAL hour index inset from OD')


def _fit_view():
    try:
        app = adsk.core.Application.get()
        viewport = app.activeViewport if app else None
        if viewport:
            viewport.fit()
    except Exception:
        pass
