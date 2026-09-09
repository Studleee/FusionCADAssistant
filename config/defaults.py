"""Default values for CAD Assistant commands.

Fusion's internal unit is centimeters. Dialogs should present millimeters
to the user; convert with mm_to_cm / cm_to_mm when calling the API.
"""

# --- Unit helpers -----------------------------------------------------------

def mm_to_cm(value_mm):
    """Convert millimeters to Fusion internal centimeters."""
    return float(value_mm) / 10.0


def cm_to_mm(value_cm):
    """Convert Fusion internal centimeters to millimeters."""
    return float(value_cm) * 10.0


# --- UI IDs -----------------------------------------------------------------

ADDIN_ID = 'FusionCADAssistant'
PANEL_ID = 'CADAssistantPanel'
PANEL_NAME = 'CAD ASSISTANT'
WORKSPACE_ID = 'FusionSolidEnvironment'
TAB_ID = 'SolidTab'

CMD_CREATE_SCREW_ID = 'CADAssistant_CreateScrew'
CMD_CREATE_SCREW_NAME = 'Create Screw'
CMD_CREATE_SCREW_TOOLTIP = (
    'Create a parametric metric screw: hex or flathead; squared, cove, or '
    'countersunk underside; set stem/head size; Fusion thread.'
)

# --- CREATE SCREW defaults (user-facing mm) ---------------------------------

# designation, major_mm, pitch_mm, hex_af_mm, hex_h_mm,
# flat_head_dia_mm, flat_head_h_mm, stem_length_mm
# Watch / small sizes first; larger ISO sizes follow.
SCREW_SIZE_PRESETS = (
    # Typical movement / bridge / dial sizes (modeling defaults, not a catalog)
    ('M0.8x0.2', 0.8, 0.2, 1.5, 0.5, 1.4, 0.30, 1.8),
    ('M1x0.25', 1.0, 0.25, 2.0, 0.6, 1.8, 0.40, 2.2),
    ('M1.2x0.25', 1.2, 0.25, 2.5, 0.7, 2.2, 0.50, 2.5),
    ('M1.4x0.3', 1.4, 0.3, 2.8, 0.8, 2.5, 0.55, 3.0),
    ('M1.6x0.35', 1.6, 0.35, 3.2, 0.9, 3.0, 0.65, 3.5),
    ('M2x0.4', 2.0, 0.4, 4.0, 1.2, 3.8, 0.80, 4.0),
    ('M3x0.5', 3.0, 0.5, 5.5, 2.0, 5.5, 1.65, 8.0),
    ('M4x0.7', 4.0, 0.7, 7.0, 2.8, 8.4, 2.2, 12.0),
    ('M5x0.8', 5.0, 0.8, 8.0, 3.5, 9.2, 2.5, 16.0),
    ('M6x1', 6.0, 1.0, 10.0, 4.0, 11.0, 3.0, 20.0),
    ('M8x1.25', 8.0, 1.25, 13.0, 5.3, 14.5, 4.0, 25.0),
    ('M10x1.5', 10.0, 1.5, 17.0, 6.4, 18.3, 5.0, 30.0),
)

SCREW_HEAD_NONE = 'None'
SCREW_HEAD_HEX = 'Hex'
SCREW_HEAD_FLAT = 'Flathead'
SCREW_HEAD_TRI_SLOT = 'Tri-Slot'
SCREW_DEFAULT_HEAD_STYLE = SCREW_HEAD_FLAT

SCREW_SHAPE_SQUARED = 'Squared'
SCREW_SHAPE_COVE = 'Cove'
SCREW_SHAPE_COUNTERSUNK = 'Countersunk'
SCREW_DEFAULT_HEAD_SHAPE = SCREW_SHAPE_SQUARED

# Default toward a common small movement / bridge screw
SCREW_DEFAULT_DESIGNATION = 'M1.2x0.25'
SCREW_LENGTH_MM = 2.5
SCREW_THREAD_LENGTH_MM = 2.0
SCREW_FULL_THREAD = True
SCREW_MODELED = False  # cosmetic thread by default (faster; better at tiny sizes)
SCREW_REVERSING = False  # left-hand thread + triple drive slots
SCREW_THREAD_TYPE = 'ISO Metric profile'
SCREW_THREAD_CLASS_EXTERNAL = '6g'

# Drive slot (screwdriver kerf) — fractions of head size when auto-seeding
SCREW_DRIVE_SLOT = True
SCREW_SLOT_WIDTH_FRACTION = 0.14   # of head width
SCREW_SLOT_DEPTH_FRACTION = 0.55   # of head length
SCREW_SLOT_MIN_WIDTH_MM = 0.12
SCREW_SLOT_MIN_DEPTH_MM = 0.10
SCREW_REVERSING_SLOT_COUNT = 3
# Tri-Slot head: radial kerfs stop short of center (solid hub).
SCREW_TRI_SLOT_COUNT = 3
SCREW_TRI_SLOT_HUB_FRACTION = 0.30  # of head radius

SCREW_COMPONENT_NAME = 'Screw'
SCREW_SHANK_SKETCH_NAME = 'ScrewShankSketch'
SCREW_HEAD_SKETCH_NAME = 'ScrewHeadSketch'
SCREW_PROFILE_SKETCH_NAME = 'ScrewProfileSketch'
SCREW_SLOT_SKETCH_NAME = 'ScrewSlotSketch'
SCREW_BODY_NAME = 'ScrewBody'
SCREW_SHANK_EXTRUDE_NAME = 'ScrewShank'
SCREW_HEAD_EXTRUDE_NAME = 'ScrewHead'
SCREW_REVOLVE_NAME = 'ScrewRevolve'
SCREW_HEAD_FILLET_NAME = 'ScrewHeadCove'
SCREW_SLOT_CUT_NAME = 'ScrewDriveSlot'
SCREW_THREAD_NAME = 'ScrewThread'

PARAM_SCREW_MAJOR_DIAMETER = 'screwMajorDiameter'
PARAM_SCREW_STEM_DIAMETER = 'screwStemDiameter'
PARAM_SCREW_LENGTH = 'screwLength'
PARAM_SCREW_THREAD_LENGTH = 'screwThreadLength'
PARAM_SCREW_HEAD_WIDTH = 'screwHeadWidth'
PARAM_SCREW_HEAD_HEIGHT = 'screwHeadHeight'
PARAM_SCREW_SLOT_WIDTH = 'screwSlotWidth'
PARAM_SCREW_SLOT_DEPTH = 'screwSlotDepth'
PARAM_SCREW_HEX_AF = 'screwHexAcrossFlats'  # alias kept for older timelines


def screw_preset_by_designation(designation):
    """Return preset tuple or None.

    (designation, major_mm, pitch_mm, hex_af_mm, hex_h_mm,
     flat_head_dia_mm, flat_head_h_mm, stem_length_mm)
    """
    for preset in SCREW_SIZE_PRESETS:
        if preset[0] == designation:
            return preset
    return None


def screw_head_dims_mm(preset, head_style):
    """Suggested (head_width_mm, head_height_mm) for a preset + head style."""
    if not preset:
        return 2.2, 0.5
    _des, _maj, _pitch, hex_af, hex_h, flat_dk, flat_k, _stem_len = preset
    if head_style == SCREW_HEAD_FLAT:
        return flat_dk, flat_k
    if head_style == SCREW_HEAD_TRI_SLOT:
        return flat_dk, flat_k
    if head_style == SCREW_HEAD_HEX:
        return hex_af, hex_h
    return hex_af, hex_h


def screw_stem_length_mm(preset):
    """Suggested stem length (mm) for a preset."""
    if not preset:
        return SCREW_LENGTH_MM
    return float(preset[7])


def screw_slot_dims_mm(head_width_mm, head_length_mm):
    """Suggested (slot_width_mm, slot_depth_mm) from head size."""
    width = max(
        float(head_width_mm) * SCREW_SLOT_WIDTH_FRACTION,
        SCREW_SLOT_MIN_WIDTH_MM)
    depth = max(
        float(head_length_mm) * SCREW_SLOT_DEPTH_FRACTION,
        SCREW_SLOT_MIN_DEPTH_MM)
    # Keep a little solid under the slot floor.
    depth = min(depth, float(head_length_mm) * 0.85)
    return width, depth


def screw_matching_thread_designation(stem_diameter_cm, preferred=None, tol_mm=0.05):
    """Return an ISO designation whose major Ø matches the stem, or None.

    Fusion's Thread feature requires the cylinder diameter to match the
    designation. Custom stem diameters still model; they just skip threading
    when nothing is within tol_mm.
    """
    stem_mm = float(stem_diameter_cm) * 10.0
    if preferred:
        preset = screw_preset_by_designation(preferred)
        if preset and abs(float(preset[1]) - stem_mm) <= float(tol_mm):
            return preferred

    best = None
    best_err = None
    for preset in SCREW_SIZE_PRESETS:
        err = abs(float(preset[1]) - stem_mm)
        if err <= float(tol_mm) and (best_err is None or err < best_err):
            best = preset[0]
            best_err = err
    return best


CMD_CREATE_JEWEL_ID = 'CADAssistant_CreateJewel'
CMD_CREATE_JEWEL_NAME = 'Create Jewel'
CMD_CREATE_JEWEL_TOOLTIP = (
    'Create a watch jewel blank: hole jewel or cap jewel with optional oil sink. '
    'Parametric sketches and extrudes; Sketch Only drafts without a solid.'
)

# --- CREATE JEWEL defaults (user-facing mm) ---------------------------------
# Typical small-movement hole jewel proportions (modeling defaults, not a catalog).

JEWEL_TYPE_HOLE = 'Hole Jewel'
JEWEL_TYPE_CAP = 'Cap Jewel'
JEWEL_DEFAULT_TYPE = JEWEL_TYPE_HOLE

JEWEL_OUTER_DIAMETER_MM = 1.50
JEWEL_HOLE_DIAMETER_MM = 0.20
JEWEL_THICKNESS_MM = 0.40
JEWEL_OIL_SINK = True
JEWEL_OIL_SINK_DIAMETER_MM = 0.70
JEWEL_OIL_SINK_DEPTH_MM = 0.12
JEWEL_SKETCH_ONLY = False

JEWEL_COMPONENT_NAME_HOLE = 'HoleJewel'
JEWEL_COMPONENT_NAME_CAP = 'CapJewel'
JEWEL_SKETCH_NAME = 'JewelSketch'
JEWEL_OIL_SINK_SKETCH_NAME = 'JewelOilSinkSketch'
JEWEL_BODY_NAME = 'JewelBody'
JEWEL_EXTRUDE_NAME = 'JewelExtrude'
JEWEL_OIL_SINK_CUT_NAME = 'JewelOilSink'

PARAM_JEWEL_OUTER_DIAMETER = 'jewelOuterDiameter'
PARAM_JEWEL_HOLE_DIAMETER = 'jewelHoleDiameter'
PARAM_JEWEL_THICKNESS = 'jewelThickness'
PARAM_JEWEL_OIL_SINK_DIAMETER = 'jewelOilSinkDiameter'
PARAM_JEWEL_OIL_SINK_DEPTH = 'jewelOilSinkDepth'

CMD_CREATE_PIVOT_ID = 'CADAssistant_CreatePivot'
CMD_CREATE_PIVOT_NAME = 'Create Pivot'
CMD_CREATE_PIVOT_TOOLTIP = (
    'Create a cylindrical watch pivot blank with optional slight domed ends. '
    'Set length (barrel) and width (diameter). Sketch Only drafts the profile.'
)

# --- CREATE PIVOT defaults (user-facing mm) ---------------------------------
# Typical small-movement pivot proportions (modeling defaults).

PIVOT_LENGTH_MM = 1.00
PIVOT_WIDTH_MM = 0.15   # diameter
PIVOT_DOMED_ENDS = True
PIVOT_SKETCH_ONLY = False

PIVOT_COMPONENT_NAME = 'Pivot'
PIVOT_SKETCH_NAME = 'PivotSketch'
PIVOT_BODY_NAME = 'PivotBody'
PIVOT_REVOLVE_NAME = 'PivotRevolve'
PIVOT_EXTRUDE_NAME = 'PivotExtrude'  # legacy name kept for older timelines

PARAM_PIVOT_LENGTH = 'pivotLength'
PARAM_PIVOT_WIDTH = 'pivotWidth'
PARAM_PIVOT_DOME_HEIGHT = 'pivotDomeHeight'

CMD_CREATE_HAIRSPRING_ID = 'CADAssistant_CreateHairspring'
CMD_CREATE_HAIRSPRING_NAME = 'Create Hairspring'
CMD_CREATE_HAIRSPRING_TOOLTIP = (
    'Create a flat Archimedean hairspring: spiral centerline sketch and optional '
    'extruded strip body. Sketch Only drafts the centerline without a solid.'
)

# --- CREATE HAIRSPRING defaults (user-facing mm) ----------------------------

HAIRSPRING_OUTER_DIAMETER_MM = 10.0
HAIRSPRING_INNER_DIAMETER_MM = 1.2
HAIRSPRING_TURNS = 12.5
HAIRSPRING_STRIP_WIDTH_MM = 0.10
HAIRSPRING_STRIP_THICKNESS_MM = 0.04
HAIRSPRING_HANDEDNESS = 'CCW'  # CCW or CW
HAIRSPRING_SAMPLES_PER_TURN = 16
HAIRSPRING_SKETCH_ONLY = False

HAIRSPRING_COMPONENT_NAME = 'Hairspring'
HAIRSPRING_CENTERLINE_SKETCH_NAME = 'HairspringCenterline'
HAIRSPRING_PROFILE_SKETCH_NAME = 'HairspringProfile'
HAIRSPRING_BODY_NAME = 'HairspringBody'
HAIRSPRING_EXTRUDE_NAME = 'HairspringExtrude'

PARAM_HAIRSPRING_OUTER_DIAMETER = 'hairspringOuterDiameter'
PARAM_HAIRSPRING_INNER_DIAMETER = 'hairspringInnerDiameter'
PARAM_HAIRSPRING_TURNS = 'hairspringTurns'
PARAM_HAIRSPRING_STRIP_WIDTH = 'hairspringStripWidth'
PARAM_HAIRSPRING_STRIP_THICKNESS = 'hairspringStripThickness'

CMD_CREATE_MAINSPRING_ID = 'CADAssistant_CreateMainspring'
CMD_CREATE_MAINSPRING_NAME = 'Create Mainspring'
CMD_CREATE_MAINSPRING_TOOLTIP = (
    'Create a flat Archimedean mainspring blank for a barrel. '
    'Swap Clockwise / Counterclockwise winding direction. '
    'Sketch Only drafts the centerline without a solid.'
)

# --- CREATE MAINSPRING defaults (user-facing mm) ----------------------------
# Modeling blank sized for a small barrel — not a catalog spring.

MAINSPRING_OUTER_DIAMETER_MM = 12.0
MAINSPRING_INNER_DIAMETER_MM = 3.0
MAINSPRING_TURNS = 7.0
MAINSPRING_BLADE_THICKNESS_MM = 0.15   # in-plane strip width
MAINSPRING_SPRING_HEIGHT_MM = 1.20     # extrude (axial height in barrel)
MAINSPRING_HANDEDNESS = 'CW'           # CW or CCW — user-swappable
MAINSPRING_SAMPLES_PER_TURN = 16
MAINSPRING_SKETCH_ONLY = False

MAINSPRING_COMPONENT_NAME = 'Mainspring'
MAINSPRING_CENTERLINE_SKETCH_NAME = 'MainspringCenterline'
MAINSPRING_PROFILE_SKETCH_NAME = 'MainspringProfile'
MAINSPRING_BODY_NAME = 'MainspringBody'
MAINSPRING_EXTRUDE_NAME = 'MainspringExtrude'

PARAM_MAINSPRING_OUTER_DIAMETER = 'mainspringOuterDiameter'
PARAM_MAINSPRING_INNER_DIAMETER = 'mainspringInnerDiameter'
PARAM_MAINSPRING_TURNS = 'mainspringTurns'
PARAM_MAINSPRING_BLADE_THICKNESS = 'mainspringBladeThickness'
PARAM_MAINSPRING_SPRING_HEIGHT = 'mainspringSpringHeight'

CMD_CREATE_WHEEL_ID = 'CADAssistant_CreateWheel'
CMD_CREATE_WHEEL_NAME = 'Create Wheel'
CMD_CREATE_WHEEL_TOOLTIP = (
    'Create a spur wheel from outside diameter and tooth count. '
    'Choose Involute or Cycloidal (watch-style) teeth. Optional bore and face width.'
)

# --- CREATE WHEEL defaults (user-facing mm) ---------------------------------

WHEEL_PROFILE_INVOLUTE = 'Involute'
WHEEL_PROFILE_CYCLOIDAL = 'Cycloidal'
WHEEL_DEFAULT_PROFILE = WHEEL_PROFILE_CYCLOIDAL

WHEEL_OUTSIDE_DIAMETER_MM = 20.0
WHEEL_TEETH = 30
WHEEL_FACE_WIDTH_MM = 1.0
WHEEL_BORE_DIAMETER_MM = 3.0
WHEEL_PRESSURE_ANGLE_DEG = 20.0
WHEEL_SKETCH_ONLY = False

WHEEL_COMPONENT_NAME = 'Wheel'
WHEEL_SKETCH_NAME = 'WheelSketch'
WHEEL_BODY_NAME = 'WheelBody'
WHEEL_EXTRUDE_NAME = 'WheelExtrude'

PARAM_WHEEL_OUTSIDE_DIAMETER = 'wheelOutsideDiameter'
PARAM_WHEEL_TEETH = 'wheelTeeth'
PARAM_WHEEL_FACE_WIDTH = 'wheelFaceWidth'
PARAM_WHEEL_BORE_DIAMETER = 'wheelBoreDiameter'
PARAM_WHEEL_PRESSURE_ANGLE = 'wheelPressureAngle'
PARAM_WHEEL_MODULE = 'wheelModule'

CMD_CREATE_RING_GEAR_ID = 'CADAssistant_CreateRingGear'
CMD_CREATE_RING_GEAR_NAME = 'Create Ring Gear'
CMD_CREATE_RING_GEAR_TOOLTIP = (
    'Create a differential-style crown ring gear: teeth stand on the face '
    '(90° to the axis). Set OD, ID, tooth count, ring thickness, and tooth height.'
)

# --- CREATE RING GEAR defaults (user-facing mm) -----------------------------

RING_GEAR_PROFILE_INVOLUTE = 'Involute'
RING_GEAR_PROFILE_CYCLOIDAL = 'Cycloidal'
RING_GEAR_DEFAULT_PROFILE = RING_GEAR_PROFILE_CYCLOIDAL

RING_GEAR_OUTSIDE_DIAMETER_MM = 40.0
RING_GEAR_INNER_DIAMETER_MM = 24.0
RING_GEAR_TEETH = 36
RING_GEAR_RING_THICKNESS_MM = 3.0
RING_GEAR_TOOTH_HEIGHT_MM = 2.0
RING_GEAR_PRESSURE_ANGLE_DEG = 20.0
RING_GEAR_SKETCH_ONLY = False

RING_GEAR_COMPONENT_NAME = 'RingGear'
RING_GEAR_BLANK_SKETCH_NAME = 'RingGearBlankSketch'
RING_GEAR_TOOTH_SKETCH_NAME = 'RingGearToothSketch'
RING_GEAR_TOOTH_ID_SKETCH_NAME = 'RingGearToothIdSketch'
RING_GEAR_SKETCH_NAME = 'RingGearSketch'  # legacy
RING_GEAR_BODY_NAME = 'RingGearBody'
RING_GEAR_BLANK_EXTRUDE_NAME = 'RingGearBlank'
RING_GEAR_TOOTH_EXTRUDE_NAME = 'RingGearTooth'
RING_GEAR_TOOTH_COMBINE_NAME = 'RingGearToothJoin'
RING_GEAR_TOOTH_PATTERN_NAME = 'RingGearToothPattern'
RING_GEAR_ROOT_FILLET_NAME = 'RingGearRootFillet'
RING_GEAR_EXTRUDE_NAME = 'RingGearExtrude'  # legacy

PARAM_RING_GEAR_OUTSIDE_DIAMETER = 'ringGearOutsideDiameter'
PARAM_RING_GEAR_INNER_DIAMETER = 'ringGearInnerDiameter'
PARAM_RING_GEAR_TEETH = 'ringGearTeeth'
PARAM_RING_GEAR_RING_THICKNESS = 'ringGearRingThickness'
PARAM_RING_GEAR_TOOTH_HEIGHT = 'ringGearToothHeight'
PARAM_RING_GEAR_FACE_WIDTH = 'ringGearFaceWidth'  # legacy alias
PARAM_RING_GEAR_PRESSURE_ANGLE = 'ringGearPressureAngle'
PARAM_RING_GEAR_MODULE = 'ringGearModule'

CMD_CREATE_PINION_ID = 'CADAssistant_CreatePinion'
CMD_CREATE_PINION_NAME = 'Create Pinion'
CMD_CREATE_PINION_TOOLTIP = (
    'Create a watch pinion by outside diameter, module, or matched wheel module. '
    'Choose Involute or Cycloidal leaves to pair with Create Wheel.'
)

# --- CREATE PINION defaults (user-facing mm) --------------------------------

PINION_SIZE_BY_OD = 'By Outside Diameter'
PINION_SIZE_BY_MODULE = 'By Module'
PINION_SIZE_MATCH_WHEEL = 'Match Wheel Module'
PINION_DEFAULT_SIZE_MODE = PINION_SIZE_BY_OD

PINION_PROFILE_INVOLUTE = 'Involute'
PINION_PROFILE_CYCLOIDAL = 'Cycloidal'
PINION_DEFAULT_PROFILE = PINION_PROFILE_CYCLOIDAL

PINION_OUTSIDE_DIAMETER_MM = 4.0
PINION_LEAVES = 8
PINION_MODULE_MM = 0.25
PINION_FACE_WIDTH_MM = 1.5
PINION_BORE_DIAMETER_MM = 0.8
PINION_PRESSURE_ANGLE_DEG = 20.0
PINION_SKETCH_ONLY = False

# Defaults used when matching a wheel (example: 20 mm / 30T → m ≈ 0.625 mm)
PINION_MATCH_WHEEL_OD_MM = 20.0
PINION_MATCH_WHEEL_TEETH = 30

PINION_COMPONENT_NAME = 'Pinion'
PINION_SKETCH_NAME = 'PinionSketch'
PINION_BODY_NAME = 'PinionBody'
PINION_EXTRUDE_NAME = 'PinionExtrude'

PARAM_PINION_OUTSIDE_DIAMETER = 'pinionOutsideDiameter'
PARAM_PINION_LEAVES = 'pinionLeaves'
PARAM_PINION_FACE_WIDTH = 'pinionFaceWidth'
PARAM_PINION_BORE_DIAMETER = 'pinionBoreDiameter'
PARAM_PINION_PRESSURE_ANGLE = 'pinionPressureAngle'
PARAM_PINION_MODULE = 'pinionModule'

CMD_CREATE_WATCH_CASE_ID = 'CADAssistant_CreateWatchCase'
CMD_CREATE_WATCH_CASE_NAME = 'Create Watch Case'
CMD_CREATE_WATCH_CASE_TOOLTIP = (
    'Create a round watch case from an adjustable revolved profile, '
    'with optional strap lugs. Sliders control diameter, height, bezel, '
    'crystal, cavity, caseback, and lug size.'
)

# --- CREATE WATCH CASE defaults (user-facing mm) ---------------------------

WATCH_CASE_DIAMETER_MM = 40.0
WATCH_CASE_HEIGHT_MM = 11.0
WATCH_CASE_CRYSTAL_DIAMETER_MM = 34.0
WATCH_CASE_CAVITY_DIAMETER_MM = 36.0
WATCH_CASE_BEZEL_HEIGHT_MM = 2.2
WATCH_CASE_BEZEL_INSET_MM = 0.8
WATCH_CASE_CASEBACK_HEIGHT_MM = 2.0
WATCH_CASE_CASEBACK_INSET_MM = 1.2
WATCH_CASE_CASEBACK_OPENING_MM = 32.0
WATCH_CASE_EDGE_SOFTNESS = 0.35  # 0 = sharp, 1 = soft outer corners
WATCH_CASE_ADD_LUGS = True
WATCH_CASE_LUG_LENGTH_MM = 4.5
WATCH_CASE_LUG_WIDTH_MM = 3.0
WATCH_CASE_LUG_GAP_MM = 20.0
WATCH_CASE_LUG_THICKNESS_MM = 3.5
WATCH_CASE_SKETCH_ONLY = False

WATCH_CASE_DIAMETER_MIN_MM = 20.0
WATCH_CASE_DIAMETER_MAX_MM = 55.0
WATCH_CASE_HEIGHT_MIN_MM = 5.0
WATCH_CASE_HEIGHT_MAX_MM = 18.0
WATCH_CASE_SOFTNESS_MIN = 0.0
WATCH_CASE_SOFTNESS_MAX = 1.0

WATCH_CASE_COMPONENT_NAME = 'WatchCase'
WATCH_CASE_PROFILE_SKETCH_NAME = 'WatchCaseProfileSketch'
WATCH_CASE_LUG_SKETCH_NAME = 'WatchCaseLugSketch'
WATCH_CASE_BODY_NAME = 'WatchCaseBody'
WATCH_CASE_REVOLVE_NAME = 'WatchCaseRevolve'
WATCH_CASE_LUG_EXTRUDE_NAME = 'WatchCaseLugs'

PARAM_WATCH_CASE_DIAMETER = 'watchCaseDiameter'
PARAM_WATCH_CASE_HEIGHT = 'watchCaseHeight'
PARAM_WATCH_CASE_CRYSTAL_DIAMETER = 'watchCaseCrystalDiameter'
PARAM_WATCH_CASE_CAVITY_DIAMETER = 'watchCaseCavityDiameter'
PARAM_WATCH_CASE_BEZEL_HEIGHT = 'watchCaseBezelHeight'
PARAM_WATCH_CASE_BEZEL_INSET = 'watchCaseBezelInset'
PARAM_WATCH_CASE_CASEBACK_HEIGHT = 'watchCaseCasebackHeight'
PARAM_WATCH_CASE_CASEBACK_INSET = 'watchCaseCasebackInset'
PARAM_WATCH_CASE_CASEBACK_OPENING = 'watchCaseCasebackOpening'
PARAM_WATCH_CASE_EDGE_SOFTNESS = 'watchCaseEdgeSoftness'
PARAM_WATCH_CASE_LUG_LENGTH = 'watchCaseLugLength'
PARAM_WATCH_CASE_LUG_WIDTH = 'watchCaseLugWidth'
PARAM_WATCH_CASE_LUG_GAP = 'watchCaseLugGap'
PARAM_WATCH_CASE_LUG_THICKNESS = 'watchCaseLugThickness'

CMD_CREATE_DIAL_ID = 'CADAssistant_CreateDial'
CMD_CREATE_DIAL_NAME = 'Create Dial'
CMD_CREATE_DIAL_TOOLTIP = (
    'Create a round watch dial with adjustable diameter, thickness, center '
    'hole, optional chapter ring, and hour indices.'
)

# --- CREATE DIAL defaults (user-facing mm) ---------------------------------

DIAL_DIAMETER_MM = 28.5
DIAL_THICKNESS_MM = 0.40
DIAL_CENTER_HOLE_MM = 1.20
DIAL_CHAPTER_RING = True
DIAL_CHAPTER_WIDTH_MM = 1.60
DIAL_CHAPTER_HEIGHT_MM = 0.15
DIAL_HOUR_INDICES = True
DIAL_INDEX_LENGTH_MM = 2.20
DIAL_INDEX_WIDTH_MM = 0.55
DIAL_INDEX_HEIGHT_MM = 0.20
DIAL_INDEX_INSET_MM = 0.80  # from outer edge to tip of index
DIAL_MINUTE_TRACK = True
DIAL_SKETCH_ONLY = False

DIAL_DIAMETER_MIN_MM = 12.0
DIAL_DIAMETER_MAX_MM = 45.0
DIAL_THICKNESS_MIN_MM = 0.15
DIAL_THICKNESS_MAX_MM = 1.50

DIAL_COMPONENT_NAME = 'Dial'
DIAL_BLANK_SKETCH_NAME = 'DialBlankSketch'
DIAL_CHAPTER_SKETCH_NAME = 'DialChapterSketch'
DIAL_INDEX_SKETCH_NAME = 'DialIndexSketch'
DIAL_TRACK_SKETCH_NAME = 'DialMinuteTrackSketch'
DIAL_BODY_NAME = 'DialBody'
DIAL_BLANK_EXTRUDE_NAME = 'DialBlank'
DIAL_HOLE_CUT_NAME = 'DialCenterHole'
DIAL_CHAPTER_EXTRUDE_NAME = 'DialChapterRing'
DIAL_INDEX_EXTRUDE_NAME = 'DialHourIndices'

PARAM_DIAL_DIAMETER = 'dialDiameter'
PARAM_DIAL_THICKNESS = 'dialThickness'
PARAM_DIAL_CENTER_HOLE = 'dialCenterHole'
PARAM_DIAL_CHAPTER_WIDTH = 'dialChapterWidth'
PARAM_DIAL_CHAPTER_HEIGHT = 'dialChapterHeight'
PARAM_DIAL_INDEX_LENGTH = 'dialIndexLength'
PARAM_DIAL_INDEX_WIDTH = 'dialIndexWidth'
PARAM_DIAL_INDEX_HEIGHT = 'dialIndexHeight'
PARAM_DIAL_INDEX_INSET = 'dialIndexInset'

CMD_FINISH_GUIDES_ID = 'CADAssistant_FinishGuides'
CMD_FINISH_GUIDES_NAME = 'Finish Guides'
CMD_FINISH_GUIDES_TOOLTIP = (
    'Lay out decorative finish guides on a planar face: Geneva stripes, '
    'perlage, circular graining, sunburst, or brushing lines (construction only).'
)

# --- FINISH GUIDES defaults (user-facing mm) --------------------------------

FINISH_GENEVA = 'Geneva Stripes'
FINISH_PERLAGE = 'Perlage'
FINISH_CIRCULAR = 'Circular Graining'
FINISH_SUNBURST = 'Sunburst'
FINISH_BRUSHING = 'Brushing Guides'
FINISH_DEFAULT_TYPE = FINISH_GENEVA

FINISH_SPACING_MM = 1.2
FINISH_MARGIN_MM = 0.5
FINISH_ANGLE_DEG = 0.0
FINISH_PERLAGE_RADIUS_MM = 0.6
FINISH_PERLAGE_HEX = True
FINISH_SUNBURST_RAYS = 36
FINISH_INNER_RADIUS_MM = 0.5

CMD_ANGLAGE_ID = 'CADAssistant_Anglage'
CMD_ANGLAGE_NAME = 'Anglage'
CMD_ANGLAGE_TOOLTIP = (
    'Apply watch-style edge bevels (anglage) using native Fusion chamfers. '
    'Select edges, set width, optional angle, tangent chain.'
)

# --- ANGLAGE defaults (user-facing mm / deg) --------------------------------

ANGLAGE_MODE_EQUAL = 'Equal Distance'
ANGLAGE_MODE_DISTANCE_ANGLE = 'Distance + Angle'
ANGLAGE_DEFAULT_MODE = ANGLAGE_MODE_EQUAL

ANGLAGE_WIDTH_MM = 0.40
ANGLAGE_ANGLE_DEG = 45.0
ANGLAGE_TANGENT_CHAIN = True
ANGLAGE_FLIP = False
ANGLAGE_FEATURE_NAME = 'Anglage'

